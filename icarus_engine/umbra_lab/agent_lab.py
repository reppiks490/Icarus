"""Opt-in synthetic agent experiments; no production routes or live authority."""
from __future__ import annotations

from collections import defaultdict, deque
from contextlib import closing
import json
import multiprocessing as mp
import os
from pathlib import Path
import re
import sqlite3
import time

from .adaptive_foundry import _head, _verified, _indexed
from .distillation import Bank, FIELDS, ZERO, digest
from .learning_fabric import RESERVE, dataset, fit, validate, schedule

AGENTS = frozenset(f'Q{i:02d}-{suffix}' for i in range(1,11) for suffix in 'PTXV')
ESTIMATES = {'linear':256_000_000, 'deep':1_300_000_000}
MAX_PAYLOAD = 2_000_000
MAX_HISTORY = 256


def _agent(agent):
    if not isinstance(agent,str) or agent not in AGENTS:
        raise ValueError('unknown federation identity')
    return agent


def _bank(bank, head):
    _head(head)
    if not isinstance(bank,Bank) or bank.head!=head:
        raise ValueError('evidence head mismatch')
    return Bank(bank.rows,head)


class Vault:
    """Append-only per-agent candidate receipts, requiring externally pinned heads."""
    def __init__(self,path):
        self.path=str(path)
        if not self.path or self.path==':memory:': raise ValueError('local persistent path required')
        with closing(self._connect()) as c,c:
            c.execute('CREATE TABLE IF NOT EXISTS checkpoints(agent TEXT NOT NULL, seq INTEGER NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(agent,seq))')

    def _connect(self):
        c=sqlite3.connect(self.path,timeout=5)
        c.execute('PRAGMA synchronous=FULL')
        return c

    def _history(self,c,agent,head):
        _agent(agent); _head(head)
        n,size=c.execute('SELECT COUNT(*),COALESCE(SUM(length(CAST(payload AS BLOB))),0) FROM checkpoints WHERE agent=?',(agent,)).fetchone()
        if n>MAX_HISTORY or size>MAX_HISTORY*50_000: raise ValueError('history budget exceeded')
        out=[]; previous=ZERO
        for i,(seq,payload) in enumerate(c.execute('SELECT seq,payload FROM checkpoints WHERE agent=? ORDER BY seq',(agent,)),1):
            try:
                r=json.loads(payload); b=r['body']; validate(b['checkpoint']); _head(b['evidence_head'])
                if seq!=i or set(r)!={'body','hash'} or set(b)!={'agent','parent','evidence_head','checkpoint','status'} or b['agent']!=agent or b['parent']!=previous or b['status']!='synthetic-candidate' or r['hash']!=digest(b):
                    raise ValueError('receipt mismatch')
            except (KeyError,TypeError,ValueError) as exc:
                raise ValueError('invalid checkpoint history') from exc
            previous=r['hash']; out.append(r)
        if previous!=head: raise ValueError('stale or altered agent head')
        return out

    def history(self,agent,head):
        with closing(self._connect()) as c,c:
            c.execute('BEGIN')
            return self._history(c,agent,head)

    def record(self,agent,bank,evidence_head,checkpoint,parent):
        _agent(agent); validate(checkpoint)
        b=_bank(bank,evidence_head)
        if digest(dataset(b,checkpoint['model_digest'],'train'))!=checkpoint['training_digest']:
            raise ValueError('training lineage mismatch')
        body={'agent':agent,'parent':_head(parent),'evidence_head':evidence_head,'checkpoint':checkpoint,'status':'synthetic-candidate'}
        receipt={'body':body,'hash':digest(body)}
        payload=json.dumps(receipt,sort_keys=True,separators=(',',':'),allow_nan=False)
        if len(payload)>50_000: raise ValueError('checkpoint budget exceeded')
        with closing(self._connect()) as c,c:
            c.execute('BEGIN IMMEDIATE'); rows=self._history(c,agent,parent)
            if len(rows)>=MAX_HISTORY: raise ValueError('history budget exceeded')
            c.execute('INSERT INTO checkpoints VALUES(?,?,?)',(agent,len(rows)+1,payload))
        return receipt['hash']


def prequential(bank,model_digest,window=16):
    """Predict then observe in synthetic append order; bounded rolling drift heuristic."""
    _head(model_digest)
    if type(window) is not int or not 2<=window<=128: raise ValueError('invalid window')
    rows=[r for r in _verified(bank) if r['split']=='train' and r['model_digest']==model_digest]
    _indexed(rows,[model_digest])
    histories=defaultdict(lambda:deque(maxlen=2*window)); trace=[]; drift_count=0
    for r in rows:
        history=histories[r['task']['kind']]; recent=list(history)[-window:]
        p=(1+sum(recent))/(2+len(recent)); y=int(r['correct'])
        history.append(y); values=list(history)
        drift=len(values)==2*window and abs(sum(values[:window])-sum(values[window:]))/window>=.5
        drift_count+=int(drift)
        trace.append({'identity':r['identity'],'task_hash':r['task_hash'],'split':'train','probability':p,'outcome':y,'drift':drift})
    if not trace: raise ValueError('empty prequential evidence')
    return {'count':len(trace),'brier':sum((r['probability']-r['outcome'])**2 for r in trace)/len(trace),'drift_count':drift_count,'trace':trace,'status':'synthetic-prequential-only'}


def available_ram():
    """Native Windows/Linux telemetry; best effort, not a hard reservation."""
    if os.name=='nt':
        import ctypes
        class Status(ctypes.Structure):
            _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(k,ctypes.c_ulonglong) for k in ('total','available','page_total','page_available','virtual_total','virtual_available','extended')]
        status=Status(); status.length=ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise RuntimeError('Windows memory telemetry unavailable')
        return int(status.available)
    meminfo=Path('/proc/meminfo')
    if not meminfo.is_file(): raise RuntimeError('native memory telemetry unavailable')
    fields=[line.split() for line in meminfo.read_text().splitlines() if line.startswith('MemAvailable:')]
    if len(fields)!=1 or len(fields[0])!=3 or fields[0][2]!='kB': raise ValueError('invalid memory telemetry')
    n=int(fields[0][1])*1024
    root=Path('/sys/fs/cgroup').resolve()
    if (root/'cgroup.controllers').is_file():
        groups=[line[3:] for line in Path('/proc/self/cgroup').read_text().splitlines() if line.startswith('0::')]
        if len(groups)!=1: raise ValueError('invalid unified cgroup identity')
        group=(root/groups[0].lstrip('/')).resolve()
        if not group.is_relative_to(root) or not group.is_dir(): raise ValueError('unresolved cgroup')
        while True:
            cap=group/'memory.max'; used=group/'memory.current'
            if cap.is_file():
                limit=cap.read_text().strip()
                if limit!='max': n=min(n,max(0,int(limit)-int(used.read_text().strip())))
            if group==root: break
            group=group.parent
    if type(n) is not int or n<0: raise ValueError('invalid physical memory')
    return n


def _worker(pipe, payload, job):
    try:
        os.environ['OMP_NUM_THREADS']='1'; os.environ['MKL_NUM_THREADS']='1'
        start=time.monotonic_ns(); data=json.loads(payload)
        if job['kind']=='deep':
            import torch
            torch.set_num_threads(1)
        bank=Bank(data['rows'],data['head'])
        checkpoint=fit(bank,job['model_digest'],job['kind'],job['epochs'],job['seed'])
        result={'checkpoint':checkpoint,'pid':os.getpid(),'started_ns':start,'finished_ns':time.monotonic_ns()}
    except Exception as exc:
        result={'error':type(exc).__name__}
    try: pipe.send_bytes(json.dumps(result,allow_nan=False).encode('utf-8'))
    finally: pipe.close()


def run_wave(bank,head,jobs,*,allow_execution=False,memory=None,timeout=30):
    """Fixed two-child synthetic wave; estimates and polling are not hard OS limits."""
    if allow_execution is not True or type(timeout) is not int or not 1<=timeout<=120 or not isinstance(jobs,list) or not 1<=len(jobs)<=40:
        raise ValueError('explicit execution and bounded wave required')
    b=_bank(bank,head); specs={}; payloads={}
    for j in jobs:
        if not isinstance(j,dict) or set(j)!={'agent','model_digest','kind','epochs','seed'}: raise ValueError('job schema')
        a=_agent(j['agent']); _head(j['model_digest'])
        if a in specs or not isinstance(j['kind'],str) or j['kind'] not in ESTIMATES or type(j['epochs']) is not int or not 1<=j['epochs']<=200 or type(j['seed']) is not int or not 0<=j['seed']<2**32: raise ValueError('invalid job')
        train=Bank()
        for r in b.rows:
            r=r['body']
            if r['split']=='train' and r['model_digest']==j['model_digest']: train.append({k:r[k] for k in FIELDS})
        payload=json.dumps({'rows':train.rows,'head':train.head},separators=(',',':'),ensure_ascii=True)
        if len(payload)>MAX_PAYLOAD: raise ValueError('worker input too large')
        dataset(train,j['model_digest'],'train')
        specs[a]=dict(j); payloads[a]=payload
    def measure():
        actual=available_ram()
        if memory is None: return actual
        requested=memory()
        if type(requested) is not int or requested<0: raise ValueError('invalid supplemental telemetry')
        return min(actual,requested)
    plan=schedule([dict(id=a,ram=ESTIMATES[j['kind']],threads=1,deps=[]) for a,j in specs.items()],measure(),2,[])
    output={'completed':[],'failed':[],'deferred':plan['deferred'][:],'promotion_authorized':False,'reserve_bytes':RESERVE,'status':'synthetic-wave-only'}
    ctx=mp.get_context('spawn'); children={}; deadline=time.monotonic()+timeout
    try:
        for a in plan['admitted']:
            if measure()<RESERVE+ESTIMATES[specs[a]['kind']]:
                output['deferred'].append(a); continue
            rx,tx=ctx.Pipe(duplex=False); p=ctx.Process(target=_worker,args=(tx,payloads[a],specs[a]))
            try: p.start()
            except BaseException:
                rx.close(); tx.close(); raise
            tx.close(); children[a]=(p,rx)
        pending=set(children)
        while pending:
            if time.monotonic()>=deadline or measure()<RESERVE:
                reason='deadline' if time.monotonic()>=deadline else 'memory-reserve'
                output['failed'].extend({'agent':a,'reason':reason} for a in sorted(pending)); break
            for a in sorted(pending):
                p,rx=children[a]
                if not rx.poll() and p.is_alive(): continue
                try:
                    result=json.loads(rx.recv_bytes(100_000)) if rx.poll() else {'error':'worker-exit'}
                    if 'error' in result: raise ValueError(result['error'])
                    checkpoint=result['checkpoint']; validate(checkpoint); j=specs[a]
                    if checkpoint['model_digest']!=j['model_digest'] or checkpoint['kind']!=j['kind'] or checkpoint['epochs']!=j['epochs'] or checkpoint['seed']!=j['seed'] or checkpoint['training_digest']!=digest(dataset(b,j['model_digest'],'train')) or result['pid']!=p.pid:
                        raise ValueError('worker result mismatch')
                    output['completed'].append(dict(result,agent=a,evidence_head=head))
                except (OSError,EOFError,ValueError,KeyError,TypeError):
                    output['failed'].append({'agent':a,'reason':'invalid-or-failed-worker'})
                pending.remove(a)
            if pending: time.sleep(.025)
    finally:
        for p,rx in children.values():
            rx.close(); p.join(.2)
            if p.is_alive(): p.terminate(); p.join(.5)
            if p.is_alive(): p.kill(); p.join(1)
            if not p.is_alive(): p.close()
    for k in ('completed','failed'): output[k].sort(key=lambda r:r['agent'])
    return output

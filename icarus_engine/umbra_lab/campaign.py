"""Bounded continuation across synthetic federation training waves; never a production promotion."""
from __future__ import annotations

from .adaptive_foundry import _head
from .agent_lab import AGENTS, ESTIMATES, Vault, _bank, available_ram, run_wave
from .distillation import Bank, FIELDS, ZERO, digest, expected
from .learning_fabric import dataset, evaluate, schedule


def curriculum(agents=None):
    """Deterministic toy model responses, not outputs from real language models."""
    agents=sorted(AGENTS) if agents is None else agents
    if not isinstance(agents,list) or not agents or not all(isinstance(a,str) and a in AGENTS for a in agents) or len(set(agents))!=len(agents):
        raise ValueError('invalid curriculum identities')
    b=Bank(); jobs=[]
    for agent in sorted(agents):
        family=int(agent[1:3]); suffix=agent[-1]
        model=digest({'schema':'umbra.synthetic_teacher_fixture.v1','agent':agent})
        jobs.append(dict(agent=agent,model_digest=model,kind='deep' if suffix=='P' else 'linear',epochs=80,seed=family*10+'PTXV'.index(suffix)))
        for split,start in [('train',1),('holdout',21)]:
            for n in range(start,start+4):
                for sa in (-1,1):
                    for sb in (-1,1):
                        task={'kind':'multiply' if family%2 else 'ratio','a':sa*(family*100+n),'b':sb*(family+2)}
                        correct={'P':sa==sb,'T':sa>0,'X':sa<0,'V':sb>0}[suffix]
                        answer=expected(task)+int(not correct)
                        b.append(dict(identity=f'{agent}-{split}-{n}-{sa}-{sb}',group=f'family-{family}-{n}',split=split,task=task,answer=str(answer),source='synthetic',rights='synthetic-owned',model_digest=model))
    return b,jobs


def _result(bank,head,job,record,receipt_head):
    body=record['body']; c=body['checkpoint']
    if body['evidence_head']!=head or body['agent']!=job['agent'] or any(c[k]!=job[k] for k in ('model_digest','kind','epochs','seed')) or c['training_digest']!=digest(dataset(bank,job['model_digest'],'train')):
        raise ValueError('resume checkpoint does not match campaign')
    metric=evaluate(bank,c,'holdout')
    return {'agent':job['agent'],'kind':job['kind'],'receipt_head':receipt_head,'checkpoint_digest':c['digest'],'training_digest':c['training_digest'],'metrics':metric}


def advance(bank,head,jobs,vault,heads,*,allow_execution=False,max_waves=20,memory=None):
    """Continue until bounded wave budget, exhaustion or a no-progress wave.

    A caller must persist returned heads separately. An unpinned post-crash write
    is refused, not automatically trusted. This API is synthetic-only.
    """
    if allow_execution is not True or type(max_waves) is not int or not 1<=max_waves<=40 or not isinstance(vault,Vault) or not isinstance(jobs,list) or not 1<=len(jobs)<=40 or not isinstance(heads,dict):
        raise ValueError('invalid campaign or execution budget')
    b=_bank(bank,head); specs={}; scoped={}
    for j in jobs:
        if not isinstance(j,dict) or set(j)!={'agent','model_digest','kind','epochs','seed'} or not isinstance(j['agent'],str) or j['agent'] not in AGENTS or j['agent'] in specs or not isinstance(j['kind'],str) or j['kind'] not in ESTIMATES or type(j['epochs']) is not int or not 1<=j['epochs']<=200 or type(j['seed']) is not int or not 0<=j['seed']<2**32:
            raise ValueError('invalid campaign job')
        _head(j['model_digest']); specs[j['agent']]=dict(j)
    for j in specs.values():
        scoped.setdefault(j['model_digest'], Bank())
    for row in b.rows:
        body=row['body']; model=body['model_digest']
        if model in scoped: scoped[model].append({k:body[k] for k in FIELDS})
    for model,scope in scoped.items():
        data=dataset(scope,model,'train')
        if {r['y'] for r in data}!={0,1}: raise ValueError('both outcomes required')
        dataset(scope,model,'holdout')
    if not set(heads)<=set(specs): raise ValueError('unknown resume identity')
    pins=dict(heads); results={}
    for a,j in specs.items():
        h=_head(pins[a]) if a in pins else ZERO
        rows=vault.history(a,h)
        if a in pins:
            if not rows: raise ValueError('empty pinned history')
            results[a]=_result(scoped[j['model_digest']],head,j,rows[-1],h)
    waves=0; failures=[]; attempted_failures=set(); timings=[]
    while waves<max_waves:
        pending=[a for a in specs if a not in pins and a not in attempted_failures]
        if not pending: break
        waves+=1
        available=available_ram()
        if memory is not None:
            supplement=memory()
            if type(supplement) is not int or supplement<0: raise ValueError('invalid supplemental telemetry')
            available=min(available,supplement)
        plan=schedule([dict(id=a,ram=ESTIMATES[specs[a]['kind']],threads=1,deps=[]) for a in pending],available,2,[])
        if not plan['admitted']: break
        out=run_wave(b,head,[specs[a] for a in plan['admitted']],allow_execution=True,memory=memory)
        failures.extend(out['failed']); attempted_failures.update(r['agent'] for r in out['failed'])
        for r in out['completed']:
            a=r['agent']; c=r['checkpoint']
            # Validate evaluation before persistence; metrics never select/promote a candidate.
            scope=scoped[c['model_digest']]; evaluate(scope,c,'holdout')
            h=vault.record(a,b,head,c,ZERO)
            results[a]=_result(scope,head,specs[a],vault.history(a,h)[-1],h); pins[a]=h
            timings.append({k:r[k] for k in ('agent','pid','started_ns','finished_ns')})
        if not out['completed'] and not out['failed']: break
    pending=[a for a in specs if a not in pins]
    return {'status':'incomplete' if pending else 'complete-synthetic-candidates','manifest_digest':digest({'schema':'umbra.synthetic_campaign.v1','head':head,'jobs':list(specs.values())}),
            'heads':pins,'results':[results[a] for a in sorted(results)],'pending':pending,'waves':waves,'failed':failures,'timings':timings,'promotion_authorized':False}

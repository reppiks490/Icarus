"""Synthetic research only: durable evidence, group-balanced routing and evaluation."""
from __future__ import annotations

from collections import defaultdict
from contextlib import closing
import json
import re
import sqlite3

from .distillation import Bank, expected

MAX_ROWS = 4096
MAX_BYTES = 32_000_000
MAX_BATCH = 128


def _head(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
        raise ValueError('invalid externally pinned digest')
    return value


def _encode(row):
    return json.dumps(row, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


class Store:
    """SQLite single-writer CAS; callers must retain the trusted head outside this DB."""
    def __init__(self, path):
        self.path = str(path)
        if not self.path or self.path == ':memory:':
            raise ValueError('persistent local path required')
        with closing(self._connect()) as c, c:
            c.execute('CREATE TABLE IF NOT EXISTS evidence (seq INTEGER PRIMARY KEY CHECK(seq>0), payload TEXT NOT NULL)')

    def _connect(self):
        c = sqlite3.connect(self.path, timeout=5)
        c.execute('PRAGMA synchronous=FULL')
        return c

    @staticmethod
    def _snapshot(c, head):
        _head(head)
        n, size = c.execute('SELECT COUNT(*), COALESCE(SUM(length(CAST(payload AS BLOB))),0) FROM evidence').fetchone()
        if n > MAX_ROWS or size > MAX_BYTES:
            raise ValueError('store budget exceeded')
        rows = []
        for i, (seq, payload) in enumerate(c.execute('SELECT seq,payload FROM evidence ORDER BY seq'), 1):
            if seq != i:
                raise ValueError('sequence gap')
            try:
                rows.append(json.loads(payload))
            except (ValueError, TypeError) as exc:
                raise ValueError('invalid stored record') from exc
        return Bank(rows, head), size

    def snapshot(self, head):
        with closing(self._connect()) as c, c:
            c.execute('BEGIN')
            return self._snapshot(c, head)[0]

    def append(self, candidates, head):
        _head(head)
        if not isinstance(candidates,list) or not 1<=len(candidates)<=MAX_BATCH:
            raise ValueError('invalid batch size')
        with closing(self._connect()) as c, c:
            c.execute('BEGIN IMMEDIATE')
            bank, size = self._snapshot(c, head)
            seq = len(bank.rows)
            if seq+len(candidates)>MAX_ROWS:
                raise ValueError('row budget exceeded')
            for candidate in candidates:
                payload = _encode(bank.append(candidate))
                size += len(payload)
                if size>MAX_BYTES:
                    raise ValueError('byte budget exceeded')
                seq += 1
                c.execute('INSERT INTO evidence(seq,payload) VALUES (?,?)',(seq,payload))
            return bank.head


def _verified(bank):
    if not isinstance(bank,Bank):
        raise ValueError('invalid reasoning bank')
    rows=bank.rows
    if len(rows)>MAX_ROWS:
        raise ValueError('bank exceeds pilot budget')
    return [r['body'] for r in Bank(rows,bank.head).rows]


def _indexed(rows, models):
    """Reject duplicate responses and inconsistent group assignments."""
    by_model={m:{} for m in models}; groups={}
    for r in rows:
        m,k,g=r['model_digest'],r['task_hash'],r['group']
        if m not in by_model:
            continue
        if k in by_model[m] or groups.get(k,g)!=g:
            raise ValueError('duplicate response or conflicting task group')
        groups[k]=g
        by_model[m][k]=r
    return by_model


def recommend(bank, task, candidates):
    """Group-smoothed success score; advisory only, not a calibrated posterior."""
    expected(task)
    if not isinstance(candidates,list) or not 1<=len(candidates)<=40:
        raise ValueError('invalid candidate set')
    for m in candidates: _head(m)
    if len(set(candidates))!=len(candidates):
        raise ValueError('duplicate candidate')
    rows=[r for r in _verified(bank) if r['split']=='train' and r['task']['kind']==task['kind']]
    result=[]
    for model, tasks in _indexed(rows,candidates).items():
        groups=defaultdict(list)
        for r in tasks.values(): groups[r['group']].append(int(r['correct']))
        if groups:
            means=[sum(v)/len(v) for v in groups.values()]
            result.append({'model_digest':model,'groups':len(means),'tasks':len(tasks),'mean':(1+sum(means))/(2+len(means))})
    result.sort(key=lambda r:(-r['mean'],-r['groups'],r['model_digest']))
    return {'selected':result[0]['model_digest'] if result else None,'candidates':result,
            'status':'synthetic-advisory-only','promotion_authorized':False}


def paired_report(bank, candidate, baseline, split):
    _head(candidate); _head(baseline)
    if candidate==baseline or split not in ('validation','holdout'):
        raise ValueError('distinct models and evaluation split required')
    index=_indexed([r for r in _verified(bank) if r['split']==split],[candidate,baseline])
    a,b=index[candidate],index[baseline]
    common=sorted(a.keys() & b.keys())
    if not common:
        raise ValueError('no paired observations')
    groups=defaultdict(list)
    for key in common:
        groups[a[key]['group']].append(int(a[key]['correct'])-int(b[key]['correct']))
    deltas=[sum(v)/len(v) for v in groups.values()]
    return {'split':split,'matched_tasks':len(common),'unmatched':len(a.keys() ^ b.keys()),
            'groups':len(groups),'group_mean_delta':sum(deltas)/len(deltas),
            'group_wins':sum(d>0 for d in deltas),'group_losses':sum(d<0 for d in deltas),
            'group_ties':sum(d==0 for d in deltas),'promotion_authorized':False,
            'status':'synthetic-descriptive-only'}

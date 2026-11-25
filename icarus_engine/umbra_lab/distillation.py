"""Bounded synthetic reasoning bank; no model execution or training authority."""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import hashlib
import json
import re

ZERO = '0' * 64
FIELDS = {'identity','group','split','task','answer','source','model_digest','rights'}
SPLITS = frozenset(('train','validation','holdout'))


def digest(body):
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=True, allow_nan=False).encode('ascii')).hexdigest()


def bounded_int(value, nonnegative=False):
    if type(value) is not int or abs(value) >= 10**100 or (nonnegative and value < 0):
        raise ValueError('invalid bounded integer')
    return value


def expected(task):
    if not isinstance(task, dict):
        raise ValueError('invalid task')
    kind = task.get('kind')
    if kind in ('multiply','ratio') and set(task) == {'kind','a','b'}:
        a, b = bounded_int(task['a']), bounded_int(task['b'])
        if kind == 'multiply':
            return Fraction(a*b)
        if b == 0:
            raise ValueError('zero denominator')
        return Fraction(a,b)
    if kind == 'prefix_count' and set(task) == {'kind','decision_ns','events'}:
        decision = bounded_int(task['decision_ns'], True)
        events = task['events']
        if not isinstance(events,list) or len(events)>1024:
            raise ValueError('invalid event list')
        count = 0
        for clocks in events:
            if not isinstance(clocks,list) or len(clocks)!=3:
                raise ValueError('invalid event clocks')
            event, available, ingested = [bounded_int(x,True) for x in clocks]
            if not event <= available <= ingested:
                raise ValueError('invalid clock ordering')
            count += ingested <= decision
        return Fraction(count)
    raise ValueError('unsupported task')


def grade(task, answer):
    """Exact rational comparison; never interpret submitted text as code."""
    truth = expected(task)
    if not isinstance(answer,str) or len(answer)>512 or not re.fullmatch(r'[+-]?[0-9]+(?:/[0-9]+)?',answer):
        return False
    try:
        return Fraction(answer) == truth
    except (ValueError, ZeroDivisionError):
        return False


class Bank:
    """In-memory reference ledger with replay against an externally pinned head."""
    def __init__(self, rows=None, expected_head=None):
        self._rows=[]
        self._identities=set()
        self._groups={}
        self._tasks={}
        self._head=ZERO
        if rows is not None:
            if not isinstance(rows,list) or not isinstance(expected_head,str):
                raise ValueError('replay requires rows and trusted head')
            for row in rows:
                try:
                    raw={k:row['body'][k] for k in FIELDS}
                    actual=self.append(raw)
                    if actual!=row:
                        raise ValueError('row integrity failure')
                except (KeyError, TypeError) as exc:
                    raise ValueError('malformed row') from exc
        if expected_head is not None and self._head!=expected_head:
            raise ValueError('head mismatch')

    @property
    def head(self):
        return self._head

    @property
    def rows(self):
        return deepcopy(self._rows)

    def append(self, candidate):
        if not isinstance(candidate,dict) or set(candidate)!=FIELDS:
            raise ValueError('invalid candidate schema')
        body=deepcopy(candidate)
        for k in ('identity','group'):
            if not isinstance(body[k],str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}',body[k]):
                raise ValueError('invalid identifier')
        if not isinstance(body['split'],str) or body['split'] not in SPLITS:
            raise ValueError('invalid split')
        if body['source']!='synthetic' or body['rights']!='synthetic-owned':
            raise ValueError('only synthetic fixtures admitted')
        if not isinstance(body['model_digest'],str) or not re.fullmatch(r'[0-9a-f]{64}',body['model_digest']):
            raise ValueError('invalid model digest')
        if not isinstance(body['answer'],str) or len(body['answer'])>512:
            raise ValueError('invalid answer bounds')
        identity, group, split=body['identity'],body['group'],body['split']
        correct=grade(body['task'],body['answer'])
        task_hash=digest(body['task'])
        if identity in self._identities:
            raise ValueError('duplicate identity')
        if self._groups.get(group,split)!=split or self._tasks.get(task_hash,split)!=split:
            raise ValueError('cross-split group or task leakage')
        body.update(correct=correct, task_hash=task_hash, grader='exact-synthetic-v1')
        row={'previous_hash':self._head,'body':body}
        row['hash']=digest(row)
        self._rows.append(row)
        self._head=row['hash']
        self._identities.add(identity)
        self._groups[group]=split
        self._tasks[task_hash]=split
        return deepcopy(row)

    def training(self):
        seen=set()
        out=[]
        for row in self._rows:
            body=row['body']
            key=body['task_hash']
            if body['split']=='train' and body['correct'] and key not in seen:
                out.append(deepcopy(body)); seen.add(key)
        return out

    def metrics(self, split):
        if not isinstance(split,str) or split not in SPLITS:
            raise ValueError('invalid split')
        rows=[r['body'] for r in self._rows if r['body']['split']==split]
        return {'correct':sum(r['correct'] for r in rows),'total':len(rows)}

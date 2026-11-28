import sqlite3
from tempfile import TemporaryDirectory
from pathlib import Path
import pytest
from icarus_engine.umbra_lab.distillation import Bank, ZERO
from icarus_engine.umbra_lab.adaptive_foundry import Store, recommend, paired_report

A='a'*64
B='b'*64

def row(identity, n, model=A, correct=True, split='train', group=None):
    return dict(identity=identity,group=group or f'g{n}',split=split,
                task={'kind':'multiply','a':n,'b':2},answer=str(n*2+int(not correct)),
                source='synthetic',model_digest=model,rights='synthetic-owned')

def test_store_restart_and_stale_writer(tmp_path):
    p=tmp_path/'bank.db'; s=Store(p); t=Store(p)
    head=s.append([row('a',1)],ZERO)
    assert t.snapshot(head).training()[0]['identity']=='a'
    with pytest.raises(ValueError): t.append([row('b',2)],ZERO)
    assert Store(p).snapshot(head).head==head

def test_store_atomic_batch(tmp_path):
    s=Store(tmp_path/'bank.db')
    with pytest.raises(ValueError): s.append([row('a',1),row('a',2)],ZERO)
    assert s.snapshot(ZERO).rows==[]

def test_store_tamper_and_rollback(tmp_path):
    p=tmp_path/'bank.db'; s=Store(p); head=s.append([row('a',1)],ZERO)
    with sqlite3.connect(p) as c: c.execute('DELETE FROM evidence')
    with pytest.raises(ValueError): s.snapshot(head)

def test_store_rejects_oversize_batch(tmp_path):
    s=Store(tmp_path/'bank.db')
    with pytest.raises(ValueError): s.append([row(str(i),i) for i in range(129)],ZERO)

def test_router_observes_only_train_and_deduplicates_groups():
    b=Bank()
    for i in range(1,5):
        b.append(row(f'a{i}',i,A,True,group='same'))
        b.append(row(f'b{i}',i,B,False,group='same'))
    b.append(row('ha',8,A,False,'holdout'))
    b.append(row('hb',8,B,True,'holdout'))
    out=recommend(b,{'kind':'multiply','a':7,'b':2},[A,B])
    assert out['selected']==A
    assert out['candidates'][0]['groups']==1
    assert out['candidates'][0]['mean']==pytest.approx(2/3)
    assert out['status']=='synthetic-advisory-only'

def test_router_abstains_on_unseen_or_unqualified():
    b=Bank(); b.append(row('a',1))
    assert recommend(b,{'kind':'ratio','a':1,'b':2},[A,B])['selected'] is None
    assert recommend(b,{'kind':'multiply','a':1,'b':2},[B])['selected'] is None
    with pytest.raises(ValueError): recommend(b,{'kind':'multiply','a':1,'b':2},[A,A])

def test_paired_group_evaluation_and_unmatched():
    b=Bank()
    for n in (1,2,3):
        group='g1' if n<3 else 'g2'
        b.append(row(f'a{n}',n,A,True,'holdout',group))
        b.append(row(f'b{n}',n,B,n==3,'holdout',group))
    b.append(row('extra',4,A,True,'holdout'))
    r=paired_report(b,A,B,'holdout')
    assert r['matched_tasks']==3 and r['groups']==2 and r['unmatched']==1
    assert r['group_mean_delta']==pytest.approx(.5)
    assert r['promotion_authorized'] is False

def test_paired_rejects_duplicate_and_training_split():
    b=Bank(); b.append(row('a',1,A,True,'holdout')); b.append(row('a2',1,A,False,'holdout')); b.append(row('b',1,B,False,'holdout'))
    with pytest.raises(ValueError): paired_report(b,A,B,'holdout')
    with pytest.raises(ValueError): paired_report(b,A,B,'train')

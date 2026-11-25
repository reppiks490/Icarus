import sqlite3
import pytest
from icarus_engine.umbra_lab.distillation import Bank, ZERO
from icarus_engine.umbra_lab.learning_fabric import fit
from icarus_engine.umbra_lab.agent_lab import Vault, run_wave, prequential

H='a'*64

def bank():
    b=Bank()
    for split,start in [('train',1),('holdout',21)]:
        for n in range(start,start+8):
            for sign in (-1,1):
                a=n*sign
                b.append(dict(identity=f'{split}-{a}',group=f'g{n}',split=split,
                    task={'kind':'multiply','a':a,'b':2},answer=str(a*2+(sign<0)),
                    source='synthetic',rights='synthetic-owned',model_digest=H))
    return b

def spec(agent, kind='linear'):
    return dict(agent=agent,model_digest=H,kind=kind,epochs=10,seed=42)

def test_vault_isolates_agent_lineage(tmp_path):
    b=bank(); c=fit(b,H,'linear',epochs=3); v=Vault(tmp_path/'agents.db')
    p=v.record('Q01-P',b,b.head,c,ZERO); t=v.record('Q01-T',b,b.head,c,ZERO)
    assert p!=t
    assert v.history('Q01-P',p)[0]['body']['checkpoint']==c
    assert v.history('Q01-T',t)[0]['body']['checkpoint']==c
    with pytest.raises(ValueError): v.record('Q01-P',b,b.head,c,ZERO)
    with pytest.raises(ValueError): v.history('Q01-T',p)
    with pytest.raises(ValueError): v.record('Q99-P',b,b.head,c,ZERO)

def test_vault_rejects_mismatched_training_and_tampering(tmp_path):
    b=bank(); c=fit(b,H,'linear',epochs=3); p=tmp_path/'agents.db'; v=Vault(p)
    with pytest.raises(ValueError): v.record('Q01-P',b,ZERO,c,ZERO)
    head=v.record('Q01-P',b,b.head,c,ZERO)
    with sqlite3.connect(p) as db: db.execute('DELETE FROM checkpoints')
    with pytest.raises(ValueError): v.history('Q01-P',head)

def test_wave_refuses_unapproved_and_low_ram():
    b=bank(); jobs=[spec('Q01-P'),spec('Q01-T')]
    with pytest.raises(ValueError): run_wave(b,b.head,jobs,allow_execution=False)
    out=run_wave(b,b.head,jobs,allow_execution=True,memory=lambda:1_800_000_000)
    assert out['completed']==[] and len(out['deferred'])==2

def test_wave_real_parallel_processes():
    b=bank(); jobs=[spec('Q01-P'),spec('Q01-T')]
    # Inject a controlled telemetry fixture for execution contract, not an OS memory claim.
    out=run_wave(b,b.head,jobs,allow_execution=True,memory=lambda:4_000_000_000)
    assert len(out['completed'])==2 and not out['failed']
    assert len({r['pid'] for r in out['completed']})==2
    assert all(r['checkpoint']['training_count']==16 for r in out['completed'])
    assert all(r['evidence_head']==b.head for r in out['completed'])
    assert out['promotion_authorized'] is False

def test_prequential_predicts_before_observing():
    b=bank(); out=prequential(b,H,window=4)
    assert out['count']==16 and out['trace'][0]['probability']==.5
    assert len(out['trace'])==16 and all(t['split']=='train' for t in out['trace'])
    assert out['status']=='synthetic-prequential-only'
    # Holdout additions do not change prequential results.
    c=Bank(); fields={'identity','group','split','task','answer','source','rights','model_digest'}
    for r in b.rows:
        if r['body']['split']=='train': c.append({k:r['body'][k] for k in fields})
    assert prequential(c,H,window=4)==out

def test_prequential_drift_detects_reversal():
    b=Bank()
    for n in range(16):
        b.append(dict(identity=str(n),group=f'g{n}',split='train',task={'kind':'multiply','a':n,'b':2},
            answer=str(n*2+int(n>=8)),source='synthetic',rights='synthetic-owned',model_digest=H))
    out=prequential(b,H,window=4)
    assert out['drift_count']>0
    assert out['trace'][-1]['probability']<out['trace'][8]['probability']

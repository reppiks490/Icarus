import pytest
from icarus_engine.umbra_lab.agent_lab import Vault, AGENTS
from icarus_engine.umbra_lab.campaign import curriculum, advance


def test_curriculum_exact_federation_and_split_groups():
    b,jobs=curriculum()
    assert {j['agent'] for j in jobs}==AGENTS
    assert len(jobs)==40 and len({j['model_digest'] for j in jobs})==40
    assert sum(j['kind']=='deep' for j in jobs)==10
    assert len(b.rows)==40*32
    assert b.head==curriculum()[0].head


def test_campaign_moves_through_checkpoints_and_resumes(tmp_path):
    b,jobs=curriculum(['Q01-T','Q01-V','Q02-T','Q02-V'])
    v=Vault(tmp_path/'campaign.db')
    first=advance(b,b.head,jobs,v,{},allow_execution=True,max_waves=1)
    assert len(first['heads'])==2 and first['status']=='incomplete'
    second=advance(b,b.head,jobs,v,first['heads'],allow_execution=True,max_waves=2)
    assert len(second['heads'])==4 and second['status']=='complete-synthetic-candidates'
    assert set(first['heads'].items())<=set(second['heads'].items())
    assert second['promotion_authorized'] is False
    third=advance(b,b.head,jobs,v,second['heads'],allow_execution=True,max_waves=1)
    assert third['waves']==0 and third['heads']==second['heads']


def test_campaign_fails_closed_on_stale_head_or_changed_spec(tmp_path):
    b,jobs=curriculum(['Q01-T'])
    v=Vault(tmp_path/'campaign.db')
    out=advance(b,b.head,jobs,v,{},allow_execution=True,max_waves=1)
    with pytest.raises(ValueError): advance(b,b.head,jobs,v,{},allow_execution=True,max_waves=1)
    with pytest.raises(ValueError): advance(b,b.head,[dict(jobs[0],seed=99)],v,out['heads'],allow_execution=True,max_waves=1)
    with pytest.raises(ValueError): advance(b,b.head,jobs,v,out['heads'],allow_execution=False)


def test_campaign_no_progress_returns_without_spin(tmp_path):
    b,jobs=curriculum(['Q01-T','Q01-V'])
    out=advance(b,b.head,jobs,Vault(tmp_path/'campaign.db'),{},allow_execution=True,max_waves=20,memory=lambda:1_800_000_000)
    assert out['waves']==1 and out['heads']=={} and len(out['pending'])==2

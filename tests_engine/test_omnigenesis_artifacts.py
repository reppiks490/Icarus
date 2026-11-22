"""Unified OMNIGENESIS scientific artifacts: immutability and provenance."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

from icarus_engine.omnigenesis import ResearchLedger
from icarus_engine.omnigenesis.automata import compile_automaton
from icarus_engine.omnigenesis.formal import formal_certificate
from icarus_engine.omnigenesis.simulation import synthetic_scenario, replay_book
from icarus_engine.omnigenesis.first_passage import label_first_passage
from icarus_engine.omnigenesis.evolution import compile_proposal, plan_capabilities


def formal():
    return formal_certificate(compile_automaton({
        "name":"proof","states":["WAIT","HIT","MISS"],
        "initial":"WAIT","terminal_states":["HIT","MISS"],
        "transitions":[
            {"from":"WAIT","to":"HIT","feature":"x",
             "op":"gte","threshold":1},
            {"from":"WAIT","to":"MISS","feature":"x",
             "op":"lt","threshold":1},
        ]
    }))


def passage():
    t=datetime(2026,1,1,tzinfo=timezone.utc)
    bars=[]
    for i in range(10):
        now=t+timedelta(minutes=i)
        bars.append({"record_id":f"record_{i}",
                     "observed_at":(now-timedelta(seconds=1)).isoformat(),
                     "received_at":now.isoformat(),
                     "open_ticks":100,"high_ticks":101,
                     "low_ticks":99,"close_ticks":100})
    return label_first_passage({
        "asset":"NQ","source_commit":"f"*40,"bars":bars},
        upper_distance_ticks=3,lower_distance_ticks=3,horizon_bars=3)


def plan():
    proposal=compile_proposal({
        "name":"New failure detection",
        "kind":"verification_tool",
        "objective":"Build an independent counterexample detection algorithm.",
        "falsifier":"The model detects no new verified contradictions.",
        "evidence_ids":["a"*64],"depends_on":[],
        "estimated_compute_seconds":100,"estimated_cost_usd":0,
        "estimated_information_gain":0.5,
    })
    return plan_capabilities([proposal],max_compute_seconds=200,max_cost_usd=0)


def test_artifact_types_durable_immutable_idempotent(tmp_path):
    store=ResearchLedger(tmp_path)
    examples={
        "formal":formal(),
        "first_passage":passage(),
        "capability_plan":plan(),
        "synthetic_book":replay_book(synthetic_scenario(3,50)),
    }
    keys={}
    for name,report in examples.items():
        keys[name]=store.append_artifact(name,report)
        assert store.append_artifact(name,report)==keys[name]
    snap=store.snapshot()
    assert snap["artifact_count"]==4
    assert snap["study_count"]==0
    assert len(snap["recent_artifacts"])==4
    assert set(r["kind"] for r in snap["recent_artifacts"])==set(examples)
    assert all(r["research_only"] for r in snap["recent_artifacts"])
    assert all(len(r["artifact_id"])==64 for r in snap["recent_artifacts"])
    # The database contains summaries, never raw historic event rows.
    raw=(tmp_path/"research"/"omnigenesis.sqlite3").read_bytes()
    assert b'"labels"' not in raw
    assert b'"trades"' not in raw
    assert b"record_9" not in raw


def test_no_unauthorized_or_forged_artifact(tmp_path):
    store=ResearchLedger(tmp_path)
    report=formal()
    report["execution_authorized"]=True
    with pytest.raises(ValueError,match="cannot authorize"):
        store.append_artifact("formal",report)
    report=passage()
    report["label_count"]=99999
    with pytest.raises(ValueError,match="tamper"):
        store.append_artifact("first_passage",report)
    with pytest.raises(ValueError,match="unsupported"):
        store.append_artifact("order",{"status":"live"})


def test_cli_science_recorded_and_retrievable(tmp_path):
    command=[sys.executable,"-m","icarus_engine.omnigenesis"]
    proc=subprocess.run(command+["synthetic-book","--seed","7",
                                 "--steps","70","--root",str(tmp_path)],
                        capture_output=True,text=True,check=True)
    result=json.loads(proc.stdout)
    assert result["evidence_kind"]=="SYNTHETIC"
    status=subprocess.run(command+["status","--root",str(tmp_path)],
                          capture_output=True,text=True,check=True)
    snap=json.loads(status.stdout)
    assert snap["artifact_count"]==1
    assert snap["recent_artifacts"][0]["status"]=="SYNTHETIC"
    assert snap["authority"]["execution_authorized"] is False

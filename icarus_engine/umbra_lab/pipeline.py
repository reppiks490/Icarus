"""One deterministic research-only reference cycle; no production imports."""
from statistics import fmean
from . import evidence, science, world

def run(seed,n,shock):
    w=world.paired_world(seed,n,shock)
    l=evidence.Ledger()
    # Freeze a simple baseline before the target; synthetic labels only.
    l.forecast("baseline",0,1,.5,"synthetic")
    label=int(w["control"][0]>0)
    l.settle("baseline",1,label,"synthetic")
    c=evidence.capsule([{"id":"initial","event_ns":0,"available_ns":0,"ingested_ns":0,"value":0}],0)
    report={"schema":"umbra.reference_cycle.v1","authority":"research_only","domain":"synthetic",
            "seed":seed,"shock":shock,"paired_observations":n,"capsule_digest":c["digest"],
            "world_digest":evidence.digest(w),"ledger_verified":l.verify(),"ledger_head":l.entries[-1]["hash"],
            "mean_intervention_delta":fmean(y-x for x,y in zip(w["control"],w["intervention"])),
            "baseline_brier":science.brier([.5],[label]),"qualified_for_trading":False}
    return {**report,"digest":evidence.digest(report)}

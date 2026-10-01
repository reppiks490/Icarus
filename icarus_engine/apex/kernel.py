"""Unified orchestration kernel for ICARUS APEX Ω."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib,json
from pathlib import Path
from typing import Any, Mapping
from .adapters import sibling_evidence
from .ancestry import EvidenceAncestry
from .contracts import authority_flags, parse_utc
from .crowdhunt import crowd_map
from .epistemics import epistemic_kernel_snapshot
from .force_field import pressure_tensor
from .information_gain import rank_experiments
from .institutional import institutional_mechanics
from .liquidity import liquidity_topology
from .macro_state import economic_world_state
from .participants import participant_state
from .store import ApexStore

def _now()->str:return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
def _finite_json_copy(body:Mapping[str,Any])->dict[str,Any]:
    if not isinstance(body,Mapping):raise ValueError("research mutation must be an object")
    out=dict(body)
    try:json.dumps(out,sort_keys=True,separators=(",",":"),allow_nan=False)
    except (TypeError,ValueError) as ex:raise ValueError("research mutation must be finite JSON") from ex
    return out
class ApexKernel:
    def __init__(self,base_dir,*,possibility=None,chronofold=None,pantheon=None,parallax=None,dreamstate=None,sibyl=None):
        self.base_dir=Path(base_dir);self.store=ApexStore(self.base_dir);self._siblings={"possibility":possibility,"chronofold":chronofold,"pantheon":pantheon,"parallax":parallax,"dreamstate":dreamstate,"sibyl":sibyl};self._research_events_path=self.base_dir/"research"/"apex-research-events.jsonl";self._research_events_path.parent.mkdir(parents=True,exist_ok=True)
    def ingest_evidence(self,body:Mapping[str,Any])->dict[str,Any]:return self.store.record_evidence(body)
    def resolve_engine_evidence_lineage(self,engine_evidence_ids:Mapping[str,Any],*,as_of:str|None=None)->dict[str,Any]:
        """Resolve engine evidence IDs into verified APEX root-source ancestry."""
        if not isinstance(engine_evidence_ids,Mapping) or not engine_evidence_ids:
            raise ValueError("engine_evidence_ids must be a non-empty object")
        if len(engine_evidence_ids)>32:
            raise ValueError("engine_evidence_ids exceeds 32 engines")
        boundary=as_of or _now();parse_utc(boundary,"as_of")
        evidence=self.store.evidence_as_of(boundary)
        ancestry=EvidenceAncestry()
        for row in evidence: ancestry.add(row)
        lineage={};support_by_engine={};seen_engines=set()
        for raw_engine,raw_ids in engine_evidence_ids.items():
            if not isinstance(raw_engine,str) or not raw_engine.strip():
                raise ValueError("engine_evidence_ids engine names must be non-empty strings")
            engine=raw_engine.strip()
            if len(engine)>64:
                raise ValueError("engine_evidence_ids engine name exceeds 64 characters")
            if engine in seen_engines:
                raise ValueError(f"duplicate normalized engine name: {engine}")
            seen_engines.add(engine)
            if not isinstance(raw_ids,list) or not raw_ids or len(raw_ids)>32:
                raise ValueError(f"engine_evidence_ids.{engine} must contain 1-32 evidence IDs")
            ids=[]
            for raw_id in raw_ids:
                if not isinstance(raw_id,str) or not raw_id.strip():
                    raise ValueError(f"engine_evidence_ids.{engine} contains an invalid evidence ID")
                eid=raw_id.strip()
                if len(eid)>128:
                    raise ValueError(f"engine_evidence_ids.{engine} evidence ID exceeds 128 characters")
                ids.append(eid)
            if len(set(ids))!=len(ids):
                raise ValueError(f"engine_evidence_ids.{engine} must be unique")
            support=ancestry.effective_support(ids)
            if not support.get("integrity_ok"):
                missing=", ".join(support.get("missing_dependencies",[])) or "none"
                cycles=", ".join(support.get("cycle_evidence_ids",[])) or "none"
                raise ValueError(f"APEX evidence lineage integrity failure for {engine}; missing={missing}; cycles={cycles}")
            roots=set()
            for eid in ids: roots.update(ancestry.roots(eid))
            if not roots:
                raise ValueError(f"APEX evidence lineage for {engine} resolved to no root sources")
            root_ids=sorted(roots)
            root_tokens=sorted(
                "apex-root:" + hashlib.sha256(root.encode("utf-8")).hexdigest()[:32]
                for root in root_ids
            )
            lineage[engine]=root_tokens
            support_by_engine[engine]={
                "evidence_ids":ids,
                "root_ids":root_ids,
                "root_tokens":root_tokens,
                "nominal_support":support["nominal_support"],
                "effective_independent_families":support["effective_independent_families"],
                "overlap_ratio":support["overlap_ratio"],
                "semantic_duplicate_count":support["semantic_duplicate_count"],
                "integrity_ok":True,
            }
        return {
            "schema_version":"icarus-apex-engine-lineage-v1",
            "status":"VERIFIED",
            "as_of":boundary,
            "engine_evidence_lineage":lineage,
            "engine_support":support_by_engine,
            "lineage_owner":"APEX_EVIDENCE_ANCESTRY",
            **authority_flags(),
        }
    def _record_research_event(self,event_type:str,body:Mapping[str,Any])->dict[str,Any]:
        semantic=_finite_json_copy(body);semantic.update(authority_flags());event={"event_type":event_type,"semantic":semantic};raw=json.dumps(event,sort_keys=True,separators=(",",":"),allow_nan=False);event_id=hashlib.sha256(raw.encode()).hexdigest();line=json.dumps({"event_id":event_id,**event},sort_keys=True,separators=(",",":"),allow_nan=False);existing=set()
        if self._research_events_path.exists():
            for prior in self._research_events_path.read_text(encoding="utf-8").splitlines():
                try:obj=json.loads(prior)
                except json.JSONDecodeError:continue
                if isinstance(obj,dict) and isinstance(obj.get("event_id"),str):existing.add(obj["event_id"])
        if event_id not in existing:
            with self._research_events_path.open("a",encoding="utf-8",newline="\n") as fh:fh.write(line+"\n")
        return {"ok":True,"idempotent":event_id in existing,"event_id":event_id,**semantic}
    def record_outcome(self,body:Mapping[str,Any])->dict[str,Any]:
        semantic=_finite_json_copy(body)
        if not isinstance(semantic.get("outcome_id"),str) or not semantic["outcome_id"].strip():raise ValueError("outcome_id is required")
        if "as_of" in semantic:parse_utc(str(semantic["as_of"]),"as_of")
        return self._record_research_event("outcome",semantic)
    def record_model_observation(self,body:Mapping[str,Any])->dict[str,Any]:
        semantic=_finite_json_copy(body)
        if not isinstance(semantic.get("model_id"),str) or not semantic["model_id"].strip():raise ValueError("model_id is required")
        if not isinstance(semantic.get("as_of"),str):raise ValueError("as_of is required")
        parse_utc(semantic["as_of"],"as_of");semantic.update(authority_flags())
        if "gap" in semantic and "state" in semantic:
            result=self.store.record_reality_gap(semantic);return {**result,**semantic}
        return self._record_research_event("model_observation",semantic)
    def propose_experiment(self,body:Mapping[str,Any])->dict[str,Any]:
        semantic=_finite_json_copy(body);eid=str(semantic.get("id") or "").strip()
        if not eid:raise ValueError("experiment id is required")
        ranked=rank_experiments(["H1","H2"],[semantic]);proposal={**semantic,"score":ranked[0]["score"] if ranked else None,**authority_flags()}
        return self._record_research_event("experiment",proposal)
    @staticmethod
    def _price_grid(evidence:list[Mapping[str,Any]])->list[float]:
        values=set()
        for row in evidence:
            value=row.get("value")
            if not isinstance(value,Mapping):continue
            for key in ("price","price_low","price_high"):
                raw=value.get(key)
                if isinstance(raw,(int,float)) and not isinstance(raw,bool):values.add(float(raw))
        return sorted(values)[:128]
    def snapshot(self,*,as_of:str|None=None,asset:str|None=None)->dict[str,Any]:
        boundary=as_of or _now();parse_utc(boundary,"as_of");normalized_asset=None if asset is None else str(asset).strip().upper();evidence=self.store.evidence_as_of(boundary)
        siblings=sibling_evidence(possibility=self._siblings["possibility"],chronofold=self._siblings["chronofold"],pantheon=self._siblings["pantheon"],parallax=self._siblings["parallax"],dreamstate=self._siblings["dreamstate"],sibyl=self._siblings["sibyl"]);epistemics=epistemic_kernel_snapshot(self.store,as_of=boundary);economic_world=economic_world_state(evidence,as_of=boundary)
        if normalized_asset:
            participants=participant_state(evidence,asset=normalized_asset,as_of=boundary,horizon_seconds=300);grid=self._price_grid(evidence);crowd=crowd_map(participants,price_grid=grid);institutional=institutional_mechanics(evidence,asset=normalized_asset,as_of=boundary,horizon_seconds=300);liquidity=liquidity_topology(evidence,asset=normalized_asset,as_of=boundary,price_grid=grid);forces=pressure_tensor(participants=participants,crowd=crowd,institutional=institutional,liquidity=liquidity,price_grid=grid,horizons=[300]);forces["status"]="ACTIVE" if any(c.get("status")=="ACTIVE" for c in forces.get("cells",[])) else "UNAVAILABLE"
        else:
            participants={"status":"UNAVAILABLE","classes":[],**authority_flags()};crowd={"status":"UNAVAILABLE","cells":[],**authority_flags()};institutional={"status":"UNAVAILABLE","mechanisms":[],**authority_flags()};liquidity={"status":"UNAVAILABLE","depth_status":"UNAVAILABLE","cells":[],**authority_flags()};forces={"status":"UNAVAILABLE","cells":[],**authority_flags()}
        causal_edges=self.store.causal_edges_as_of(boundary);cascade_edges=self.store.cascade_edges_as_of(boundary);worlds=self.store.world_states_as_of(boundary);unknown=self.store.unknown_force_events_as_of(boundary);model_health=self.store.model_credibility_as_of(boundary);reality=self.store.reality_gap_as_of(boundary);conscience=self.store.conscience_verdicts_as_of(boundary);degraded=[x["subsystem"] for x in siblings if x.get("status")=="DEGRADED"]
        status="DEGRADED" if degraded else ("EMPTY" if epistemics["status"]=="EMPTY" and not causal_edges and not cascade_edges and not worlds and not unknown else "ACTIVE")
        result={"schema_version":"icarus-apex-kernel-v1","as_of":boundary,"asset":normalized_asset,"status":status,"siblings":siblings,"epistemics":epistemics,"economic_world":economic_world,"participants":participants,"crowdhunt":crowd,"institutional":institutional,"liquidity":liquidity,"forces":forces,"causality":{"edges":causal_edges,**authority_flags()},"cascades":{"edges":cascade_edges,**authority_flags()},"worlds":{"states":worlds,**authority_flags()},"unknown_force":{"events":unknown,**authority_flags()},"self":{"model_health":model_health,"reality_gap":reality,"degraded_siblings":degraded,**authority_flags()},"conscience":{"verdicts":conscience,"status":"UNMEASURED" if not conscience else "AVAILABLE",**authority_flags()},**authority_flags()}
        json.dumps(result,sort_keys=True,separators=(",",":"),allow_nan=False);return result

"""Unknown-force residual and anonymous latent-state discovery for APEX Ω."""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from typing import Any, Mapping, Sequence

from .contracts import authority_flags


def _nonneg(v: Any, field: str) -> float:
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(float(v)) or float(v)<0: raise ValueError(f"{field} must be finite and non-negative")
    return float(v)


def unknown_force_event(*, observed: Mapping[str,Any], explained: Mapping[str,Any], evidence_ids: Sequence[str], as_of: str) -> dict[str,Any]:
    obs=_nonneg(observed.get("magnitude",0.0),"observed magnitude"); exp=_nonneg(explained.get("magnitude",0.0),"explained magnitude"); env=_nonneg(explained.get("envelope",0.0),"envelope")
    residual=max(0.0,obs-exp); fraction=0.0 if obs<=0 else min(1.0,residual/obs)
    inside=residual<=env
    state="KNOWN_KNOWN" if inside else ("KNOWN_UNKNOWN" if evidence_ids else "UNKNOWN_UNKNOWN")
    semantic={"schema_version":"icarus-apex-unknown-force-v1","as_of":as_of,"observed_magnitude":obs,"explained_magnitude":exp,"envelope":env,"unexplained_fraction":fraction,"state":state,"cause":None,"evidence_ids":sorted(str(x) for x in evidence_ids),**authority_flags()}
    semantic["residual_signature"]=hashlib.sha256(json.dumps({"fraction":round(fraction,6),"state":state},sort_keys=True).encode()).hexdigest()[:16]
    semantic["event_id"]=hashlib.sha256(json.dumps(semantic,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
    return semantic


def latent_candidate(events: Sequence[Mapping[str,Any]], *, min_independent_episodes: int=3) -> dict[str,Any]:
    if min_independent_episodes<1: raise ValueError("min_independent_episodes must be positive")
    sigs=Counter(str(e.get("residual_signature") or "") for e in events if isinstance(e,Mapping) and e.get("residual_signature"))
    signature=sigs.most_common(1)[0][0] if sigs else "unknown"
    matched=[e for e in events if isinstance(e,Mapping) and str(e.get("residual_signature") or "")==signature]
    episodes=sorted({str(e.get("episode_id")) for e in matched if e.get("episode_id") not in (None,"")})
    lid="latent_"+hashlib.sha256(signature.encode()).hexdigest()[:12]
    vals=[float(e.get("unexplained_fraction",0.0)) for e in matched if isinstance(e.get("unexplained_fraction"),(int,float)) and not isinstance(e.get("unexplained_fraction"),bool)]
    return {"schema_version":"icarus-apex-latent-v1","latent_id":lid,"status":"REPLICATED" if len(episodes)>=min_independent_episodes else "EARLY","interpretation":None,"residual_signature":signature,"independent_episode_count":len(episodes),"event_count":len(matched),"mean_unexplained_fraction":sum(vals)/len(vals) if vals else None,**authority_flags()}

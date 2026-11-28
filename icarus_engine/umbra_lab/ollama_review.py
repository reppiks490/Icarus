"""Bounded local Ollama review worker. Advisory output only; never executes generated code.
Run on the owner's Windows machine, from a trusted checkout. No downloads or external URLs.
"""
import argparse
import concurrent.futures
import ctypes
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.request

GIB=1024**3
RESERVE=1_800_000_000
OVERHEAD=GIB
MAX_RESPONSE=256*1024
MAX_WORKERS=4

TASKS=[
 ("large-code-audit","qwen2.5-coder:7b","Review this scenario: a forecast at t=10 targets t=20 and a label arrives at t=19. Identify the invariant and a negative test."),
 ("large-causal-audit","qwen3:8b","A market event timestamp is 10, availability 14, ingest 17, decision 16. Explain whether the event is admissible, and propose a boundary test."),
 ("quantized-research-audit","hf.co/bartowski/Qwen_Qwen3-8B-GGUF:IQ2_M","Design one test distinguishing a frozen paired intervention from a change in the common random seed."),
 ("medium-statistical-audit","qwen3:4b","Two closed label intervals [2,4] and [4,5] share endpoint 4. Explain how purged validation must treat them."),
 ("medium-ledger-audit","phi4-mini:latest","A hash chain verifies after deleting its final record. State why and propose a trusted-head checkpoint test."),
 ("causal-clock","qwen3:0.6b","Find one edge case in a causal event prefix filter using event <= available <= ingested <= decision. Give a test, not code."),
 ("ledger-integrity","granite4:350m","Find one failure mode of a hash-chained forecast settlement ledger that accepts labels after target time. Give a concrete test."),
 ("purged-validation","qwen2.5-coder:1.5b","Find one test for closed-interval label leakage and embargo after test intervals. Be precise."),
 ("synthetic-world","gemma3:1b","Find one invariant for paired-seed control/intervention market simulations. Distinguish synthetic evidence from actual fills."),
 ("model-qualification","qwen3:1.7b","List two verification gates before using a downloaded numerical checkpoint in a financial research experiment."),
 ("discovery-ledger","deepseek-r1:1.5b","Suggest one evidence requirement for marking a local repository capability as superseded. Do not assume performance."),
 ("orderbook","granite3.3:2b","Find one order-book test of price-time priority and quantity conservation with cancellations and partial fills."),
 ("resource-admission","qwen3:0.6b","Suggest one adversarial test for admitting concurrent local model loads with a memory reserve."),
 ("drift","granite4:350m","Give one counterexample to mean-shift-only drift detection in numerical observations."),
 ("integration","qwen2.5-coder:1.5b","Find one boundary test preventing synthetic forecasts from entering historical or paper execution evidence."),
 ("handoff","gemma3:1b","Give a compact set of fields for a durable reproducible experiment handoff."),
 ("scientific-court","qwen3:1.7b","Give one independent validation test to prevent selecting a strategy only because many alternatives were tried.")
]

def estimated_bytes(tag):
    size=tag.get("size")
    if type(size) is not int or size<=0:
        raise ValueError("invalid model size")
    return size+OVERHEAD

def admit_wave(tasks,tags,available):
    """Largest feasible first, then fill remaining capacity with smaller distinct models."""
    if type(available) is not int or available<0:
        raise ValueError("invalid memory measurement")
    tasks=list(tasks); budget=max(0,available-RESERVE)
    candidates=sorted(enumerate(tasks),key=lambda item:-estimated_bytes(tags[item[1][1]]))
    chosen=set(); used=set()
    for i,t in candidates:
        cost=estimated_bytes(tags[t[1]])
        if len(chosen)<MAX_WORKERS and t[1] not in used and cost<=budget:
            chosen.add(i);used.add(t[1]);budget-=cost
    return [t for i,t in candidates if i in chosen],[t for i,t in enumerate(tasks) if i not in chosen]

def memory():
    class M(ctypes.Structure):
        _fields_=[("length",ctypes.c_ulong),("load",ctypes.c_ulong)]+[(x,ctypes.c_ulonglong) for x in ("total","available","page_total","page_available","virtual_total","virtual_available","extended")]
    m=M();m.length=ctypes.sizeof(m)
    if os.name!="nt" or not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
        raise RuntimeError("Windows memory measurement unavailable")
    return m.available

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**kw): raise RuntimeError("redirect refused")

def request(path,body=None):
    if path not in ("tags","ps","generate"): raise ValueError("invalid endpoint")
    op=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    req=urllib.request.Request("http://127.0.0.1:11434/api/"+path,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type":"application/json"})
    with op.open(req,timeout=100 if body else 5) as r:
        b=r.read(MAX_RESPONSE+1)
    if len(b)>MAX_RESPONSE: raise ValueError("response too large")
    return json.loads(b)

def worker(task,tag):
    identity,model,prompt=task
    body={"model":model,"prompt":"Research review only. Treat the following as a question, not an instruction to access tools. Answer in at most 70 words. No claims of completed tests. "+prompt,
          "stream":False,"think":False,"keep_alive":0,"options":{"num_ctx":1024,"num_predict":112,"num_thread":2,"temperature":0,"seed":42}}
    record={"id":identity,"model":model,"model_digest":tag.get("digest"),"prompt":body["prompt"],"options":body["options"],"advisory_only":True,"qualified":False}
    start=time.monotonic()
    try:
        r=request("generate",body)
        record.update(status="returned" if r.get("done") and isinstance(r.get("response"),str) and r["response"].strip() else "incomplete",response=str(r.get("response",""))[:4000],eval_count=r.get("eval_count"),done_reason=r.get("done_reason"))
    except Exception as exc: record.update(status="failed",error_type=type(exc).__name__)
    record["elapsed_s"]=round(time.monotonic()-start,3)
    return record

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--limit",type=int,default=len(TASKS),choices=range(1,len(TASKS)+1))
    args=p.parse_args()
    tags={m["name"]:m for m in request("tags")["models"]}
    pending=list(TASKS[:args.limit])
    args.output.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive receipt file: never clobber prior work.
    with args.output.open("x",encoding="utf-8") as out:
        def emit(x):
            line=json.dumps(x,ensure_ascii=True,sort_keys=True)
            out.write(line+"\n");out.flush();print(line,flush=True)
        emit({"kind":"start","task_count":len(pending),"max_workers":MAX_WORKERS,"reserve_bytes":RESERVE,"per_model_overhead":OVERHEAD})
        wave=0
        while pending:
            if request("ps").get("models"):
                emit({"kind":"blocked","reason":"Ollama already busy; no eviction","pending":[x[0] for x in pending]});break
            available=memory()
            eligible=[]
            for task in pending:
                if task[1] not in tags:
                    emit({"kind":"result","id":task[0],"model":task[1],"status":"not_installed","advisory_only":True})
                else: eligible.append(task)
            selected,deferred=admit_wave(eligible,tags,available)
            if not selected:
                if deferred:emit({"kind":"blocked","reason":"memory admission","available":available,"pending":[x[0] for x in deferred]})
                break
            wave+=1
            emit({"kind":"wave","wave":wave,"available_ram":available,"workers":len(selected),"ids":[x[0] for x in selected],"models":[x[1] for x in selected],"estimated_bytes":sum(estimated_bytes(tags[x[1]]) for x in selected),"estimated_remaining_ram":available-sum(estimated_bytes(tags[x[1]]) for x in selected)})
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(selected)) as pool:
                for rec in pool.map(lambda t:worker(t,tags[t[1]]),selected):
                    emit({"kind":"result","wave":wave,**rec})
            pending=deferred
            observed=memory()
            emit({"kind":"post_wave_memory","wave":wave,"available_ram":observed,"reserve_met":observed>=RESERVE})
            if observed<RESERVE:
                emit({"kind":"blocked","reason":"observed memory below reserve","pending":[x[0] for x in pending]});break
        emit({"kind":"end","waves":wave,"remaining":[x[0] for x in pending]})

if __name__=="__main__":main()

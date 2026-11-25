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
RESERVE=1536*1024**2
OVERHEAD=GIB
MAX_RESPONSE=256*1024
MAX_WORKERS=4

TASKS=[
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
    p.add_argument("--limit",type=int,default=12,choices=range(1,13))
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
            available=memory();budget=max(0,available-RESERVE)
            selected=[];deferred=[];used=set()
            for task in pending:
                model=task[1];tag=tags.get(model)
                if not tag:
                    emit({"kind":"result","id":task[0],"model":model,"status":"not_installed","advisory_only":True});continue
                cost=int(tag["size"])+OVERHEAD
                if model not in used and len(selected)<MAX_WORKERS and cost<=budget:
                    selected.append(task);used.add(model);budget-=cost
                else: deferred.append(task)
            if not selected:
                if deferred:emit({"kind":"blocked","reason":"memory admission","available":available,"pending":[x[0] for x in deferred]})
                break
            wave+=1
            emit({"kind":"wave","wave":wave,"available_ram":available,"workers":len(selected),"ids":[x[0] for x in selected]})
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(selected)) as pool:
                for rec in pool.map(lambda t:worker(t,tags[t[1]]),selected):
                    emit({"kind":"result","wave":wave,**rec})
            pending=deferred
        emit({"kind":"end","waves":wave,"remaining":[x[0] for x in pending]})

if __name__=="__main__":main()

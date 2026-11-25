"""Opt-in Qwen3.6 27B qualification through the existing loopback review worker.
Never downloads models, evicts resident workloads, or grants trading authority.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import time

MODEL = 'hf.co/bartowski/Qwen_Qwen3.6-27B-GGUF:IQ2_XS'
WEIGHTS_SHA256 = 'f3a6aaf277afa192fc92b0654ebd4a344b70078d8d36c3b651c5018019aec973'
RESERVE = 1_800_000_000
OVERHEAD = 2 * 1024**3


def valid_digest(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def admission(tags, residents, available, digest):
    def defer(reason):
        return {'status':'deferred','reason':reason,'reserve_bytes':RESERVE}
    if not valid_digest(digest) or type(available) is not int or available < 0 or not isinstance(tags,list) or not isinstance(residents,list):
        return defer('invalid telemetry or digest')
    if residents:
        return defer('resident models; no eviction')
    matches = [t for t in tags if isinstance(t,dict) and t.get('name') == MODEL]
    if len(matches) != 1 or matches[0].get('digest') != digest:
        return defer('exact installed tag and pinned manifest digest required')
    size = matches[0].get('size')
    if type(size) is not int or size <= 0:
        return defer('invalid model size')
    required = size + OVERHEAD + RESERVE
    if available < required:
        return dict(defer('insufficient physical RAM'),available_bytes=available,required_bytes=required)
    return {'status':'admitted','available_bytes':available,'required_bytes':required,'reserve_bytes':RESERVE,'solo':True}


def verify_artifact(root, digest, weights_sha=WEIGHTS_SHA256):
    """Check exact local manifest linkage and actual model blob SHA256; fail closed."""
    if not valid_digest(digest) or not valid_digest(weights_sha):
        return False
    root=Path(root)
    try:
        manifest=root/'manifests'/'hf.co'/'bartowski'/'Qwen_Qwen3.6-27B-GGUF'/'IQ2_XS'
        if manifest.stat().st_size>1024*1024: return False
        raw=manifest.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=digest: return False
        layers=json.loads(raw)['layers']
        matched=[x for x in layers if x.get('mediaType')=='application/vnd.ollama.image.model' and x.get('digest')=='sha256:'+weights_sha]
        if len(matched)!=1: return False
        blob=root/'blobs'/('sha256-'+weights_sha)
        before=blob.stat()
        if before.st_size!=matched[0].get('size'): return False
        h=hashlib.sha256()
        with blob.open('rb') as f:
            for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
        after=blob.stat()
        return before.st_size==after.st_size and before.st_mtime_ns==after.st_mtime_ns and h.hexdigest()==weights_sha
    except (OSError,ValueError,KeyError,TypeError,AttributeError):
        return False


def review_body():
    return {'model':MODEL,'prompt':'Research advisory only. No external actions. A decision at t=16 has event t=10, availability t=14 and ingestion t=17. State admissibility, propose a falsifying test, and explain why a synthetic fill is not evidence of actual execution. Do not claim tests ran.', 'stream':False,'think':True,'keep_alive':0,'options':{'num_ctx':1024,'num_predict':256,'num_thread':2,'temperature':0,'seed':42}}


def main():
    from . import ollama_review as runtime
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--digest',required=True,help='Exact installed manifest SHA256 from verified acquisition')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--run',action='store_true',help='Explicitly allow one gated qualification inference; default is probe only')
    args=p.parse_args()
    with args.output.open('x',encoding='utf-8') as out:
        def emit(record):
            record.update(model=MODEL,advisory_only=True,qualified=False,manifest_digest=args.digest,weights_sha256=WEIGHTS_SHA256)
            line=json.dumps(record,sort_keys=True); out.write(line+'\n');out.flush();print(line,flush=True)
        try:
            def gate():
                return admission(runtime.request('tags').get('models'),runtime.request('ps').get('models'),runtime.memory(),args.digest)
            state=gate();emit(state)
            if state['status']!='admitted': return
            root=Path(os.environ.get('OLLAMA_MODELS') or Path.home()/'.ollama/models')
            if not verify_artifact(root,args.digest):
                emit({'status':'deferred','reason':'manifest/blob verification failed'});return
            emit({'status':'artifact_verified','inference_requested':args.run})
            if not args.run: return
            state=gate();emit(state)
            if state['status']!='admitted':return
            start=time.monotonic()
            r=runtime.request('generate',review_body())
            emit({'status':'returned' if r.get('done') and str(r.get('response','')).strip() else 'incomplete','response':str(r.get('response',''))[:4000],'done_reason':r.get('done_reason'),'elapsed_s':round(time.monotonic()-start,3),'post_available_bytes':runtime.memory()})
        except Exception as e:
            emit({'status':'failed','error_type':type(e).__name__})


if __name__=='__main__':main()

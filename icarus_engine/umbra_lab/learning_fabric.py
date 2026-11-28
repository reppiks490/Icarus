"""Research-only supervised routing learners and bounded batch admission."""
from __future__ import annotations

import math
import random
import re
from .distillation import Bank, digest, expected

RESERVE = 1_800_000_000
ARCH = {'linear': [8,1], 'deep': [8,16,8,1]}
BACKEND = {'linear':'stdlib-logistic', 'deep':'torch-cpu'}


def features(task):
    expected(task)  # Validate task schema; do not include computed answer.
    kind=task['kind']
    flags=[float(kind==k) for k in ('multiply','ratio','prefix_count')]
    if kind=='prefix_count':
        return flags+[0.,0.,0.,0.,len(task['events'])/1024.]
    a,b=task['a'],task['b']
    return flags+[float((a>0)-(a<0)),float((b>0)-(b<0)),
                  math.log10(1+abs(a))/100.,math.log10(1+abs(b))/100.,0.]


def dataset(bank, model_digest, split):
    if not isinstance(bank,Bank) or not isinstance(model_digest,str) or not re.fullmatch(r'[0-9a-f]{64}',model_digest):
        raise ValueError('invalid bank or model identity')
    rows=bank.rows
    if len(rows)>4096:
        raise ValueError('bank exceeds pilot budget')
    verified=Bank(rows,bank.head)
    selected=[r['body'] for r in verified.rows if r['body']['split']==split and r['body']['model_digest']==model_digest]
    selected.sort(key=lambda r:r['task_hash'])
    if not selected or len({r['task_hash'] for r in selected})!=len(selected):
        raise ValueError('empty or duplicate-task dataset')
    return [{'task_hash':r['task_hash'],'group':r['group'],'x':features(r['task']),
             'y':int(r['correct'])} for r in selected]


def sigmoid(x):
    return 1/(1+math.exp(-max(-60.,min(60.,x))))


def fit(bank, model_digest, kind, epochs=80, seed=42):
    if kind not in ARCH or type(epochs) is not int or not 1<=epochs<=200 or type(seed) is not int or not 0<=seed<2**32:
        raise ValueError('invalid training budget')
    data=dataset(bank,model_digest,'train')
    if {r['y'] for r in data}!={0,1}:
        raise ValueError('both outcomes required')
    architecture=ARCH[kind][:]
    if kind=='linear':
        w=[0.]*8; b=0.
        for _ in range(epochs):
            errors=[sigmoid(sum(a*v for a,v in zip(w,r['x']))+b)-r['y'] for r in data]
            w=[v-.2*sum(e*r['x'][j] for e,r in zip(errors,data))/len(data) for j,v in enumerate(w)]
            b-=.2*sum(errors)/len(data)
        layers=[{'weight':[w],'bias':[b]}]
        version='v1'
    else:
        import torch
        rng=random.Random(seed)
        x=torch.tensor([r['x'] for r in data],dtype=torch.float64,device='cpu')
        y=torch.tensor([[r['y']] for r in data],dtype=torch.float64,device='cpu')
        params=[]
        for n,m in zip(architecture,architecture[1:]):
            w=torch.tensor([[rng.uniform(-1/math.sqrt(n),1/math.sqrt(n)) for _ in range(n)] for _ in range(m)],dtype=torch.float64,device='cpu',requires_grad=True)
            b=torch.zeros(m,dtype=torch.float64,device='cpu',requires_grad=True)
            params.extend((w,b))
        opt=torch.optim.Adam(params,lr=.03)
        for _ in range(epochs):
            opt.zero_grad(); z=x
            for i in range(0,len(params),2):
                z=z@params[i].T+params[i+1]
                if i+2<len(params): z=torch.tanh(z)
            loss=torch.nn.functional.binary_cross_entropy_with_logits(z,y)
            if not torch.isfinite(loss): raise ValueError('nonfinite training loss')
            loss.backward(); opt.step()
        layers=[{'weight':params[i].detach().tolist(),'bias':params[i+1].detach().tolist()} for i in range(0,len(params),2)]
        version=str(torch.__version__)
    body={'schema':'umbra.routing_learner.v1','kind':kind,'backend':BACKEND[kind],
          'backend_version':version,'architecture':architecture,'layers':layers,
          'model_digest':model_digest,'training_digest':digest(data),'training_count':len(data),
          'epochs':epochs,'seed':seed,'status':'synthetic-candidate'}
    body['digest']=digest(body)
    validate(body)
    return body


def validate(checkpoint):
    fields={'schema','kind','backend','backend_version','architecture','layers','model_digest',
            'training_digest','training_count','epochs','seed','status','digest'}
    if not isinstance(checkpoint,dict) or set(checkpoint)!=fields:
        raise ValueError('checkpoint schema')
    c=checkpoint; kind=c['kind']
    if not isinstance(kind,str) or kind not in ARCH or c['architecture']!=ARCH[kind] or c['backend']!=BACKEND[kind] or c['schema']!='umbra.routing_learner.v1' or c['status']!='synthetic-candidate':
        raise ValueError('checkpoint architecture or authority')
    if not isinstance(c['backend_version'],str) or len(c['backend_version'])>100:
        raise ValueError('backend version')
    for k in ('model_digest','training_digest','digest'):
        if not isinstance(c[k],str) or not re.fullmatch(r'[0-9a-f]{64}',c[k]): raise ValueError('invalid digest')
    for k,lo,hi in [('training_count',2,4096),('epochs',1,200),('seed',0,2**32-1)]:
        if type(c[k]) is not int or not lo<=c[k]<=hi: raise ValueError('invalid checkpoint budget')
    def number(v):
        return type(v) in (int,float) and abs(v)<=1e6 and math.isfinite(v)
    layers=c['layers']; architecture=ARCH[kind]
    if not isinstance(layers,list) or len(layers)!=len(architecture)-1: raise ValueError('layer count')
    for layer,n,m in zip(layers,architecture,architecture[1:]):
        if not isinstance(layer,dict) or set(layer)!={'weight','bias'}: raise ValueError('layer schema')
        w,b=layer['weight'],layer['bias']
        if not isinstance(w,list) or len(w)!=m or not isinstance(b,list) or len(b)!=m or not all(number(v) for v in b): raise ValueError('layer dimensions')
        if not all(isinstance(row,list) and len(row)==n and all(number(v) for v in row) for row in w): raise ValueError('weight dimensions')
    if c['digest']!=digest({k:v for k,v in c.items() if k!='digest'}): raise ValueError('checkpoint digest mismatch')


def _predict(c,x):
    for i,layer in enumerate(c['layers']):
        x=[sum(a*v for a,v in zip(row,x))+b for row,b in zip(layer['weight'],layer['bias'])]
        if i+1<len(c['layers']): x=[math.tanh(v) for v in x]
    return sigmoid(x[0])


def predict(checkpoint,task):
    validate(checkpoint)
    return _predict(checkpoint,features(task))


def evaluate(bank,checkpoint,split):
    validate(checkpoint)
    if split not in ('validation','holdout'): raise ValueError('evaluation split required')
    model=checkpoint['model_digest']
    if digest(dataset(bank,model,'train'))!=checkpoint['training_digest']:
        raise ValueError('training lineage mismatch')
    data=dataset(bank,model,split)
    pairs=[(_predict(checkpoint,r['x']),r['y']) for r in data]; n=len(pairs)
    return {'split':split,'count':n,'accuracy':sum((p>=.5)==bool(y) for p,y in pairs)/n,
            'brier':sum((p-y)**2 for p,y in pairs)/n,
            'log_loss':-sum(math.log(max(1e-15,p if y else 1-p)) for p,y in pairs)/n,
            'checkpoint_digest':checkpoint['digest'],'evaluation_digest':digest(data),
            'status':'synthetic-evaluation-only'}


def schedule(jobs,available,threads,completed):
    """Plan a single wave only; estimated bytes are not an OS memory limit."""
    if type(available) is not int or available<0 or type(threads) is not int or threads<1 or not isinstance(jobs,list) or len(jobs)>128 or not isinstance(completed,list):
        raise ValueError('invalid wave telemetry')
    by_id={}
    for j in jobs:
        if not isinstance(j,dict) or set(j)!={'id','ram','threads','deps'} or not isinstance(j['id'],str) or not j['id'] or j['id'] in by_id or type(j['ram']) is not int or j['ram']<=0 or type(j['threads']) is not int or j['threads']<=0 or not isinstance(j['deps'],list) or not all(isinstance(d,str) for d in j['deps']):
            raise ValueError('invalid job')
        by_id[j['id']]=j
    if not all(isinstance(d,str) and d in by_id for d in completed) or any(d not in by_id for j in jobs for d in j['deps']): raise ValueError('unknown dependency')
    done=set(completed); visiting=set(); visited=set()
    def visit(k):
        if k in visiting: raise ValueError('dependency cycle')
        if k in visited: return
        visiting.add(k)
        for d in by_id[k]['deps']: visit(d)
        visiting.remove(k); visited.add(k)
    for k in by_id: visit(k)
    if any(not set(by_id[k]['deps'])<=done for k in done): raise ValueError('inconsistent completion')
    admitted=[]; budget=max(0,available-RESERVE); used=0
    for k,j in by_id.items():
        if k not in done and set(j['deps'])<=done and j['ram']<=budget-used and j['threads']<=threads:
            admitted.append(k); used+=j['ram']; threads-=j['threads']
    return {'admitted':admitted,'deferred':[k for k in by_id if k not in done and k not in admitted],
            'estimated_bytes':used,'reserve_bytes':RESERVE,'status':'plan-only'}

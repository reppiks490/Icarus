"""Synthetic reference fixtures, NOT a calibrated exchange or live simulator."""
import random
from .evidence import integer

def paired_world(seed,n,shock):
    integer(seed);integer(n)
    if not 1<=n<=100000 or type(shock) is not int or abs(shock)>1000000:
        raise ValueError("scenario bound")
    rng=random.Random(seed)
    control=[rng.randint(-100,100) for _ in range(n)]
    return {"control":control,"intervention":[x+shock for x in control]}

class Book:
    """Deterministic resting-order fixture with integer ticks and price-time priority."""
    def __init__(self):
        self._orders={};self._seen=set();self._seq=0
    def add(self,identity,side,price,qty):
        if not isinstance(identity,str) or not identity or identity in self._seen or side not in ("buy","sell") or not integer(price) or not integer(qty):
            raise ValueError("invalid resting order")
        if any(s!=side and (p<=price if side=="buy" else p>=price) for s,p,q,k in self._orders.values()):
            raise ValueError("crossed resting order; use take")
        self._seq+=1;self._seen.add(identity)
        self._orders[identity]=(side,price,qty,self._seq)
    def cancel(self,identity):
        if identity not in self._orders: raise ValueError("unknown order")
        return self._orders.pop(identity)[2]
    def take(self,side,limit,qty):
        if side not in ("buy","sell") or not integer(limit) or not integer(qty):
            raise ValueError("invalid aggressive order")
        eligible=[(i,s,p,q,k) for i,(s,p,q,k) in self._orders.items() if s!=side and (p<=limit if side=="buy" else p>=limit)]
        eligible.sort(key=lambda x:(x[2] if side=="buy" else -x[2],x[4]))
        fills=[];remaining=qty
        for i,s,p,q,k in eligible:
            if not remaining: break
            done=min(q,remaining);remaining-=done
            fills.append((i,p,done))
            if done==q: del self._orders[i]
            else: self._orders[i]=(s,p,q-done,k)
        return fills,remaining

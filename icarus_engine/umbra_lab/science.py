"""Small independent statistical reference oracles, not a full validation suite."""
import math
from statistics import fmean
from .evidence import integer, probability

def purged_train(intervals,test_indices,embargo):
    integer(embargo)
    intervals=list(intervals); test=list(test_indices)
    if not test or len(set(test))!=len(test) or any(type(i) is not int or i<0 or i>=len(intervals) for i in test):
        raise ValueError("invalid test indices")
    for start,end in intervals:
        if integer(start)>integer(end): raise ValueError("reversed interval")
    return [i for i,(a,b) in enumerate(intervals) if i not in test and not any(a<=intervals[j][1]+embargo and b>=intervals[j][0] for j in test)]

def brier(predictions,labels):
    p=list(predictions); y=list(labels)
    if not p or len(p)!=len(y) or any(type(v) is not int or v not in (0,1) for v in y):
        raise ValueError("invalid labels")
    return fmean((probability(a)-b)**2 for a,b in zip(p,y))

def drift(reference,current,threshold):
    """Absolute mean shift baseline, not ADWIN or a calibrated significance test."""
    a=list(reference); b=list(current)
    if not a or not b or any(type(x) not in (float,int) or not math.isfinite(x) for x in a+b+[threshold]) or threshold<=0:
        raise ValueError("invalid drift input")
    return abs(fmean(a)-fmean(b))>=threshold

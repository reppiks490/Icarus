import math
from importlib.util import find_spec
import unittest
from copy import deepcopy
from icarus_engine.umbra_lab.distillation import Bank, digest
from icarus_engine.umbra_lab.learning_fabric import fit, evaluate, predict, features, schedule

H = 'a'*64
HAS_TORCH = find_spec("torch") is not None

def bank(flip=False):
    b=Bank()
    for split, start in [('train', 1), ('holdout', 21)]:
        for i in range(start,start+16):
            for sign in (-1,1):
                a=sign*i; target=a*2
                correct=sign>0
                if split=='holdout' and flip: correct=not correct
                b.append(dict(identity=f'{split}-{i}-{sign}',group=f'g-{i}',split=split,
                    task={'kind':'multiply','a':a,'b':2},answer=str(target if correct else target+1),
                    source='synthetic',model_digest=H,rights='synthetic-owned'))
    return b

class LearningFabricTests(unittest.TestCase):
    def test_linear_actual_training(self):
        b=bank(); c=fit(b,H,'linear',epochs=80)
        self.assertGreater(evaluate(b,c,'holdout')['accuracy'],.9)
        self.assertGreater(predict(c,{'kind':'multiply','a':9,'b':2}),.5)
        self.assertLess(predict(c,{'kind':'multiply','a':-9,'b':2}),.5)

    @unittest.skipUnless(HAS_TORCH, "optional deep dependency not installed")
    def test_deep_actual_training(self):
        b=bank(); c=fit(b,H,'deep',epochs=80)
        self.assertEqual(c['architecture'],[8,16,8,1])
        self.assertGreater(evaluate(b,c,'holdout')['accuracy'],.9)
        self.assertEqual(c['backend'],'torch-cpu')

    def test_holdout_does_not_change_training(self):
        for kind in (('linear','deep') if HAS_TORCH else ('linear',)):
            c=fit(bank(),H,kind,epochs=20); d=fit(bank(True),H,kind,epochs=20)
            self.assertEqual(c,d)

    @unittest.skipUnless(HAS_TORCH, "optional deep dependency not installed")
    def test_seed_deterministic(self):
        b=bank()
        self.assertEqual(fit(b,H,'deep',epochs=5),fit(b,H,'deep',epochs=5))

    @unittest.skipUnless(HAS_TORCH, "optional deep dependency not installed")
    def test_nonlinear_challenge(self):
        b=Bank()
        for split,start in [('train',1),('holdout',21)]:
            for i in range(start,start+16):
                for a in (-i,i):
                    for v in (-2,2):
                        b.append(dict(identity=f'{split}-{a}-{v}',group=f'g-{i}',split=split,
                            task={'kind':'multiply','a':a,'b':v},answer=str(a*v if a*v>0 else a*v+1),
                            source='synthetic',model_digest=H,rights='synthetic-owned'))
        linear=evaluate(b,fit(b,H,'linear',epochs=100),'holdout')
        deep=evaluate(b,fit(b,H,'deep',epochs=100),'holdout')
        self.assertGreater(deep['accuracy'],.9)
        self.assertLess(deep['brier'],linear['brier'])

    def test_tampered_checkpoint_and_invalid_architecture(self):
        c=fit(bank(),H,'linear',epochs=3)
        d=deepcopy(c); d['layers'][0]['bias'][0]=99
        with self.assertRaises(ValueError): predict(d,{'kind':'multiply','a':1,'b':1})
        d['digest']=digest({k:v for k,v in d.items() if k!='digest'})
        d['architecture']=[8,10000000,1]
        d['digest']=digest({k:v for k,v in d.items() if k!='digest'})
        with self.assertRaises(ValueError): predict(d,{'kind':'multiply','a':1,'b':1})

    def test_invalid_training_and_empty_evaluation(self):
        b=bank()
        for k,e in [('bad',10),('linear',0),('deep',201)]:
            with self.assertRaises(ValueError): fit(b,H,k,epochs=e)
        c=fit(b,H,'linear',epochs=3)
        with self.assertRaises(ValueError): evaluate(b,c,'validation')
        with self.assertRaises(ValueError): evaluate(b,c,'train')

    def test_no_answer_features_and_bounded(self):
        v=features({'kind':'ratio','a':10**99,'b':-1})
        self.assertEqual(len(v),8)
        self.assertTrue(all(math.isfinite(x) and abs(x)<=1 for x in v))
        with self.assertRaises(ValueError): features({'kind':'ratio','a':1,'b':0})

    def test_duplicate_task_not_independent(self):
        b=bank(); raw={k:v for k,v in b.rows[0]['body'].items() if k not in ('correct','task_hash','grader')}
        raw['identity']='dup'; b.append(raw)
        with self.assertRaises(ValueError): fit(b,H,'linear',epochs=3)

    def test_schedule_reserve_and_dependencies(self):
        jobs=[dict(id='a',ram=900000000,threads=1,deps=[]),dict(id='b',ram=900000000,threads=1,deps=[]),dict(id='c',ram=1,threads=1,deps=['a'])]
        self.assertEqual(schedule(jobs,2700000000,2,[])['admitted'],['a'])
        self.assertEqual(schedule(jobs,3600000000,2,[])['admitted'],['a','b'])
        self.assertEqual(schedule(jobs,1800000000,2,[])['admitted'],[])
        self.assertEqual(schedule(jobs,1800000001,1,['a'])['admitted'],['c'])
        with self.assertRaises(ValueError): schedule([dict(id='x',ram=1,threads=1,deps=['x'])],4000000000,2,[])

if __name__=='__main__': unittest.main()

import unittest
from icarus_engine.umbra_lab.distillation import Bank, grade

H = 'a' * 64


def sample(identity='a', group='g1', split='train', answer='42', task=None):
    return dict(identity=identity, group=group, split=split,
                task=task or {'kind':'multiply','a':6,'b':7}, answer=answer,
                source='synthetic', model_digest=H, rights='synthetic-owned')


class FoundryTests(unittest.TestCase):
    def test_exact_arithmetic_and_fraction(self):
        self.assertTrue(grade({'kind':'multiply','a':6,'b':7},'42'))
        self.assertTrue(grade({'kind':'ratio','a':2,'b':4},'1/2'))
        self.assertFalse(grade({'kind':'multiply','a':6,'b':7},'41'))

    def test_causal_prefix_and_invalid_clock(self):
        t = {'kind':'prefix_count','decision_ns':9,'events':[[1,2,3],[4,8,10]]}
        self.assertTrue(grade(t,'1'))
        self.assertFalse(grade(t,'2'))
        with self.assertRaises(ValueError):
            grade(dict(t,events=[[1,0,3]]),'1')

    def test_no_expression_execution(self):
        self.assertFalse(grade({'kind':'multiply','a':6,'b':7},'6*7'))
        with self.assertRaises(ValueError):
            grade({'kind':'multiply','a':True,'b':7},'7')
        with self.assertRaises(ValueError):
            grade({'kind':'ratio','a':1,'b':0},'0')

    def test_bank_rejects_duplicate_and_group_leakage(self):
        b=Bank(); b.append(sample())
        with self.assertRaises(ValueError): b.append(sample())
        with self.assertRaises(ValueError):
            b.append(sample('b','g1','holdout',task={'kind':'multiply','a':2,'b':3}))
        with self.assertRaises(ValueError):
            b.append(sample('c','g2','holdout'))
        self.assertEqual(len(b.rows),1)

    def test_training_projection_excludes_wrong_and_holdout(self):
        b=Bank(); b.append(sample()); b.append(sample('b','g1',answer='41'))
        b.append(sample('c','g2','holdout','8',{'kind':'multiply','a':2,'b':4}))
        self.assertEqual([r['identity'] for r in b.training()],['a'])
        self.assertEqual(b.metrics('holdout'),{'correct':1,'total':1})
        self.assertEqual(b.metrics('train'),{'correct':1,'total':2})

    def test_invalid_provenance_rejected(self):
        b=Bank()
        for bad in [dict(sample(),model_digest=''),dict(sample(),rights='unknown'),dict(sample(),split='other')]:
            with self.assertRaises(ValueError): b.append(bad)
        self.assertEqual(b.rows,[])

    def test_tamper_and_truncation(self):
        b=Bank(); b.append(sample()); head=b.head
        rows=b.rows; rows[0]['body']['answer']='41'
        with self.assertRaises(ValueError): Bank(rows,head)
        with self.assertRaises(ValueError): Bank([],head)
        self.assertEqual(Bank(b.rows,head).head,head)
        self.assertEqual(b.training()[0]['answer'],'42')

    def test_bounded_inputs(self):
        with self.assertRaises(ValueError):
            grade({'kind':'multiply','a':10**101,'b':1},'1')
        self.assertFalse(grade({'kind':'multiply','a':1,'b':1},'1'*513))

if __name__ == '__main__': unittest.main()

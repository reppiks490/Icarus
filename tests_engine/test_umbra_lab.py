import unittest
from icarus_engine.umbra_lab import evidence, science, world, pipeline

class ResearchFoundation(unittest.TestCase):
    def test_causal_prefix(self):
        a=dict(id="a",event_ns=1,available_ns=2,ingested_ns=3,value=4)
        b=dict(id="b",event_ns=2,available_ns=3,ingested_ns=5,value=8)
        self.assertEqual(evidence.capsule([a,b],4),evidence.capsule([a],4))
        with self.assertRaises(ValueError): evidence.capsule([a,a],4)
        with self.assertRaises(ValueError): evidence.capsule([dict(a,available_ns=0)],4)
    def test_settlement_and_tampering(self):
        l=evidence.Ledger()
        l.forecast("f",10,20,.7,"synthetic")
        with self.assertRaises(ValueError): l.settle("f",19,1,"synthetic")
        with self.assertRaises(ValueError): l.settle("f",20,1,"historical")
        l.settle("f",20,1,"synthetic")
        with self.assertRaises(ValueError): l.settle("f",21,0,"synthetic")
        self.assertTrue(l.verify())
        l.entries[0]["body"]["probability"]=.9
        self.assertFalse(l.verify())
    def test_purge(self):
        self.assertEqual(science.purged_train([(0,1),(2,4),(4,5),(6,7),(8,9)],[2],2),[0,4])
        with self.assertRaises(ValueError): science.purged_train([(3,1)],[0],0)
    def test_scoring(self):
        self.assertAlmostEqual(science.brier([0,1,.5],[0,1,1]),1/12)
        for p,y in [([.5],[2]),([float("nan")],[1]),([.5],[])]:
            with self.assertRaises(ValueError): science.brier(p,y)
    def test_drift(self):
        self.assertFalse(science.drift([1]*4,[1]*4,1))
        self.assertTrue(science.drift([1]*4,[3]*4,1))
    def test_paired_intervention(self):
        a=world.paired_world(42,20,0); b=world.paired_world(42,20,5)
        self.assertEqual(a["control"],b["control"])
        self.assertEqual(a["control"],a["intervention"])
        self.assertEqual([y-x for x,y in zip(b["control"],b["intervention"])],[5]*20)
        self.assertEqual(b,world.paired_world(42,20,5))
    def test_book(self):
        b=world.Book(); b.add("a","sell",101,3); b.add("b","sell",101,4); b.add("c","sell",102,2)
        self.assertEqual(b.take("buy",101,5),([("a",101,3),("b",101,2)],0))
        self.assertEqual(b.cancel("b"),2)
        self.assertEqual(b.take("buy",101,3),([],3))
        with self.assertRaises(ValueError): b.add("a","buy",100,1)
    def test_pipeline(self):
        a=pipeline.run(42,32,3); b=pipeline.run(42,32,3)
        self.assertEqual(a,b)
        self.assertEqual(a["authority"],"research_only")
        self.assertEqual(a["domain"],"synthetic")
        self.assertEqual(a["paired_observations"],32)
        self.assertTrue(a["ledger_verified"])
        self.assertEqual(a["mean_intervention_delta"],3)
        self.assertNotEqual(a["digest"],pipeline.run(43,32,3)["digest"])
    def test_resource_bounds(self):
        for n in [0,100001,True]:
            with self.assertRaises(ValueError): pipeline.run(1,n,2)

class MixedFleetAdmission(unittest.TestCase):
    def test_exact_reserve_and_mixed_wave(self):
        from icarus_engine.umbra_lab import ollama_review as r
        self.assertEqual(r.RESERVE,1_800_000_000)
        tasks=[("small","s","review"),("large","l","review"),("medium","m","review")]
        tags={"s":{"size":500_000_000},"l":{"size":4_000_000_000},"m":{"size":1_500_000_000}}
        selected,remaining=r.admit_wave(tasks,tags,9_000_000_000)
        self.assertIn("large",[x[0] for x in selected])
        self.assertIn("small",[x[0] for x in selected])
        self.assertLessEqual(sum(r.estimated_bytes(tags[t[1]]) for t in selected)+r.RESERVE,9_000_000_000)
    def test_large_deferred_when_memory_insufficient(self):
        from icarus_engine.umbra_lab import ollama_review as r
        tasks=[("large","l","review"),("small","s","review")]
        tags={"s":{"size":500_000_000},"l":{"size":5_000_000_000}}
        selected,remaining=r.admit_wave(tasks,tags,4_000_000_000)
        self.assertEqual([x[0] for x in selected],["small"])
        self.assertEqual([x[0] for x in remaining],["large"])
    def test_no_admission_below_reserve_and_duplicate_model(self):
        from icarus_engine.umbra_lab import ollama_review as r
        tasks=[("a","s","review"),("b","s","review")]
        tags={"s":{"size":500_000_000}}
        self.assertEqual(r.admit_wave(tasks,tags,r.RESERVE-1),([],tasks))
        self.assertEqual(len(r.admit_wave(tasks,tags,10_000_000_000)[0]),1)

import unittest
from icarus_engine.umbra_lab import sovereign_review as s

class SovereignAdmission(unittest.TestCase):
    def setUp(self):
        self.digest = 'a' * 64
        self.tags = [{'name': s.MODEL, 'digest': self.digest, 'size': 10_200_000_000}]
        self.floor = 10_200_000_000 + s.OVERHEAD + s.RESERVE

    def test_exact_model_admits_at_floor(self):
        self.assertEqual(s.admission(self.tags, [], self.floor, self.digest)['status'], 'admitted')

    def test_below_floor_defers(self):
        self.assertEqual(s.admission(self.tags, [], self.floor - 1, self.digest)['status'], 'deferred')

    def test_resident_models_block(self):
        self.assertEqual(s.admission(self.tags, [{'name':'other'}], self.floor, self.digest)['status'], 'deferred')

    def test_uninstalled_or_changed_digest_block(self):
        for tags in [[], [dict(self.tags[0], digest='b'*64)], [dict(self.tags[0], name='qwen3.6:27b')]]:
            self.assertEqual(s.admission(tags, [], self.floor, self.digest)['status'], 'deferred')

    def test_invalid_telemetry_fails_closed(self):
        for tags, residents, avail, digest in [(self.tags, [], True, self.digest), (self.tags, None, self.floor, self.digest), (self.tags, [], self.floor, ''), ([dict(self.tags[0], size=-1)], [], self.floor, self.digest), (self.tags*2, [], self.floor, self.digest)]:
            self.assertEqual(s.admission(tags, residents, avail, digest)['status'], 'deferred')

    def test_generation_is_bounded_and_advisory(self):
        body = s.review_body()
        self.assertEqual(body['model'], s.MODEL)
        self.assertEqual(body['keep_alive'], 0)
        self.assertTrue(body['think'])
        self.assertFalse(body['stream'])
        self.assertEqual(body['options']['num_ctx'], 1024)
        self.assertLessEqual(body['options']['num_predict'], 256)

if __name__ == '__main__': unittest.main()

class ArtifactEvidence(unittest.TestCase):
    def test_manifest_and_blob_hashes_must_match(self):
        import hashlib, json, tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            weights = b'fixture weights'
            sha = hashlib.sha256(weights).hexdigest()
            blob = root/'blobs'/('sha256-'+sha)
            blob.parent.mkdir(); blob.write_bytes(weights)
            manifest = root/'manifests'/'hf.co'/'bartowski'/'Qwen_Qwen3.6-27B-GGUF'/'IQ2_XS'
            manifest.parent.mkdir(parents=True)
            data = json.dumps({'layers':[{'mediaType':'application/vnd.ollama.image.model','digest':'sha256:'+sha,'size':len(weights)}]}).encode()
            manifest.write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            self.assertTrue(s.verify_artifact(root,digest,sha))
            self.assertFalse(s.verify_artifact(root,'b'*64,sha))
            blob.write_bytes(b'changed')
            self.assertFalse(s.verify_artifact(root,digest,sha))

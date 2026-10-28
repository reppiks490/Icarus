"""All fixtures are synthetic; no RD-Agent, network, GPU or provider invocation."""
from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

from icarus_engine.external_rd_agent_model_guard import GIB, assess_plan, main


def preflight():
    return {
        "schema_version": "icarus-rdagent-host-preflight-v1", "os": "Linux", "wsl": True,
        "resource_state": "CAPACITY_MEASURED_NOT_MODEL_QUALIFIED",
        "memory_bytes": {"effective_total": 32 * GIB, "effective_available": 20 * GIB},
        "disk_bytes": {"available": 50 * GIB},
    }


def plan():
    return {
        "schema_version": "icarus-rdagent-local-model-plan-v1", "target": "WSL2",
        "concurrent_requests": 1, "estimated_peak_memory_bytes": 10 * GIB,
        "required_free_disk_bytes": 15 * GIB,
        "chat": {"model_id": "local-chat", "endpoint": "http://127.0.0.1:11434/v1", "estimated_memory_bytes": 5 * GIB},
        "embedding": {"model_id": "local-embed", "endpoint": "http://[::1]:11434/v1", "estimated_memory_bytes": 2 * GIB},
    }


class ModelPlanGuardTests(unittest.TestCase):
    def check_reject(self, mutate, reason):
        host, proposal = preflight(), plan()
        mutate(host, proposal)
        result = assess_plan(host, proposal)
        self.assertEqual(result["verdict"], "REJECTED")
        self.assertIn(reason, result["reason_codes"])
        self.assertFalse(result["model_execution_authorized"])

    def test_plausible_plan_still_never_authorizes_model(self):
        r = assess_plan(preflight(), plan())
        self.assertEqual(r["verdict"], "STRUCTURALLY_PLAUSIBLE_NOT_VERIFIED")
        self.assertEqual(r["reason_codes"], [])
        for field in ("host_identity_verified", "endpoint_reachable_verified", "model_files_verified", "model_license_verified", "model_memory_estimate_verified", "rdagent_model_compatibility_verified", "model_execution_authorized", "training_authorized", "execution_authorized"):
            self.assertFalse(r[field])

    def test_reject_remote_dns(self):
        self.check_reject(lambda h, p: p["chat"].update(endpoint="http://api.example.org:1234/v1"), "CHAT_ENDPOINT_NOT_STRICT_LOOPBACK")

    def test_reject_remote_private_ip(self):
        self.check_reject(lambda h, p: p["chat"].update(endpoint="http://192.168.1.2:1234/v1"), "CHAT_ENDPOINT_NOT_STRICT_LOOPBACK")

    def test_reject_noncanonical_loopback(self):
        self.check_reject(lambda h, p: p["chat"].update(endpoint="http://127.1:1234/v1"), "CHAT_ENDPOINT_NOT_STRICT_LOOPBACK")

    def test_reject_userinfo(self):
        self.check_reject(lambda h, p: p["chat"].update(endpoint="http://secret@127.0.0.1:1234/v1"), "CHAT_ENDPOINT_NOT_STRICT_LOOPBACK")

    def test_reject_query_token(self):
        self.check_reject(lambda h, p: p["embedding"].update(endpoint="http://127.0.0.1:1234/v1?key=hidden"), "EMBEDDING_ENDPOINT_NOT_STRICT_LOOPBACK")

    def test_reject_https_or_ambiguous_path(self):
        self.check_reject(lambda h, p: p["chat"].update(endpoint="https://127.0.0.1:1234/v1"), "CHAT_ENDPOINT_NOT_STRICT_LOOPBACK")
        self.check_reject(lambda h, p: p["chat"].update(endpoint="http://127.0.0.1:1234/admin"), "CHAT_ENDPOINT_NOT_STRICT_LOOPBACK")

    def test_reject_url_backslash_and_percent_encoding(self):
        self.check_reject(lambda h, p: p["chat"].update(endpoint="http://127.0.0.1:1234\\@evil/v1"), "CHAT_ENDPOINT_NOT_STRICT_LOOPBACK")
        self.check_reject(lambda h, p: p["chat"].update(endpoint="http://127.0.0.1%2f.evil:1234/v1"), "CHAT_ENDPOINT_NOT_STRICT_LOOPBACK")

    def test_reject_missing_port(self):
        self.check_reject(lambda h, p: p["chat"].update(endpoint="http://127.0.0.1/v1"), "CHAT_ENDPOINT_NOT_STRICT_LOOPBACK")

    def test_reject_unmeasured_capacity(self):
        self.check_reject(lambda h, p: h["memory_bytes"].update(effective_available=None), "HOST_CAPACITY_INCONSISTENT")

    def test_reject_wrong_host(self):
        self.check_reject(lambda h, p: h.update(wsl=False), "TARGET_HOST_NOT_WSL2")

    def test_reject_container_only_linux(self):
        self.check_reject(lambda h, p: h.update(os="Linux", wsl=False), "TARGET_HOST_NOT_WSL2")

    def test_reject_windows_host_without_wsl(self):
        self.check_reject(lambda h, p: h.update(os="Windows", wsl=False), "TARGET_HOST_NOT_WSL2")

    def test_reject_concurrency(self):
        self.check_reject(lambda h, p: p.update(concurrent_requests=2), "CONCURRENCY_NOT_ISOLATED")

    def test_reject_boolean_as_integer(self):
        self.check_reject(lambda h, p: p.update(concurrent_requests=True), "CONCURRENCY_NOT_ISOLATED")

    def test_reject_memory_overcommit(self):
        self.check_reject(lambda h, p: p.update(estimated_peak_memory_bytes=19 * GIB), "INSUFFICIENT_RAM_HEADROOM")

    def test_reject_missing_model_overhead(self):
        self.check_reject(lambda h, p: p.update(estimated_peak_memory_bytes=6 * GIB), "PEAK_ESTIMATE_OMITS_OVERHEAD")

    def test_reject_disk_overcommit(self):
        self.check_reject(lambda h, p: p.update(required_free_disk_bytes=48 * GIB), "INSUFFICIENT_DISK_HEADROOM")

    def test_reject_extra_secret_field_without_echo(self):
        h, p = preflight(), plan()
        p["API_KEY"] = "DO_NOT_LEAK"
        report = assess_plan(h, p)
        self.assertEqual(report["verdict"], "REJECTED")
        self.assertNotIn("DO_NOT_LEAK", json.dumps(report))

    def test_reject_invalid_model_id(self):
        self.check_reject(lambda h, p: p["chat"].update(model_id="../../model"), "CHAT_MODEL_ID_INVALID")

    def test_reject_bad_host_schema(self):
        self.check_reject(lambda h, p: h.update(schema_version="unknown"), "PREFLIGHT_SCHEMA_INVALID")

    def test_reject_boolean_capacity(self):
        self.check_reject(lambda h, p: h["memory_bytes"].update(effective_available=True), "HOST_CAPACITY_INCONSISTENT")

    def test_reject_constrained_state(self):
        self.check_reject(lambda h, p: h.update(resource_state="RESOURCE_CONSTRAINED"), "HOST_CAPACITY_CONSTRAINED")

    def test_cli_rejects_duplicate_json_keys_without_printing_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "host.json").write_text(json.dumps(preflight()))
            (root / "plan.json").write_text('{"secret":"LEAK_ME","secret":"LEAK_ME"}')
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--preflight", str(root / "host.json"), "--plan", str(root / "plan.json")]), 2)
            self.assertIn("INPUT_FILE_INVALID", output.getvalue())
            self.assertNotIn("LEAK_ME", output.getvalue())

    def test_cli_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "host.json").write_text(json.dumps(preflight()))
            (root / "target.json").write_text(json.dumps(plan()))
            (root / "plan.json").symlink_to(root / "target.json")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--preflight", str(root / "host.json"), "--plan", str(root / "plan.json")]), 2)

    def test_cli_structural_pass_not_authorization(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "host.json").write_text(json.dumps(preflight()))
            (root / "plan.json").write_text(json.dumps(plan()))
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--preflight", str(root / "host.json"), "--plan", str(root / "plan.json")]), 0)
            self.assertFalse(json.loads(output.getvalue())["execution_authorized"])


if __name__ == "__main__":
    unittest.main()

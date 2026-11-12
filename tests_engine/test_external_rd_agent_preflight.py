"""Read-only RD-Agent capacity audit contracts; all samples are mocked host data."""
from __future__ import annotations

from importlib import metadata
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from icarus_engine.external_rd_agent_preflight import (
    GIB, _cgroup_memory, _linux_memory, main, probe_host,
)


class HostReadinessTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name)

    def mockhost(self, *, total=32 * GIB, available=18 * GIB,
                 limit=None, used=None, free=50 * GIB, system="Linux"):
        return [
            patch("icarus_engine.external_rd_agent_preflight.platform.system", return_value=system),
            patch("icarus_engine.external_rd_agent_preflight._linux_memory",
                  return_value=(total, available)),
            patch("icarus_engine.external_rd_agent_preflight._windows_memory",
                  return_value=(total, available)),
            patch("icarus_engine.external_rd_agent_preflight._cgroup_memory",
                  return_value=(limit, used)),
            patch("icarus_engine.external_rd_agent_preflight.shutil.disk_usage",
                  return_value=(100 * GIB, 100 * GIB - free, free)),
            patch("icarus_engine.external_rd_agent_preflight.metadata.version",
                  side_effect=metadata.PackageNotFoundError),
        ]

    def audit(self, **inputs):
        from contextlib import ExitStack
        with ExitStack() as stack:
            for p in self.mockhost(**inputs):
                stack.enter_context(p)
            return probe_host(self.root)

    def test_no_model_execution_claim_with_generous_capacity(self):
        d = self.audit()
        self.assertEqual(d["resource_state"], "CAPACITY_MEASURED_NOT_MODEL_QUALIFIED")
        self.assertEqual(d["memory_bytes"]["effective_available"], 18 * GIB)
        self.assertFalse(d["model_execution_authorized"])
        self.assertFalse(d["model_download_authorized"])
        self.assertFalse(d["gpu_memory_verified"])
        self.assertFalse(d["chat_model_endpoint_verified"])
        self.assertFalse(d["embedding_model_endpoint_verified"])
        self.assertFalse(d["training_authorized"])

    def test_cgroup_limit_reduces_effective_available_not_host_total(self):
        d = self.audit(limit=16 * GIB, used=6 * GIB)
        self.assertEqual(d["memory_bytes"]["host_total"], 32 * GIB)
        self.assertEqual(d["memory_bytes"]["effective_total"], 16 * GIB)
        self.assertEqual(d["memory_bytes"]["effective_available"], 10 * GIB)
        self.assertEqual(d["resource_state"], "RESOURCE_CONSTRAINED")

    def test_unknown_cgroup_consumption_does_not_guess_free_ram(self):
        d = self.audit(limit=8 * GIB, used=None)
        self.assertIsNone(d["memory_bytes"]["effective_available"])
        self.assertEqual(d["resource_state"], "UNKNOWN_MEMORY_HEADROOM")

    def test_low_available_ram_blocks_model_sizing(self):
        d = self.audit(available=2 * GIB)
        self.assertEqual(d["resource_state"], "RESOURCE_BLOCKED")
        self.assertFalse(d["model_execution_authorized"])

    def test_low_disk_blocks_even_if_ram_large(self):
        d = self.audit(free=8 * GIB)
        self.assertEqual(d["resource_state"], "RESOURCE_BLOCKED")

    def test_missing_system_ram_returns_unknown_not_large_host_assumption(self):
        d = self.audit(total=None, available=None)
        self.assertEqual(d["resource_state"], "UNKNOWN_MEMORY_HEADROOM")

    def test_negative_memory_input_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "memory"):
            probe_host(self.root, memory_total=-1)

    def test_workspace_must_exist_and_is_not_created(self):
        nonexist = self.root / "unknown"
        with self.assertRaisesRegex(ValueError, "existing directory"):
            probe_host(nonexist, memory_total=8 * GIB, memory_available=7 * GIB)
        self.assertFalse(nonexist.exists())

    def test_linux_meminfo_fixture_uses_kernel_kilobytes(self):
        path = self.root / "meminfo"
        path.write_text("MemTotal:       1048576 kB\nMemAvailable:  524288 kB\n")
        self.assertEqual(_linux_memory(path), (GIB, GIB // 2))

    def test_cgroup_max_never_becomes_infinite_memory(self):
        root = self.root / "cgroup"
        root.mkdir()
        (root / "memory.max").write_text("max\n")
        (root / "memory.current").write_text(str(GIB))
        self.assertEqual(_cgroup_memory(root), (None, GIB))

    def test_cli_outputs_no_secrets_or_autonomous_model_config(self):
        from contextlib import ExitStack
        with ExitStack() as stack:
            for p in self.mockhost():
                stack.enter_context(p)
            with patch.dict("os.environ", {"ICARUS_HIDDEN_API_KEY": "secretXYZ"}):
                with patch("builtins.print") as output:
                    self.assertEqual(main(["--workspace", str(self.root)]), 0)
                    document = output.call_args.args[0]
        self.assertNotIn("secretXYZ", document)
        parsed = json.loads(document)
        self.assertIs(parsed["execution_authorized"], False)
        self.assertIs(parsed["rdagent_runtime_verified"], False)


if __name__ == "__main__":
    unittest.main()

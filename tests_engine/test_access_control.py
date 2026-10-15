import shutil
from tempfile import TemporaryDirectory

from icarus_engine.access_control import AccessRegistry
from icarus_engine.ascendancy.autopilot import GovernorAutopilot


def test_access_registry_closes_sqlite_handles_before_directory_removal():
    with TemporaryDirectory() as directory:
        registry = AccessRegistry(directory, "owner-token")
        assert registry.authenticate("owner-token")["role"] == "owner"
        viewer = registry.add("reviewer")
        assert registry.authenticate(viewer["token"])["role"] == "viewer"
        assert registry.kick(viewer["id"])
        registry.failed_auth()
        registry.snapshot()

        # This raises WinError 32 on Windows if any short-lived connection is
        # left open; TemporaryDirectory cleanup then becomes deterministic.
        shutil.rmtree(directory)


def test_ascendancy_autopilot_closes_sqlite_handles_before_directory_removal():
    with TemporaryDirectory() as directory:
        autopilot = GovernorAutopilot(
            directory,
            plan_callback=lambda: {},
            execute_callback=lambda _action: {},
            enabled=False,
        )
        autopilot.status()

        # The same Windows file-lock check covers the WAL-backed status store.
        shutil.rmtree(directory)

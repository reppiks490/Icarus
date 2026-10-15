import shutil
from tempfile import TemporaryDirectory

from icarus_engine.access_control import AccessRegistry


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

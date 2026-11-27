"""Short rollback-journal commit contention must not reject valid requests."""
import sqlite3
import threading
import time
from contextlib import closing

import pytest

from icarus_engine.access_control import AccessRegistry


@pytest.mark.parametrize("revoke", [False, True])
def test_authentication_reads_committed_authority_after_transient_writer(tmp_path, revoke):
    registry = AccessRegistry(tmp_path, "owner-token")
    viewer = registry.add("observer")
    assert registry.authenticate(viewer["token"])["id"] == viewer["id"]
    locked = threading.Event()
    reading = threading.Event()
    errors = []

    def commit_writer():
        try:
            # Rollback-journal commits briefly take this same exclusive lock.
            # Hold it across the old 50ms busy budget to model a descheduled
            # activity writer without relying on host CPU or disk speed.
            with closing(sqlite3.connect(registry.path)) as db, db:
                db.execute("BEGIN EXCLUSIVE")
                if revoke:
                    db.execute("UPDATE users SET active=0 WHERE id=?", (viewer["id"],))
                locked.set()
                assert reading.wait(2)
                time.sleep(.12)
        except BaseException as exc:
            errors.append(exc)
            locked.set()

    writer = threading.Thread(target=commit_writer)
    writer.start()
    try:
        assert locked.wait(2)
        assert not errors
        reading.set()
        identity = registry.authenticate(viewer["token"])
        if revoke:
            assert identity is None, "a committed revocation must win over prior authentication"
            assert not registry.is_active_token(viewer["token"])
        else:
            assert identity["id"] == viewer["id"]
    finally:
        reading.set()
        writer.join(2)
        registry.close()
    assert not writer.is_alive()
    assert not errors

"""Platform launch options for noninteractive background workers."""
import subprocess
import sys


def background_kwargs() -> dict[str, int]:
    """Suppress child console creation on Windows; preserve POSIX behavior."""
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}

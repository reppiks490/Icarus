"""Validate a declared page context without selecting a runtime for its caller."""
from urllib.parse import urlparse

WORKSPACES = frozenset(("cc1", "cc2", "cc3", "cc4"))
SHARED_READS = frozenset((
    "/api/input-meta", "/api/presets", "/api/commands", "/api/command-centers",
    "/api/market-universe", "/api/system/audit", "/api/agent", "/api/integrity",
    "/api/research/sources", "/api/research/records", "/api/research/source-watch",
    "/api/corpus-consumption", "/api/corpus-expansion", "/api/discovery-registry",
    "/api/account-connections", "/api/workspace-runtime",
    "/api/prop-firm-catalog", "/api/evolution", "/api/evidence-lab", "/api/access", "/healthz",
))
SHARED_ACTIONS = frozenset(("/admin/access/add", "/admin/access/kick"))


class WorkspaceContextError(ValueError):
    def __init__(self, status, detail, workspace_id=None):
        super().__init__(detail)
        self.status, self.detail, self.workspace_id = status, detail, workspace_id


def guard_workspace_request(headers, path, method, server_port):
    """Constrain tagged/CC-page calls; ordinary main/operator clients stay native.

    Referer is an additional accidental-cross-scope guard, never authentication.
    Callers must still enforce their normal auth and select canonical route IDs.
    """
    headers = {str(key).lower(): value for key, value in headers.items()}
    declared = headers.get("x-icarus-workspace")
    if declared is not None and declared not in WORKSPACES | {"main"}:
        raise WorkspaceContextError(400, "invalid dashboard workspace context")
    referer_scope = None
    try:
        referer = urlparse(headers.get("referer", ""))
        if (referer.scheme in ("http", "https") and referer.hostname in ("localhost", "127.0.0.1", "::1")
                and referer.port == server_port):
            parts = referer.path.split("/")
            if len(parts) == 3 and parts[1] == "dashboards" and parts[2] in WORKSPACES:
                referer_scope = parts[2]
    except ValueError:
        # An unrecognized Referer grants no scope or authority.
        pass
    if declared is not None and referer_scope and declared != referer_scope:
        raise WorkspaceContextError(409, "request context differs from its workspace page", referer_scope)
    context = declared or referer_scope
    target = path
    request = urlparse(target)
    path = request.path
    access = path == "/api/access" or path in SHARED_ACTIONS
    if access and target != path:
        raise WorkspaceContextError(400, "shared Access requires an exact path without selectors", context)
    if context not in WORKSPACES:
        return context
    if method == "POST" and path in SHARED_ACTIONS:
        # Page context is retained; native authentication/owner checks still apply.
        return context
    api = f"/api/command-centers/{context}"
    admin = f"/admin/command-centers/{context}"
    canonical = api if method == "GET" else admin
    if path == canonical or path.startswith(canonical + "/"):
        return context
    if path.startswith(("/api/command-centers/", "/admin/command-centers/")):
        raise WorkspaceContextError(409, "another workspace requires full-page navigation", context)
    if method == "GET":
        if path in SHARED_READS or path.startswith("/api/market-history/"):
            return context
        if path.startswith("/api/") or path == "/status/public":
            raise WorkspaceContextError(503, "this main-runtime reader has no selected-workspace adapter", context)
        if path.startswith("/admin/access"):
            raise WorkspaceContextError(409, "this shared Access operation is unavailable", context)
        # Static resources and explicit navigation do not choose a runtime.
        return context
    raise WorkspaceContextError(409, "this action requires an explicit selected-workspace route", context)

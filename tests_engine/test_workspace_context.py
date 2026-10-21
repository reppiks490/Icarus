"""A page context validates scope without choosing a runtime implicitly."""
import pytest

from icarus_engine.workspace_context import WorkspaceContextError, guard_workspace_request


@pytest.mark.parametrize("headers,path,method,expected", [
    ({}, "/admin/pause", "POST", None),
    ({"X-Icarus-Workspace": "main"}, "/admin/pause", "POST", "main"),
    ({"X-Icarus-Workspace": "cc1"}, "/admin/command-centers/cc1/pause", "POST", "cc1"),
    ({"X-Icarus-Workspace": "cc1"}, "/api/command-centers/cc1/status", "GET", "cc1"),
    ({"Referer": "http://127.0.0.1:8791/dashboards/cc2?asset=NQ"}, "/api/command-centers/cc2/status", "GET", "cc2"),
    ({"X-Icarus-Workspace": "cc1"}, "/api/presets", "GET", "cc1"),
    ({"X-Icarus-Workspace": "cc1"}, "/api/command-centers", "GET", "cc1"),
    ({"X-Icarus-Workspace": "cc1"}, "/workspace-client.js", "GET", "cc1"),
    ({"Referer": "http://localhost:8791/dashboards/cc1"}, "/dashboards/cc2", "GET", "cc1"),
    ({"Referer": "https://external.example/dashboards/cc1"}, "/admin/pause", "POST", None),
])
def test_context_validates_explicit_routes_shared_reads_and_navigation(headers, path, method, expected):
    assert guard_workspace_request(headers, path, method, 8791) == expected


@pytest.mark.parametrize("headers,path,method,status", [
    ({"X-Icarus-Workspace": "cc1"}, "/admin/pause", "POST", 409),
    ({"Referer": "http://127.0.0.1:8791/dashboards/cc1"}, "/admin/engine-control", "POST", 409),
    ({"X-Icarus-Workspace": "cc1"}, "/status/public", "GET", 503),
    ({"X-Icarus-Workspace": "cc1"}, "/api/brain", "GET", 503),
    ({"X-Icarus-Workspace": "cc1"}, "/api/command-centers/cc2/status", "GET", 409),
    ({"X-Icarus-Workspace": "cc1"}, "/admin/command-centers/cc2/pause", "POST", 409),
    ({"X-Icarus-Workspace": "main", "Referer": "http://localhost:8791/dashboards/cc1"}, "/admin/pause", "POST", 409),
    ({"X-Icarus-Workspace": "cc1", "Referer": "http://localhost:8791/dashboards/cc2"}, "/api/command-centers/cc1/status", "GET", 409),
    ({"X-Icarus-Workspace": "unknown"}, "/api/presets", "GET", 400),
    ({"X-Icarus-Workspace": ""}, "/admin/pause", "POST", 400),
])
def test_context_refuses_parent_operations_and_foreign_workspace(headers, path, method, status):
    with pytest.raises(WorkspaceContextError) as caught:
        guard_workspace_request(headers, path, method, 8791)
    assert caught.value.status == status and caught.value.detail

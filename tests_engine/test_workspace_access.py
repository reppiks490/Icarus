"""Shared native Access transport retains page context and registry authority."""
import json
import sqlite3

import pytest

from tests_engine.test_workspace_api import workspace_http  # noqa: F401
from tests_engine.test_workspace_client import NODE, run_js
from icarus_engine.workspace_context import WorkspaceContextError, guard_workspace_request


@pytest.mark.parametrize("scope", ["cc1", "cc2", "cc3", "cc4"])
@pytest.mark.skipif(NODE is None, reason="optional Node unavailable")
def test_access_client_keeps_native_read_and_owner_action_paths(scope):
    run_js("const scope=" + json.dumps(scope) + r""";
const {c,calls}=client(scope,(url,init)=>{
 const p=new URL(url).pathname;
 if(p==='/api/access')return reply({me:{role:'owner'},users:[]});
 if(p==='/admin/access/add')return reply({user:{id:'viewer',token:'shown-once'}},201);
 if(p==='/admin/access/kick')return reply({ok:true});
 return reply({...identity(scope),detail:'selected Access adapter unavailable'},503);
});
const read=await c.request('/api/access');
assert.equal(read.status,200);assert.equal(read.headers.get('X-Icarus-Scope'),'shared');
assert.equal((await read.json()).me.role,'owner');
assert.equal((await c.shared('/api/access')).me.role,'owner');
const added=await c.request('/admin/access/add',{method:'POST',headers:{'Content-Type':'application/json','X-Icarus-Workspace':'main'},body:JSON.stringify({label:'Viewer'})});
assert.equal(added.status,201);assert.equal(added.headers.get('X-Icarus-Scope'),'shared');
assert.equal((await added.json()).user.token,'shown-once');
assert.equal((await c.request('/admin/access/kick',{method:'POST',body:JSON.stringify({id:'viewer'})})).status,200);
assert.deepEqual(calls.map(call=>call.path),['/api/access','/api/access','/admin/access/add','/admin/access/kick']);
assert(calls.every(call=>call.headers.get('X-Icarus-Workspace')===scope));
assert(calls.every(call=>call.headers.get('Authorization')==='Bearer test-token'));
assert.deepEqual(calls[2].body,{label:'Viewer'});assert.deepEqual(calls[3].body,{id:'viewer'});
assert.equal(c.context.id,scope);assert(Object.isFrozen(c.context));
""")


@pytest.mark.parametrize("scope", ["main", "cc2"])
@pytest.mark.skipif(NODE is None, reason="optional Node unavailable")
def test_access_client_rejects_selectors_and_nearby_routes_before_fetch(scope):
    run_js("const scope=" + json.dumps(scope) + r""";
const {c,calls}=client(scope,()=>reply({}));
for(const path of ['/api/access?workspace=main','/api/access?profile=cc1','/api/access?workspace_id=cc3',
 '/api/access?asset=NQ','/api/access?workspace=','/api/access?cache=1',
 '/api/access/../access','/api/access;extra','/api/other/../access',
 '/api/access/extra','/api/access/','/admin/access/add/extra','/admin/access/kick/',
 '/admin/access/other/../add','/admin/access/add;extra',
 '/admin/access','/admin/access/other']){
 await assert.rejects(c.request(path,{method:path.startsWith('/admin/')?'POST':'GET',body:path.startsWith('/admin/')?'{}':undefined}));
}
await assert.rejects(c.shared('/api/access?workspace=cc1'));
await assert.rejects(c.shared('/api/access/../access'));
await assert.rejects(c.request('/api/access',{body:JSON.stringify({workspace:'cc1'})}));
for(const path of ['/admin/access/add','/admin/access/kick']){
 const required=path.endsWith('/add')?{label:'Viewer'}:{id:'viewer'};
 for(const selector of ['workspace','workspace_id','profile','asset','symbol','config_revision'])
  await assert.rejects(c.request(path,{method:'POST',body:JSON.stringify({...required,[selector]:'cc1'})}));
 await assert.rejects(c.request(path+'?workspace=cc1',{method:'POST',body:JSON.stringify(required)}));
 await assert.rejects(c.request(path));
}
await assert.rejects(c.request('/api/access',{method:'POST',body:'{}'}));
assert.equal(calls.length,0);
""")


@pytest.mark.parametrize("scope", ["cc1", "cc2", "cc3", "cc4"])
def test_shared_access_uses_one_native_registry_with_owner_and_revocation(workspace_http, scope):
    server, parent, request = workspace_http
    selected = {"X-Icarus-Workspace": scope,
                "Referer": f"http://127.0.0.1:{server.server_port}/dashboards/{scope}"}
    code, created, _ = request("/admin/access/add", body={"label": f"Shared {scope}"}, extra_headers=selected)
    assert code == 201
    viewer = created["user"]
    assert viewer["role"] == "viewer" and viewer["token"]
    for reader in ("main", "cc1", "cc2", "cc3", "cc4"):
        code, snapshot, _ = request("/api/access", extra_headers={"X-Icarus-Workspace": reader})
        assert code == 200 and snapshot["me"]["role"] == "owner"
        row = next(user for user in snapshot["users"] if user["id"] == viewer["id"])
        assert row["label"] == f"Shared {scope}" and row["active"]
        assert "token" not in row and "token_hash" not in row
        assert viewer["token"] not in json.dumps(snapshot)
    assert request("/api/access", token=viewer["token"], extra_headers=selected)[0] == 200
    assert request("/api/access", token=None, extra_headers=selected)[0] == 401
    assert request("/admin/access/add", body={"label": "Forbidden"}, token=viewer["token"], extra_headers=selected)[0] == 403
    assert request("/admin/access/kick", body={"id": viewer["id"]}, token=viewer["token"], extra_headers=selected)[0] == 403
    assert request("/admin/access/kick", body={"id": "owner"}, extra_headers=selected)[0] == 400
    assert request("/admin/access/kick", body={"id": viewer["id"]}, extra_headers=selected)[0] == 200
    assert request("/api/access", token=viewer["token"], extra_headers=selected)[0] == 401
    with sqlite3.connect(parent.base_dir + "/access_registry.sqlite3") as db:
        digest = db.execute("SELECT token_hash FROM users WHERE id=?", (viewer["id"],)).fetchone()[0]
    assert digest != viewer["token"] and len(digest) == 64
    assert not parent.runners["NQ"].paused
    assert all(not portfolio.runners["NQ"].paused for portfolio in server.command_centers.portfolios.values())


@pytest.mark.parametrize("scope", ["main", "cc1"])
@pytest.mark.parametrize("path,body", [
    ("/api/access?workspace=cc2", None),
    ("/api/access?workspace=", None),
    ("/api/access?profile=cc2", None),
    ("/api/access?workspace_id=cc2", None),
    ("/api/access?asset=NQ", None),
    ("/api/access;extra", None),
    ("/api/access;", None),
    ("/admin/access/add?workspace=cc2", {"label": "Forbidden"}),
    ("/admin/access/add;extra", {"label": "Forbidden"}),
    ("/admin/access/add;", {"label": "Forbidden"}),
    ("/admin/access/kick?workspace=cc2", {"id": "owner"}),
    ("/admin/access/add", {"label": "Forbidden", "workspace": "cc2"}),
    ("/admin/access/add", {"label": "Forbidden", "workspace_id": "cc2"}),
    ("/admin/access/kick", {"id": "owner", "profile": "cc2"}),
])
def test_native_access_rejects_scope_selectors_without_registry_mutation(workspace_http, scope, path, body):
    _, _, request = workspace_http
    if path.startswith("/admin/access/kick"):
        viewer = request("/admin/access/add", body={"label": "Keep active"})[1]["user"]
        body = {**body, "id": viewer["id"]}
    before = request("/api/access")[1]["users"]
    assert request(path, body=body, extra_headers={"X-Icarus-Workspace": scope})[0] == 400
    after = request("/api/access")[1]["users"]
    assert [(u["id"], u["label"], u["active"]) for u in after] == [
        (u["id"], u["label"], u["active"]) for u in before]


@pytest.mark.parametrize("path,method", [
    ("/api/access", "GET"), ("/admin/access/add", "POST"), ("/admin/access/kick", "POST"),
])
def test_access_guard_retains_header_and_referer_context(path, method):
    assert guard_workspace_request({"X-Icarus-Workspace": "cc3"}, path, method, 8791) == "cc3"
    assert guard_workspace_request({"Referer": "http://localhost:8791/dashboards/cc4"}, path, method, 8791) == "cc4"
    with pytest.raises(WorkspaceContextError) as caught:
        guard_workspace_request({"X-Icarus-Workspace": "main", "Referer": "http://localhost:8791/dashboards/cc4"}, path, method, 8791)
    assert caught.value.status == 409


@pytest.mark.parametrize("path,method", [
    ("/api/access/extra", "GET"), ("/api/access/", "GET"),
    ("/admin/access/add/extra", "POST"), ("/admin/access/kick/", "POST"),
    ("/admin/access/other", "POST"), ("/api/access", "POST"),
    ("/admin/access/add", "GET"), ("/admin/pause", "POST"), ("/api/brain", "GET"),
])
def test_access_allowlist_does_not_open_other_native_workspace_routes(path, method):
    with pytest.raises(WorkspaceContextError):
        guard_workspace_request({"X-Icarus-Workspace": "cc1"}, path, method, 8791)


@pytest.mark.parametrize("path,method", [
    ("/api/command-centers/cc1/chart/NQ?n=20&offset=20", "GET"),
    ("/api/command-centers/cc1/trades/NQ?limit=10", "GET"),
    ("/api/presets?asset=NQ", "GET"),
])
def test_raw_context_guard_preserves_unrelated_query_routing(path, method):
    assert guard_workspace_request({"X-Icarus-Workspace": "cc1"}, path, method, 8791) == "cc1"


@pytest.mark.parametrize("path,body", [
    ("/api/access/extra", None), ("/api/access/", None),
    ("/admin/access/add/extra", {"label": "Forbidden"}),
    ("/admin/access/kick/", {"id": "owner"}),
    ("/admin/access/other", {"label": "Forbidden"}),
])
def test_native_access_prefixes_do_not_reach_registry(workspace_http, path, body):
    _, _, request = workspace_http
    before = request("/api/access")[1]["total_users"]
    assert request(path, body=body, extra_headers={"X-Icarus-Workspace": "cc1"})[0] >= 400
    assert request("/api/access")[1]["total_users"] == before

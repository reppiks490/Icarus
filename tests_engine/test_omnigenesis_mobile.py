"""Mobile gateway only forwards OMNIGENESIS as an authenticated read surface."""
from __future__ import annotations

import pytest

from icarus_mobile_gateway.proxy import UpstreamClient, UpstreamError


def test_omnigenesis_whitelisted_only_for_authenticated_mobile_read(monkeypatch):
    calls=[]
    client=UpstreamClient("http://127.0.0.1:8791",admin_token="test-secret")
    def fake_get(path,authenticated=False,query=None):
        calls.append((path,authenticated,query))
        return {"schema_version":"icarus-omnigenesis-snapshot-v1",
                "status":"RESEARCH_ONLY","authority":{"execution_authorized":False}}
    monkeypatch.setattr(client,"_get",fake_get)
    response=client.mobile_get("/v1/omnigenesis",{})
    assert response["status"]=="RESEARCH_ONLY"
    assert calls==[("/api/omnigenesis",True,{})]
    with pytest.raises(UpstreamError) as error:
        client.mobile_post("/v1/omnigenesis",{"execution_authorized":True})
    assert error.value.status==404


def test_unknown_mobile_omnigenesis_mutations_unavailable():
    client=UpstreamClient("http://127.0.0.1:8791",admin_token="test-secret")
    for route in ("/v1/omnigenesis/execute","/v1/omnigenesis/promote",
                  "/v1/omnigenesis/order"):
        with pytest.raises(UpstreamError) as error:
            client.mobile_get(route,{})
        assert error.value.status==404

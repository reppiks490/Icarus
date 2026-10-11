"""Pinned public-GitHub intake, offline fakes, and receipt/privacy boundaries."""
import io
import json
from pathlib import Path

import pytest

from tools.catalog_registry_ingest import CatalogFetchError, GitHubPublicCatalogClient, run


PAYLOAD = b"# Finance\n| API Name | Description |\n|---|---|\n| [A](https://example.com) | SECRET_SENTINEL |\n"


class FakeClient:
    def __init__(self, payload=PAYLOAD, resolved="a" * 40):
        self.payload, self.resolved = payload, resolved
        self.fetch_calls = []

    def resolve_ref(self, repo, ref="main"):
        return self.resolved

    def fetch_text(self, repo, commit, path):
        self.fetch_calls.append((repo, commit, path))
        return self.payload


def test_fetch_uses_resolved_commit_not_mutable_ref(tmp_path):
    client = FakeClient()
    result = run(tmp_path, run_id="r1", catalog_ids=["api-mega-list"], client=client)
    assert result["status"] == "SUCCESS"
    assert client.fetch_calls == [("cporter202/API-mega-list", "a" * 40, "README.md")]


def test_public_client_pins_requests_and_reads_one_byte_past_limit():
    requests = []
    reads = []
    class Response(io.BytesIO):
        def read(self, size=-1):
            reads.append(size)
            return super().read(size)
    def opener(request, timeout):
        requests.append(request)
        if "api.github.com" in request.full_url:
            return Response(json.dumps({"sha": "a" * 40}).encode())
        return Response(b"x" * 20_000_001)
    client = GitHubPublicCatalogClient(opener=opener)
    assert client.resolve_ref("cporter202/API-mega-list") == "a" * 40
    with pytest.raises(CatalogFetchError, match="CATALOG_PAYLOAD_LIMIT"):
        client.fetch_text("cporter202/API-mega-list", "a" * 40, "README.md")
    assert requests[-1].full_url == "https://raw.githubusercontent.com/cporter202/API-mega-list/" + "a" * 40 + "/README.md"
    assert requests[-1].get_header("User-agent") == "ICARUS-catalog-registry/1"
    assert reads[-1] == 20_000_001


@pytest.mark.parametrize("repo,commit,path", [
    ("evil.example/x", "a" * 40, "README.md"),
    ("cporter202/API-mega-list", "main", "README.md"),
    ("cporter202/API-mega-list", "a" * 40, "../secret"),
    ("cporter202/API-mega-list", "a" * 40, "/README.md"),
    ("cporter202/API-mega-list", "a" * 40, "README.md?token=abc"),
])
def test_invalid_network_target_is_rejected_before_io(repo, commit, path):
    def forbidden(*args, **kwargs):
        pytest.fail("invalid target reached network opener")
    with pytest.raises(CatalogFetchError):
        GitHubPublicCatalogClient(opener=forbidden).fetch_text(repo, commit, path)


def test_receipt_contains_no_raw_rows_or_secrets_and_cache_is_ignored(tmp_path):
    result = run(tmp_path, run_id="r1", catalog_ids=["api-mega-list"], client=FakeClient())
    receipt = (tmp_path / result["receipt_path"]).read_text()
    assert "SECRET_SENTINEL" not in receipt
    assert "https://example.com" not in receipt
    data = json.loads(receipt)
    assert data["execution_authorized"] is False
    assert data["production_decision_authorized"] is False
    assert data["chatgpt_tokens_used"] == data["paid_model_calls"] == 0
    assert len(data["catalogs"]["api-mega-list"]["content_sha256"]) == 64
    assert len(list((tmp_path / ".catalog_registry_cache/raw").rglob("*.md.gz"))) == 1
    assert ".catalog_registry_cache/" in (Path(__file__).resolve().parents[1] / ".gitignore").read_text()


def test_same_commit_content_reuses_snapshot_and_preserves_first_retrieval(tmp_path):
    first = run(tmp_path, run_id="r1", catalog_ids=["api-mega-list"], client=FakeClient())
    second = run(tmp_path, run_id="r2", catalog_ids=["api-mega-list"], client=FakeClient())
    a, b = (r["catalogs"]["api-mega-list"] for r in (first, second))
    assert a["snapshot_id"] == b["snapshot_id"]
    assert a["retrieved_at"] == b["retrieved_at"]
    assert a["import_summary"] == b["import_summary"]


def test_failed_fetch_writes_cycle_but_preserves_successful_latest(tmp_path):
    first = run(tmp_path, run_id="r1", catalog_ids=["api-mega-list"], client=FakeClient())
    latest = tmp_path / "automation_intelligence/catalog_registry_v1/latest/api-mega-list.json"
    before = latest.read_bytes()
    class Broken(FakeClient):
        def fetch_text(self, *args):
            raise CatalogFetchError("NETWORK_FAILURE")
    failed = run(tmp_path, run_id="r2", catalog_ids=["api-mega-list"], client=Broken())
    assert failed["status"] == "FAILED"
    assert latest.read_bytes() == before
    assert (tmp_path / failed["receipt_path"]).is_file()
    assert failed["errors"] == [{"catalog_id": "api-mega-list", "error_code": "NETWORK_FAILURE"}]


def test_bad_commit_and_oversized_fake_fail_closed(tmp_path):
    result = run(tmp_path, run_id="bad-ref", catalog_ids=["api-mega-list"], client=FakeClient(resolved="main"))
    assert result["status"] == "FAILED"
    assert result["errors"][0]["error_code"] == "INVALID_COMMIT"
    result = run(tmp_path, run_id="over-limit", catalog_ids=["api-mega-list"], client=FakeClient(b"x" * 20_000_001))
    assert result["errors"][0]["error_code"] == "CATALOG_PAYLOAD_LIMIT"


def test_run_id_and_catalog_selection_cannot_escape_allowlist(tmp_path):
    for run_id in ("../outside", "/tmp/x", "", "r/1"):
        with pytest.raises(ValueError):
            run(tmp_path, run_id=run_id, client=FakeClient())
    with pytest.raises(ValueError):
        run(tmp_path, run_id="r1", catalog_ids=["unapproved"], client=FakeClient())
    assert not (tmp_path / "research").exists()


def test_all_three_sources_and_capability_only_tools_import_offline(tmp_path):
    class Catalogs(FakeClient):
        def fetch_text(self, repo, commit, path):
            self.fetch_calls.append((repo, commit, path))
            if repo.endswith("ai-agent-tools"):
                return b"# AI\n- [Assistant](https://example.com/assistant) - Coding assistant\n"
            return PAYLOAD
    result = run(tmp_path, run_id="all", client=Catalogs())
    assert result["status"] == "SUCCESS"
    assert len(result["catalogs"]) == 3
    from icarus_engine.discovery_registry.service import DiscoveryRegistryService
    service = DiscoveryRegistryService(tmp_path)
    tools = [c for c in service.store.candidates() if c.canonical_name == "Assistant"]
    assert len(tools) == 1 and tools[0].capability_only is True
    service.close()


def test_existing_run_id_cannot_overwrite_immutable_cycle(tmp_path):
    run(tmp_path, run_id="r1", client=FakeClient())
    with pytest.raises(FileExistsError):
        run(tmp_path, run_id="r1", client=FakeClient())

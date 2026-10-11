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


def test_autonomous_workflow_is_offline_tested_and_scope_guarded():
    workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/catalog-registry-refresh.yml").read_text()
    assert "37 4 * * *" in workflow
    assert "workflow_dispatch" in workflow
    assert "contents: write" in workflow
    assert "--catalog all" in workflow
    assert "python -m pytest tests/test_catalog_registry_ingest.py tests_engine/test_discovery_registry_*.py -q" in workflow
    assert workflow.index("python -m pytest") < workflow.index("python -m tools.catalog_registry_ingest")
    assert "secrets." not in workflow
    assert "chatgpt" not in workflow.lower()
    assert "git rebase" not in workflow and "--force" not in workflow
    assert "Out-of-scope paths staged" in workflow
    adds = [line.strip() for line in workflow.splitlines() if "git add " in line]
    assert adds
    assert all(".catalog_registry_cache" not in line and "research/capability_registry.sqlite3" not in line for line in adds)
    assert 'automation_intelligence/catalog_registry_v1/cycles/$RUN_ID' in workflow
    assert 'automation_intelligence/catalog_registry_v1/latest' in workflow
    assert "catalog-registry-v1-" in workflow
    assert "actions/cache/restore@v4" in workflow and "actions/cache/save@v4" in workflow
    assert "refs/heads/main" in workflow
    # Only the bounded receipt is uploaded, not a cache/database/directory of raw data.
    artifact = workflow.split("uses: actions/upload-artifact@v4", 1)[1].split("- name:", 1)[0]
    assert "receipt.json" in artifact
    assert ".catalog_registry_cache" not in artifact and "sqlite3" not in artifact


def test_cli_federates_local_receipts_without_downloader_calls(tmp_path):
    from datetime import datetime, timezone
    config = tmp_path / "config"
    config.mkdir()
    (config / "provider_endpoint_catalog.json").write_text(json.dumps({"operations": [
        {"id": "twelve:get:/quote", "provider": "twelve", "method": "GET", "path": "/quote"}]}))
    latest = tmp_path / "automation_intelligence/provider_collection_v1/latest"
    latest.mkdir(parents=True)
    (latest / "twelve.json").write_text(json.dumps({"completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "providers": {"twelve": {"status": "COLLECTED_PARTIAL", "collected_pages": 1}}}))
    payload = PAYLOAD.replace(b"https://example.com", b"https://twelvedata.com")
    result = run(tmp_path, run_id="federated", catalog_ids=["api-mega-list"], client=FakeClient(payload))
    assert result["provider_federation"]["events_recorded"] == 1
    assert result["registry_summary"]["provider_links"] == 1
    assert result["registry_summary"]["qualification_events"] == 1


@pytest.mark.parametrize("payload", [
    PAYLOAD.replace(b"https://example.com", b"https://user:SECRET_SENTINEL@example.com"),
    PAYLOAD.replace(b"https://example.com", b"https://example.com?api_key=SECRET_SENTINEL"),
    PAYLOAD.replace(b"SECRET_SENTINEL", b"Authorization: Bearer SECRET_SENTINEL"),
])
def test_credential_content_never_enters_raw_cache_or_registry(tmp_path, payload):
    result = run(tmp_path, run_id="secret", catalog_ids=["api-mega-list"], client=FakeClient(payload))
    assert result["status"] == "FAILED"
    assert result["errors"][0]["error_code"] == "CREDENTIAL_BEARING_METADATA"
    assert result["registry_summary"]["catalog_snapshots"] == 0
    assert not (tmp_path / ".catalog_registry_cache/raw").exists()
    assert "SECRET_SENTINEL" not in (tmp_path / result["receipt_path"]).read_text()


@pytest.mark.parametrize("description", ['{"api_key": "SECRET_SENTINEL"}', '{"password": "SECRET_SENTINEL"}',
    '"Authorization": "Bearer SECRET_SENTINEL"', 'api_token=SECRET_SENTINEL', 'auth_token=SECRET_SENTINEL'])
def test_quoted_and_alias_credentials_fail_before_persistence(tmp_path, description):
    result = run(tmp_path, run_id="quoted-secret", catalog_ids=["api-mega-list"],
                 client=FakeClient(PAYLOAD.replace(b"SECRET_SENTINEL", description.encode())))
    assert result["status"] == "FAILED"
    assert not (tmp_path / ".catalog_registry_cache/raw").exists()


def test_corrupted_existing_snapshot_cache_is_repaired_atomically(tmp_path):
    import gzip
    import hashlib
    digest = hashlib.sha256(PAYLOAD).hexdigest()
    cache = tmp_path / ".catalog_registry_cache/raw/api-mega-list" / ("a" * 40) / (digest + ".md.gz")
    cache.parent.mkdir(parents=True)
    cache.write_bytes(gzip.compress(b""))
    result = run(tmp_path, run_id="repair-cache", catalog_ids=["api-mega-list"], client=FakeClient())
    assert result["status"] == "SUCCESS"
    assert gzip.decompress(cache.read_bytes()) == PAYLOAD
    assert not list(cache.parent.glob(".registry-*"))


def test_unrecognized_empty_catalog_format_does_not_claim_success(tmp_path):
    result = run(tmp_path, run_id="format-drift", catalog_ids=["api-mega-list"],
                 client=FakeClient(b"# Catalog\n- [A](https://example.com) - Valid bullet, wrong configured format\n"))
    assert result["status"] == "FAILED"
    assert result["errors"][0]["error_code"] == "UNRECOGNIZED_CATALOG_FORMAT"

from __future__ import annotations

from pathlib import Path


WORKFLOW = Path('.github/workflows/provider-exhaustive-collection.yml')
HANDOFF = Path('GITHUB_NATIVE_DATA_FEDERATION.md')
AGENTS = Path('AGENTS.md')
COLLECTOR = Path('tools/provider_exhaustive_collection.py')


ALIASES = {
    'TICKSTREAM_API_KEY': ('TICKSTREAM_API_KEY', 'TICKSTREAM', 'TICKSTREAM_KEY', 'TICKSTREAM_TOKEN', 'TICK_STREAM_API_KEY'),
    'MASSIVE_API_KEY': ('MASSIVE_API_KEY', 'MASSIVE', 'MASSIVE_API_TOKEN', 'MASSIVE_KEY', 'MASSIVE_TOKEN', 'POLYGON_API_KEY', 'POLYGON_IO_API_KEY', 'POLYGON_KEY', 'POLYGON_TOKEN', 'POLYGON'),
    'TWELVEDATA_API_KEY': ('TWELVEDATA_API_KEY', 'TWELVEDATA', 'TWELVEDATA_KEY', 'TWELVE_API_KEY', 'TWELVE_DATA', 'TWELVE_DATA_API_KEY', 'TWELVE_DATA_KEY', 'TWELVE_KEY', 'TD_API_KEY'),
    'FMP_API_KEY': ('FMP_API_KEY', 'FMP_KEY'),
    'EODHD_API_TOKEN': ('EODHD_API_TOKEN', 'EODHD_API_KEY', 'EODHD_KEY', 'EOD_API_KEY'),
    'TIINGO_API_TOKEN': ('TIINGO_API_TOKEN', 'TIINGO_API_KEY', 'TIINGO_KEY', 'TIINGO_TOKEN'),
    'INTRINIO_API_KEY': ('INTRINIO_API_KEY', 'INTRINIO', 'INTRINIO_API_TOKEN', 'INTRINIO_KEY', 'INTRINIO_TOKEN'),
    'QUIVER_API_KEY': ('QUIVER_API_KEY', 'QUIVER', 'QUIVERQUANT_API_KEY', 'QUIVER_API_TOKEN', 'QUIVER_KEY', 'QUIVER_QUANT_API_KEY', 'QUIVER_TOKEN'),
    'FRED_API_KEY': ('FRED_API_KEY', 'FRED_KEY'),
    'ALPACA_API_KEY': ('ALPACA_API_KEY', 'ALPACA_API_KEY_ID', 'ALPACA_KEY', 'ALPACA_KEY_ID', 'ALPACA_PAPER_KEY', 'APCA_API_KEY_ID'),
    'ALPACA_SECRET_KEY': ('ALPACA_API_SECRET', 'ALPACA_API_SECRET_KEY', 'ALPACA_SECRET', 'ALPACA_SECRET_KEY', 'ALPACA_PAPER_SECRET', 'APCA_API_SECRET_KEY'),
    'ICARUS_DATA_ARCHIVE_KEY': ('ICARUS_DATA_ARCHIVE_KEY',),
}


def _env_expression(text: str, name: str) -> str:
    prefix = name + ':'
    matches = [line.strip()[len(prefix):].strip() for line in text.splitlines() if line.strip().startswith(prefix)]
    assert len(matches) == 1, (name, matches)
    return matches[0]


def test_provider_workflow_resolves_every_supported_alias_from_secrets_only() -> None:
    text = WORKFLOW.read_text()
    for canonical, aliases in ALIASES.items():
        expression = _env_expression(text, canonical)
        for alias in aliases:
            assert f'secrets.{alias}' in expression, (canonical, alias)
            assert f'vars.{alias}' not in expression, (canonical, alias)


def test_legacy_duplicate_runtime_names_are_not_exported_by_actions() -> None:
    text = WORKFLOW.read_text()
    env_block = text.split('      - name: Drain all-catalog provider queue without ChatGPT', 1)[1].split('        run:', 1)[0]
    for legacy in (
        'TICK_STREAM_API_KEY', 'POLYGON_API_KEY', 'TWELVE_DATA_API_KEY', 'TWELVE_API_KEY',
        'EODHD_API_KEY', 'TIINGO_API_KEY', 'INTRINIO_API_TOKEN', 'QUIVER_API_TOKEN',
        'QUIVER_QUANT_API_KEY',
    ):
        assert f'          {legacy}:' not in env_block
    assert 'vars.' not in env_block


def test_collector_preserves_cross_repo_owner_failover_and_intrinio_owner() -> None:
    text = COLLECTOR.read_text()
    assert "preferred='reppiks490/Icarus' if args.provider=='intrinio' else 'reppiks490/Icarus-engine'" in text
    assert 'STANDBY_PREFERRED_OWNER' in text
    assert 'BLOCKED_MISSING_CREDENTIAL' in text
    assert 'BLOCKED_AUTHENTICATION' in text


def test_handoff_requires_engine_ledger_and_no_plaintext_credentials() -> None:
    text = HANDOFF.read_text().lower()
    for phrase in (
        'reppiks490/icarus-engine',
        'config/data_ingestion_manifest.json',
        'federated_data_collection.md',
        'all ai units',
        'github actions secrets',
        'variables are for non-sensitive',
        'do not copy plaintext',
        'intrinio',
        'preferred owner',
    ):
        assert phrase in text


def test_agent_entrypoint_requires_shared_cross_repo_ledger_and_coordination_bus() -> None:
    text = AGENTS.read_text().lower()
    for phrase in (
        'every ai unit',
        'reppiks490/icarus-engine',
        'config/data_ingestion_manifest.json',
        'config/federated_repo_evidence.json',
        'sentinel/data_health.json',
        'github actions secrets',
        'variables',
        'non-sensitive configuration',
        'intrinio',
        'zero known icarus-owned gaps',
        'reppiks490/icarus-owner-actions',
        'coordination/start_here.md',
        'coordination/active.md',
        'coordination/collisions.json',
        'plan',
        'claim',
        'waiting',
        'no model-specific task ownership',
        'live broker arming',
        'disabled',
    ):
        assert phrase in text

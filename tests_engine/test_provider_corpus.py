import hashlib
import json
from pathlib import Path

import pytest

from icarus_engine import provider_corpus as pc


def source():
    return json.loads(Path(pc.DEFAULT_PATH).read_text())


def consume(payload=None, **kwargs):
    return pc.consume_context(source() if payload is None else payload,
        source_blob_sha=pc.SOURCE_BLOB_SHA, available_at_ns=pc.AVAILABLE_AT_NS,
        asof_ns=pc.AVAILABLE_AT_NS, **kwargs)


def test_real_public_bytes_values_and_actual_reads():
    raw = Path(pc.DEFAULT_PATH).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == '58325d5985863eacfaab0571bb48cfc783ce350c9fb962a6976c2de6b365194e'
    result = consume()
    assert result['summary']['source_rows_reported'] == 132554
    assert result['summary']['feature_records_consumed'] == 4
    assert result['summary']['statistical_columns_consumed'] == 5
    assert result['summary']['unique_numeric_values_consumed'] == 25
    assert result['summary']['numeric_feature_reads'] == 150
    assert result['summary']['raw_rows_consumed'] == 0
    assert result['features'][0]['statistics']['mean'] == 92.75882111436948
    assert len([f for f in result['features'] if f['provider'] == 'fred']) == 2
    assert result['quality'][0]['range'] == pytest.approx(327.24)
    assert result['quality'][2]['zero_dispersion'] is True
    assert result['provider_coverage'][-1]['current_status'] == 'BLOCKED_AUTHENTICATION'
    assert result['provider_coverage'][-1]['historical_rows_reported'] == 111
    assert len(json.dumps(result).encode()) < 24576
    assert result['candidate_evidence_eligible'] is False
    assert result['execution_authorized'] is False


def test_snapshot_exact_and_no_follow(tmp_path):
    assert pc.snapshot(now_ns=pc.AVAILABLE_AT_NS)['status'] == 'HISTORICAL_CONTEXT_CONSUMED'
    file = tmp_path / 'bundle.json'
    file.write_bytes(Path(pc.DEFAULT_PATH).read_bytes())
    assert pc.snapshot(now_ns=pc.AVAILABLE_AT_NS, path=file)['status'] == 'HISTORICAL_CONTEXT_CONSUMED'
    file.write_text('{}')
    assert pc.snapshot(now_ns=pc.AVAILABLE_AT_NS, path=file)['status'] == 'UNAVAILABLE'
    link = tmp_path / 'link.json'
    try:
        link.symlink_to(pc.DEFAULT_PATH)
    except OSError:
        pass  # Some Windows runners disallow unprivileged symlinks.
    else:
        assert pc.snapshot(now_ns=pc.AVAILABLE_AT_NS, path=link)['status'] == 'UNAVAILABLE'
    assert pc.snapshot(now_ns=pc.AVAILABLE_AT_NS - 1)['status'] == 'UNAVAILABLE'


@pytest.mark.parametrize('mutation', [
    lambda p: p.update(api_key='secret'),
    lambda p: p.update(execution_authorized=True),
    lambda p: p['summary'].update(collected_rows=1),
    lambda p: p['providers']['fred'].update(completed_at_utc='2099-01-01T00:00:00Z'),
    lambda p: p['providers']['fred'].update(completed_at_utc='2026-10-19T01:17:54'),
    lambda p: p['providers']['fred']['research_features'][0]['features']['value'].update(mean=True),
    lambda p: p['providers']['fred']['research_features'][0]['features']['value'].update(mean='3'),
    lambda p: p['providers']['fred']['research_features'][0]['features']['value'].update(mean=float('nan')),
    lambda p: p['providers']['fred']['research_features'][0]['features']['value'].update(mean=1000),
    lambda p: p['providers']['fred']['research_features'][0]['features']['value'].update(standard_deviation=1000),
    lambda p: p['providers']['fred']['research_features'][0]['features']['value'].update(samples=0),
    lambda p: p['providers']['fred']['research_features'][0]['features']['value'].update(samples=True),
    lambda p: p['providers']['fred']['research_features'][0].update(ticker='invented'),
    lambda p: p['providers']['fred']['catalog'].update(secret='hidden'),
    lambda p: p['providers']['unusual_whales']['last_successful_receipt'].update(historical_only=False),
    lambda p: p['providers']['fred'].update(research_features=[{}] * 65),
])
def test_rejects_invalid_or_private_fields(mutation):
    payload = source()
    mutation(payload)
    with pytest.raises(ValueError, match='Invalid provider context'):
        consume(payload)


def test_consumers_are_isolated_and_empty_features_never_claim_usage():
    result = consume()
    result['workspaces']['cc1']['features'][0]['statistics']['mean'] = -1
    assert result['workspaces']['cc2']['features'][0]['statistics']['mean'] > 0
    payload = source()
    for provider in payload['providers'].values():
        provider['research_features'] = []
    result = consume(payload)
    assert result['summary']['numeric_feature_reads'] == 0
    assert result['summary']['feature_records_consumed'] == 0
    assert all(r['feature_used'] is False for r in result['read_receipts'])


@pytest.mark.parametrize('field,value', [('available_at_ns',True),('available_at_ns',10**1000),('asof_ns',-1),('asof_ns',10**1000),('source_blob_sha','bad')])
def test_invalid_boundary(field,value):
    args = dict(source_blob_sha=pc.SOURCE_BLOB_SHA, available_at_ns=pc.AVAILABLE_AT_NS, asof_ns=pc.AVAILABLE_AT_NS)
    args[field] = value
    with pytest.raises(ValueError):
        pc.consume_context(source(), **args)


def test_unknown_consumers_and_preavailability_fail():
    with pytest.raises(ValueError):
        consume(consumer_ids=('cc1','cc1'))
    with pytest.raises(ValueError):
        pc.consume_context(source(),source_blob_sha=pc.SOURCE_BLOB_SHA,available_at_ns=pc.AVAILABLE_AT_NS,asof_ns=pc.AVAILABLE_AT_NS - 1)


@pytest.mark.parametrize('mutation', [
    lambda p: p['summary'].update(providers_blocked=0),
    lambda p: p['providers']['fred'].update(status='BLOCKED_AUTHENTICATION'),
    lambda p: p['providers']['fred']['research_features'][0]['features']['value'].update(maximum=float('inf')),
    lambda p: p['providers']['fred']['research_features'][0]['features']['value'].update(minimum=10**1000),
    lambda p: p['providers']['fred']['last_successful_receipt'].update(api_key='private'),
    lambda p: p['providers']['fred'].update(credential_present=1),
    lambda p: p['providers']['fred'].update(substantive_work_performed=False),
])
def test_more_negative_controls(mutation):
    payload = source()
    mutation(payload)
    with pytest.raises(ValueError, match='Invalid provider context'):
        consume(payload)


def test_quality_and_views_are_derived_from_retained_values():
    result = consume()
    for field, diagnostic in zip(result['features'], result['quality']):
        statistics = field['statistics']
        assert diagnostic['range'] == statistics['maximum'] - statistics['minimum']
        if diagnostic['range']:
            assert diagnostic['dispersion_ratio'] == statistics['standard_deviation'] / diagnostic['range']
    assert result['read_receipts'][0]['numeric_feature_reads'] == 25
    assert result['workspaces']['cc4']['features'][3]['statistics']['samples'] == 9


def test_snapshot_bounds_and_missing_path(tmp_path):
    path = tmp_path / 'oversized.json'
    path.write_bytes(b' ' * (pc.MAX_BYTES + 1))
    assert pc.snapshot(now_ns=pc.AVAILABLE_AT_NS, path=path)['status'] == 'UNAVAILABLE'
    assert pc.snapshot(now_ns=pc.AVAILABLE_AT_NS, path=tmp_path / 'absent')['status'] == 'UNAVAILABLE'


def test_constant_distribution_cannot_have_positive_deviation():
    payload = source()
    payload['providers']['eodhd']['research_features'][0]['features']['volume']['standard_deviation'] = 1e-13
    with pytest.raises(ValueError, match='Invalid provider context'):
        consume(payload)

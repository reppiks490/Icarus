"""Bounded consumption of public derived statistics; never a market feed."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import time

SOURCE_COMMIT = '84dd20e5186cc26fe4c95a371ea5fbbfed2ecdfe'
SOURCE_BLOB_SHA = '6451722b09c73f357f4a6e27c8185eb9a6d3a52b'
SOURCE_SHA256 = '58325d5985863eacfaab0571bb48cfc783ce350c9fb962a6976c2de6b365194e'
AVAILABLE_AT_NS = 1792372790000000000
DEFAULT_PATH = Path(__file__).with_name('provider-corpus.json')
CONSUMER_IDS = ('quality', 'research', 'cc1', 'cc2', 'cc3', 'cc4')
MAX_BYTES = 131072
_PROVIDERS = frozenset(('alpaca','alphavantage','bybit','eodhd','finnhub','fmp','fred','intrinio','massive','quiver','tickstream','tiingo','twelve','unusual_whales'))
_STAT_FIELDS = frozenset(('minimum','maximum','mean','standard_deviation','samples'))
_CATALOG_FIELDS = frozenset(('asset_datasets_collected','asset_templates','assets','collected_operations','denied_operations','operations','pending_pages','qualification','unresolved_operations'))
_RECORD_FIELDS = frozenset(('catalog','collected_pages','collected_rows','completed_at_utc','credential_present','requests','research_features','run_id','status','substantive_work_performed'))
_FLAGS = dict(authority='RESEARCH_CONTEXT_ONLY', automatic_model_promotion=False,
    execution_authorized=False, production_decision_authorized=False,
    candidate_evidence_eligible=False, live_data=False, strategy_qualified=False,
    training_performed=False, paper_warmup_performed=False, historical_only=True,
    point_in_time_qualified=False)


def _fail():
    raise ValueError('Invalid provider context')


def _keys(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        _fail()


def _integer(value, maximum=10**12):
    if type(value) is not int or not 0 <= value <= maximum:
        _fail()
    return value


def _number(value):
    if type(value) not in (int, float) or not -1e18 <= value <= 1e18 or not math.isfinite(value):
        _fail()
    return value


def _label(value, pattern, limit=160):
    if not isinstance(value, str) or len(value) > limit or not re.fullmatch(pattern, value):
        _fail()
    return value


def _clock(value):
    if not isinstance(value, str) or not re.fullmatch(
            r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}'
            r'(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})', value):
        _fail()
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            _fail()
        elapsed = parsed.astimezone(timezone.utc) - datetime(1970, 1, 1, tzinfo=timezone.utc)
        ns = (elapsed.days * 86400 + elapsed.seconds) * 1_000_000_000 + elapsed.microseconds * 1000
        _integer(ns, 2**63 - 1)
        return ns
    except (ValueError, OverflowError, TypeError):
        _fail()


def _features(records, rows, provider):
    if not isinstance(records, list) or len(records) > 32:
        _fail()
    result = []
    for ordinal, record in enumerate(records):
        _keys(record, ('operation','features'))
        operation = _label(record['operation'], r'[a-z0-9_]+:get:[A-Za-z0-9_/{.}-]+')
        if not operation.startswith(provider + ':get:'):
            _fail()
        fields = record['features']
        if not isinstance(fields, dict) or not 1 <= len(fields) <= 8:
            _fail()
        for name, statistics in fields.items():
            _label(name, r'[a-z][a-z0-9_]{0,31}')
            # Only producer-defined statistical field names, never secret labels.
            if name not in ('value','close','volume','price','open','high','low'):
                _fail()
            _keys(statistics, _STAT_FIELDS)
            n = _integer(statistics['samples'])
            if n == 0 or n > rows:
                _fail()
            lo, hi, mean, sd = (_number(statistics[key]) for key in ('minimum','maximum','mean','standard_deviation'))
            if not lo <= mean <= hi or sd < 0:
                _fail()
            # Population and sample standard deviations both fit this bound.
            max_sd = math.sqrt((hi-mean)*(mean-lo)) * math.sqrt(n/(n-1)) if n > 1 else 0
            if sd > max_sd * (1 + 1e-9) or (n == 1 and lo != hi):
                _fail()
            result.append(dict(provider=provider, record_ordinal=ordinal, operation=operation,
                field=name, statistics=copy.deepcopy(statistics), instrument_identity=None,
                units=None, observation_window=None))
    return result


def _record(value, *, provider, snapshot_ns, historical=False):
    _keys(value, _RECORD_FIELDS | ({'historical_only'} if historical else {'last_successful_receipt'}))
    for name in ('collected_pages','collected_rows','requests'):
        _integer(value[name])
    if type(value['credential_present']) is not bool or type(value['substantive_work_performed']) is not bool:
        _fail()
    if historical and value['historical_only'] is not True:
        _fail()
    status = _label(value['status'], r'[A-Z][A-Z_]{0,79}')
    _label(value['run_id'], r'[A-Za-z0-9_-]{1,160}')
    completed_ns = _clock(value['completed_at_utc'])
    if completed_ns > snapshot_ns:
        _fail()
    _keys(value['catalog'], _CATALOG_FIELDS)
    for key, number in value['catalog'].items():
        if key == 'qualification':
            if number != 'INCOMPLETE_UNTIL_EVERY_OPERATION_ASSET_PAGE_TIME_RANGE_AND_TRANSPORT_IS_VERIFIED':
                _fail()
        else:
            _integer(number)
    features = _features(value['research_features'], value['collected_rows'], provider)
    substantive = value['collected_rows'] > 0
    if value['substantive_work_performed'] is not substantive:
        _fail()
    if (features or substantive) and not status.startswith('COLLECTED'):
        _fail()
    return features


def _validate(payload, available_at_ns, asof_ns):
    _keys(payload, ('schema_version','authority','automatic_model_promotion','execution_authorized',
        'production_decision_authorized','raw_payloads_included','providers','snapshot_at_utc','source_root','summary'))
    if payload['schema_version'] != 'icarus-provider-research-context-v1' or payload['authority'] != 'RESEARCH_CONTEXT_ONLY':
        _fail()
    for flag in ('automatic_model_promotion','execution_authorized','production_decision_authorized','raw_payloads_included'):
        if payload[flag] is not False:
            _fail()
    _integer(available_at_ns, 2**63-1)
    _integer(asof_ns, 2**63-1)
    snapshot_ns = _clock(payload['snapshot_at_utc'])
    if snapshot_ns > available_at_ns or available_at_ns > asof_ns:
        _fail()
    if payload['source_root'] != 'automation_intelligence/provider_collection_v1/latest+automation_intelligence/provider_collection_v1/cycles':
        _fail()
    providers = payload['providers']
    _keys(providers, _PROVIDERS)
    features, coverage = [], []
    for name, item in providers.items():
        features.extend(_record(item, provider=name, snapshot_ns=snapshot_ns))
        historical = item['last_successful_receipt']
        if historical is not None:
            _record(historical, provider=name, snapshot_ns=snapshot_ns, historical=True)
            if _clock(historical['completed_at_utc']) > _clock(item['completed_at_utc']):
                _fail()
        coverage.append(dict(provider=name,current_status=item['status'],
            current_rows_reported=item['collected_rows'],current_pages_reported=item['collected_pages'],
            credential_present=item['credential_present'],completed_at_utc=item['completed_at_utc'],
            historical_rows_reported=historical['collected_rows'] if historical else 0,
            historical_only=historical is not None,
            qualification='INCOMPLETE',execution_authorized=False))
    summary = payload['summary']
    _keys(summary, ('collected_pages','collected_rows','providers_blocked','providers_substantive','providers_total','requests'))
    expected = dict(collected_pages=sum(p['collected_pages'] for p in providers.values()),
        collected_rows=sum(p['collected_rows'] for p in providers.values()),
        requests=sum(p['requests'] for p in providers.values()),providers_total=len(providers),
        providers_substantive=sum(p['collected_rows'] > 0 for p in providers.values()),
        providers_blocked=sum(p['status'].startswith('BLOCKED') for p in providers.values()))
    for key, expected_value in expected.items():
        if _integer(summary[key]) != expected_value:
            _fail()
    if len(features) > 64:
        _fail()
    return coverage, features


def _consume(consumer, coverage, features):
    """Every recorded read happens here, after numeric schema validation."""
    diagnostics, retained = [], []
    numeric_reads = 0
    for feature in features:
        statistics = {}
        for field in sorted(_STAT_FIELDS):
            statistics[field] = feature['statistics'][field]
            numeric_reads += 1
        lo, hi = statistics['minimum'], statistics['maximum']
        diagnostics.append(dict(provider=feature['provider'],record_ordinal=feature['record_ordinal'],
            field=feature['field'],range=hi-lo,zero_dispersion=statistics['standard_deviation'] == 0,
            dispersion_ratio=statistics['standard_deviation']/(hi-lo) if hi != lo else None))
        retained.append({**feature, 'statistics': statistics})
    coverage_reads = 0
    statuses = {}
    for provider in coverage:
        statuses[provider['provider']] = provider['current_status']
        coverage_reads += 1
    receipt = dict(consumer_id=consumer,feature_records_read=len({(f['provider'],f['record_ordinal']) for f in retained}),
        statistical_columns_read=len(retained),numeric_feature_reads=numeric_reads,
        coverage_reads=coverage_reads,feature_used=numeric_reads > 0,raw_rows_consumed=0)
    return retained, diagnostics, statuses, receipt


def consume_context(payload, *, source_blob_sha, available_at_ns, asof_ns, consumer_ids=CONSUMER_IDS):
    """Validate safe derived context and run independent descriptive consumers.

    ``source_blob_sha`` must come from the authenticated repository transport.
    It is provenance metadata here; ``snapshot`` additionally verifies exact bytes.
    """
    _label(source_blob_sha, r'[0-9a-f]{40}', 40)
    if not isinstance(consumer_ids, (tuple,list)) or tuple(consumer_ids) != CONSUMER_IDS:
        _fail()
    coverage, features = _validate(payload, available_at_ns, asof_ns)
    output = dict(schema_version='icarus-provider-context-consumption-v1',status='HISTORICAL_CONTEXT_CONSUMED',
        source=dict(repository='reppiks490/Icarus-engine',blob_sha=source_blob_sha,
            available_at_ns=available_at_ns,snapshot_at_utc=payload['snapshot_at_utc']),
        provider_coverage=coverage,features=copy.deepcopy(features),quality=[],research=[],workspaces={},read_receipts=[],**_FLAGS)
    for consumer in consumer_ids:
        retained, diagnostics, statuses, receipt = _consume(consumer, coverage, features)
        output['read_receipts'].append(receipt)
        if consumer == 'quality':
            output['quality'] = diagnostics
        elif consumer == 'research':
            output['research'] = [dict(provider=f['provider'],record_ordinal=f['record_ordinal'],field=f['field'],
                mean=f['statistics']['mean'],samples=f['statistics']['samples'],
                observed_range=d['range'],dispersion_ratio=d['dispersion_ratio'],
                description='Historical distribution summary; instrument, units and observation window unverified.') for f, d in zip(retained, diagnostics)]
        else:
            output['workspaces'][consumer] = dict(features=copy.deepcopy(retained),
                provider_statuses=statuses,historical_only=True,strategy_input_authorized=False)
    records = len({(f['provider'],f['record_ordinal']) for f in features})
    output['summary'] = dict(providers_total=len(coverage),providers_with_current_rows=payload['summary']['providers_substantive'],
        source_rows_reported=payload['summary']['collected_rows'],source_pages_reported=payload['summary']['collected_pages'],
        feature_records_consumed=records,statistical_columns_consumed=len(features),unique_numeric_values_consumed=len(features)*5,
        numeric_feature_reads=sum(r['numeric_feature_reads'] for r in output['read_receipts']),
        coverage_reads=sum(r['coverage_reads'] for r in output['read_receipts']),raw_rows_consumed=0)
    if len(json.dumps(output, allow_nan=False).encode()) > 24576:
        _fail()
    return output


def _windows_open_no_follow(path):
    """Open the final Windows component itself, rejecting all reparse points.

    The handle is checked before conversion to a Python descriptor or reading.
    Its open share mode prevents replacement while it is being inspected.
    Parent-directory reparse points are outside this final-component guarantee.
    """
    import ctypes
    from ctypes import wintypes
    import msvcrt

    class AttributeTagInfo(ctypes.Structure):
        _fields_ = [('attributes', wintypes.DWORD), ('reparse_tag', wintypes.DWORD)]

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    create.restype = wintypes.HANDLE
    information = kernel.GetFileInformationByHandleEx
    information.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
    information.restype = wintypes.BOOL
    close = kernel.CloseHandle
    close.argtypes = (wintypes.HANDLE,)
    close.restype = wintypes.BOOL
    handle = create(os.fsdecode(path), 0x80000000, 0x00000001, None, 3,
                    0x00200000, None)  # READ, SHARE_READ, EXISTING, OPEN_REPARSE_POINT
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        attributes = AttributeTagInfo()
        if not information(handle, 9, ctypes.byref(attributes), ctypes.sizeof(attributes)):
            raise ctypes.WinError(ctypes.get_last_error())
        if attributes.attributes & 0x00000400:  # FILE_ATTRIBUTE_REPARSE_POINT
            _fail()
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        handle = None  # Descriptor now owns the native handle.
        return descriptor
    finally:
        if handle is not None:
            close(handle)


def _open_no_follow(path):
    if os.name == 'nt':
        return _windows_open_no_follow(path)
    if not hasattr(os, 'O_NOFOLLOW'):
        _fail()
    return os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NONBLOCK', 0))


def snapshot(now_ns=None, path=None):
    """Read a pinned metadata-only bundle without following a final symlink."""
    try:
        fd = _open_no_follow(DEFAULT_PATH if path is None else path)
        with os.fdopen(fd,'rb') as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
                _fail()
            raw = handle.read(MAX_BYTES+1)
        if len(raw) > MAX_BYTES or hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
            _fail()
        git_blob = hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        if git_blob != SOURCE_BLOB_SHA:
            _fail()
        output = consume_context(json.loads(raw),source_blob_sha=SOURCE_BLOB_SHA,
            available_at_ns=AVAILABLE_AT_NS,asof_ns=time.time_ns() if now_ns is None else now_ns)
        output['source'].update(commit=SOURCE_COMMIT,sha256=SOURCE_SHA256)
        return output
    except (OSError,ValueError,TypeError,OverflowError,RecursionError):
        return dict(schema_version='icarus-provider-context-consumption-v1',status='UNAVAILABLE',
            reason='PROVIDER_CONTEXT_UNAVAILABLE',**_FLAGS)

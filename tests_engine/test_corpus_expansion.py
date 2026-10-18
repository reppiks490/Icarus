"""Real pinned native metadata is the oracle; faults never touch provider data."""
import hashlib
import importlib
import json
from pathlib import Path

import pytest


BUNDLE = Path(__file__).parents[1] / "icarus_engine" / "corpus-expansion.json"
NOW = 1792401987000000000
FULL = ['CL', 'NG', 'HG', '6E', '6J', '6B', '6A', 'ZN', 'ZB', 'BTCF']
ABSENT = ['MNG', 'MHG', 'M6E', 'MJY', 'M6B', 'M6A']


def api():
    return importlib.import_module('icarus_engine.corpus_expansion')


def write(tmp_path, bundle):
    path = tmp_path / 'bundle.json'
    path.write_text(json.dumps(bundle))
    return path


def unavailable(result):
    assert result['status'] == 'UNAVAILABLE'
    assert result['reason'] == 'INVALID_CORPUS_EXPANSION_EVIDENCE'
    assert result['corpora'] == []
    assert result['requested_futures_expansion'] is None
    assert result['execution_authorized'] is False
    assert result['live_feed_qualified'] is False
    assert result['profitability_verified'] is False
    assert 'PRIVATE_MARKER' not in json.dumps(result)


def fault(tmp_path, monkeypatch, mutate):
    bundle = json.loads(BUNDLE.read_bytes())
    artifact = bundle['artifacts'][0]
    report = json.loads(artifact['receipt_json'])
    mutate(report)
    artifact['receipt_json'] = json.dumps(report)
    artifact['receipt_sha256'] = hashlib.sha256(artifact['receipt_json'].encode()).hexdigest()
    # Bypass only the fixed byte trust anchor to independently test semantics.
    monkeypatch.setattr(api(), '_RECEIPT_SHA256', artifact['receipt_sha256'])
    return api().snapshot(now_ns=NOW, path=write(tmp_path, bundle))


def test_actual_native_expansion_warms_all_ten_full_families_in_all_four_workspaces():
    result = api().snapshot(now_ns=NOW)
    assert result['status'] == 'HISTORICAL_EXPANSION_CONSUMPTION_VERIFIED'
    assert result['run_id'] == 39162615234
    assert result['artifact_id'] == 12148939831
    assert result['receipt_sha256'] == '67c948545419792f86200af4139963943f3184a9f726150892921e71b458b8c2'
    assert result['source_commit'] == 'ced31fcfcdf75e4ff2f4181315f462aa5d59a76b'
    assert result['consumer_commit'] == '19093b23a8b4853a6ee3e697029085986d871146'
    corpus, = result['corpora']
    assert corpus['dataset_count'] == 32
    assert corpus['retained_rows'] == 192000
    assert [w['warm_asset_count'] for w in corpus['workspaces']] == [24]*4
    expansion = result['requested_futures_expansion']
    assert expansion['full_roots'] == FULL
    assert expansion['available_symbols'] == FULL + ['MCL', 'MBT']
    assert expansion['unavailable_symbols'] == ABSENT
    for wid in ['cc1','cc2','cc3','cc4']:
        assert expansion['warmed_symbols_by_workspace'][wid] == sorted(FULL + ['MCL','MBT'])
    assert expansion['all_full_families_warmed'] is True
    assert result['historical'] is True and result['no_new_acquisition'] is True
    assert result['profitability_verified'] is result['fresh_feed_access_verified'] is False
    assert corpus['age_seconds'] == NOW//10**9 - corpus['latest_bar_closed_ts']
    assert result['latest_bar_closed_ts'] == corpus['latest_bar_closed_ts']
    public = json.dumps(result)
    for forbidden in ['receipt_json', 'history_sha256', 'private_dir', 'open_profit', 'realized_pnl', '"inputs"', '"open"', '"close"', 'PRIVATE_MARKER']:
        assert forbidden not in public


@pytest.mark.parametrize('field,value', [
    ('source_commit', 'f'*40), ('consumer_commit', 'f'*40),
    ('source_repo', 'other/repo'), ('run_id', 39115319263),
    ('schema_version', 'icarus-corpus-evidence-bundle-v1'),
    ('private_path', '/PRIVATE_MARKER'),
])
def test_envelope_is_exact_and_source_pinned(tmp_path, field, value):
    bundle=json.loads(BUNDLE.read_bytes());bundle[field]=value
    unavailable(api().snapshot(now_ns=NOW,path=write(tmp_path,bundle)))


@pytest.mark.parametrize('kind', ['bytes','hash','artifact','cache','duplicate'])
def test_fixed_artifact_identity_and_exact_bytes_cannot_be_swapped(tmp_path, kind):
    bundle=json.loads(BUNDLE.read_bytes());artifact=bundle['artifacts'][0]
    if kind=='bytes': artifact['receipt_json']+=' '
    elif kind=='hash': artifact['receipt_sha256']='0'*64
    elif kind=='artifact': artifact['artifact_id']=12132181638
    elif kind=='cache': artifact['cache_name']='bars_secondary'
    else: bundle['artifacts'].append(dict(artifact))
    unavailable(api().snapshot(now_ns=NOW,path=write(tmp_path,bundle)))


@pytest.mark.parametrize('kind', [
    'source','consumer','read_hash','read_missing','duplicate_workspace','fake_warm',
    'missing_warm','authority','market','acquisition','raw_payload','private_field',
    'family','micro','available','missing_micro','invent_micro_available',
    'false_full_warm','full_unavailable','warmed_map','warmed_map_missing','metadata_authority',
    'profitability','fresh_feed','false_no_acquisition','enabled','numeric_false',
])
def test_semantic_faults_are_rejected_even_with_matching_byte_hash(tmp_path, monkeypatch, kind):
    def mutate(r):
        e=r['requested_futures_expansion']
        if kind=='source': r['datasets'][0]['source_commit']='f'*40
        elif kind=='consumer': r['workflow_provenance']['consumer_commit']='f'*40
        elif kind=='read_hash': r['read_receipts'][0]['source_sha256']='0'*64
        elif kind=='read_missing': r['read_receipts']=[x for x in r['read_receipts'] if x['consumer_id']!='paper:cc1']
        elif kind=='duplicate_workspace': r['workspaces'][1]=r['workspaces'][0]
        elif kind=='fake_warm': r['workspaces'][0]['assets'][0]['symbol']='MNG'
        elif kind=='missing_warm': r['workspaces'][0]['assets']=[x for x in r['workspaces'][0]['assets'] if x['symbol']!='CL']
        elif kind=='authority': r['execution_authorized']=True
        elif kind=='market': r['market_validation']=True
        elif kind=='acquisition': r['workflow_provenance']['acquisition_performed']=True
        elif kind=='raw_payload': r['raw_payloads_included']=True
        elif kind=='private_field': r['datasets'][0]['private_path']='/PRIVATE_MARKER'
        elif kind=='family': e['full_roots'][0]='ES'
        elif kind=='micro': e['micro_roots'].append('MES')
        elif kind=='available': e['available_symbols'].remove('CL')
        elif kind=='missing_micro': e['unavailable_symbols'].remove('MNG')
        elif kind=='invent_micro_available': e['available_symbols'].append('MNG');e['unavailable_symbols'].remove('MNG')
        elif kind=='false_full_warm': e['all_full_families_warmed']=False
        elif kind=='full_unavailable': e['unavailable_symbols'].append('CL')
        elif kind=='warmed_map': e['warmed_symbols_by_workspace']['cc1'].append('MNG')
        elif kind=='warmed_map_missing': del e['warmed_symbols_by_workspace']['cc4']
        elif kind=='metadata_authority': e['execution_authorized']=True
        elif kind=='profitability': e['profitability_verified']=True
        elif kind=='fresh_feed': e['fresh_feed_access_verified']=True
        elif kind=='false_no_acquisition': e['no_new_acquisition']=False
        elif kind=='enabled': e['enabled']=False
        elif kind=='numeric_false': e['execution_authorized']=0
    unavailable(fault(tmp_path,monkeypatch,mutate))


@pytest.mark.parametrize('kind', ['missing','malformed','oversized','nested','duplicate_keys','symlink'])
def test_file_reader_is_bounded_and_generic(tmp_path, kind):
    p=tmp_path/'bad.json'
    if kind=='malformed': p.write_bytes(b'{bad')
    elif kind=='oversized': p.write_bytes(b' '*(2*1024*1024+1))
    elif kind=='nested': p.write_text('['*10000+'0'+']'*10000)
    elif kind=='duplicate_keys': p.write_text('{"schema_version":"a","schema_version":"b"}')
    elif kind=='symlink':
        try:p.symlink_to(BUNDLE)
        except OSError:pytest.skip('symlinks unavailable')
    unavailable(api().snapshot(now_ns=NOW,path=p))


@pytest.mark.parametrize('clock',[True,-1,1,'today'])
def test_invalid_clock_is_unavailable(clock):
    unavailable(api().snapshot(now_ns=clock))


def test_original_historical_snapshot_and_pins_are_unchanged():
    old=importlib.import_module('icarus_engine.corpus_evidence')
    result=old.snapshot(now_ns=NOW)
    assert old._RUN==39115319263
    assert old._SOURCE_COMMIT=='a6054cb952c428c7cb2fa1cd9841e04f381666e6'
    assert result['status']=='HISTORICAL_CONSUMPTION_VERIFIED'
    assert [c['artifact_id'] for c in result['corpora']]==[12132181638,12132122538,12132291117]


def test_later_observation_ages_historical_data_without_promoting_access():
    initial=api().snapshot(now_ns=NOW);later=api().snapshot(now_ns=NOW+86400*10**9)
    assert later['age_seconds']==initial['age_seconds']+86400
    assert later['live_feed_qualified'] is later['profitability_verified'] is False


def test_self_consistent_warm_map_cannot_hide_a_missing_full_family(tmp_path, monkeypatch):
    def mutate(report):
        workspace=report['workspaces'][0]
        workspace['assets']=[asset for asset in workspace['assets'] if asset['symbol']!='CL']
        workspace['unavailable_assets'].append('CL')
        report['requested_futures_expansion']['warmed_symbols_by_workspace']['cc1'].remove('CL')
    unavailable(fault(tmp_path,monkeypatch,mutate))


def test_missing_micro_must_be_explicit_in_every_workspace(tmp_path, monkeypatch):
    def mutate(report):
        report['workspaces'][0]['unavailable_assets'].remove('MNG')
    unavailable(fault(tmp_path,monkeypatch,mutate))


def test_unavailable_old_three_corpus_envelope_cannot_be_used_as_expansion(tmp_path):
    old=Path(__file__).parents[1]/'icarus_engine'/'corpus-consumption.json'
    unavailable(api().snapshot(now_ns=NOW,path=old))

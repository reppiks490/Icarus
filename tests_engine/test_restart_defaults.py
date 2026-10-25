"""Owner-requested NQ defaults and the explicit ETH exception."""
import copy
import json
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
from types import SimpleNamespace
import os
import shutil
import subprocess
import sys
import socket
from urllib.error import HTTPError
import time

import pytest

from icarus_engine import restart_defaults as defaults
from icarus_engine.assets import REGISTRY
from icarus_engine.runtime import resolve_inputs
from icarus_engine.strategy.inputs import Inputs
from tests_engine.test_workspace_api import workspace_http  # noqa: F401


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def state(tmp_path):
    write(tmp_path / "presets/NQ-20m-ultracoded.json", {
        "tp1_pts": 11, "qty_contracts": 4,
        "_meta": {"timeframe": "10", "chart_type": "heikin_ashi", "session": "rth"},
    })
    write(tmp_path / "inputs.json", {"sl_pts": 33})
    write(tmp_path / "inputs.NQ.json", {"tp1_pts": 19, "qty_contracts": 7,
        "_meta": {"timeframe": "15", "commission": 9}})
    write(tmp_path / "inputs.ES.json", {"tp1_pts": 999, "_meta": {"commission": 3}})
    write(tmp_path / "command_centers/cc1.json", {
        "id": "cc1", "name": "Keep this", "description": "owner workspace",
        "assets": ["NQ", "ES", "SOL", "ETH"], "inputs": {"tp1_pts": 111},
        "chart": {"timeframe": "5"}, "schema_version": 2, "config_revision": 8,
        "asset_overrides": {"ES": {"inputs": {"qty_contracts": 90}}},
    })
    (tmp_path / "command_centers/runtime-power.json").write_bytes(b'keep power exactly')
    (tmp_path / "command_centers/cc1.sqlite3").write_bytes(b'keep journal exactly')
    return tmp_path


def test_plan_uses_actual_saved_nq_precedence_and_has_no_side_effects(state):
    before = {p.relative_to(state): p.read_bytes() for p in state.rglob("*") if p.is_file()}
    plan = defaults.plan_defaults(state)
    assert plan["baseline"]["inputs"]["tp1_pts"] == 19
    assert plan["baseline"]["inputs"]["sl_pts"] == 33
    assert plan["baseline"]["inputs"]["qty_contracts"] == 7
    assert plan["baseline"]["chart"]["timeframe"] == "15"
    assert before == {p.relative_to(state): p.read_bytes() for p in state.rglob("*") if p.is_file()}


def test_apply_copies_nq_values_with_only_eth_exception(state, monkeypatch):
    monkeypatch.setattr(defaults, "ensure_stopped", lambda *args, **kwargs: None)
    original_specs = copy.deepcopy(REGISTRY)
    plan = defaults.plan_defaults(state)
    receipt = defaults.apply_plan(plan)
    assert receipt["status"] == "APPLIED"
    for symbol in ("NQ", "ES", "BTC", "SOL", "ETH"):
        inputs, meta, _ = resolve_inputs(copy.deepcopy(REGISTRY[symbol]), str(state), "nq", "NQ-20m-ultracoded")
        expected = dict(plan["baseline"]["inputs"])
        if symbol == "ETH":
            expected.update(qty_contracts=25, use_session=False)
            assert meta["timeframe"] == "30"
        else:
            assert meta["timeframe"] == "15"
        assert inputs.to_dict() == expected
    assert json.loads((state / "inputs.ES.json").read_text())["_meta"]["commission"] == 3
    profile = json.loads((state / "command_centers/cc1.json").read_text())
    assert profile["assets"] == ["NQ", "ES", "SOL", "ETH"]
    assert profile["name"] == "Keep this" and profile["config_revision"] == 9
    assert profile["inputs"] == plan["baseline"]["inputs"]
    assert profile["asset_overrides"]["ES"]["inputs"] == {}
    assert profile["asset_overrides"]["SOL"]["inputs"] == {}
    assert profile["asset_overrides"]["SOL"]["chart"] == {}
    assert profile["asset_overrides"]["ETH"]["inputs"] == {"qty_contracts": 25, "use_session": False}
    assert profile["asset_overrides"]["ETH"]["chart"]["timeframe"] == "30"
    assert receipt["asset_exceptions"] == {
        "ETH": {"qty_contracts": 25, "use_session": False, "timeframe": "30"},
    }
    assert (state / "command_centers/runtime-power.json").read_bytes() == b'keep power exactly'
    assert (state / "command_centers/cc1.sqlite3").read_bytes() == b'keep journal exactly'
    assert REGISTRY == original_specs
    assert Path(receipt["backup_directory"]).is_dir()


def test_every_main_asset_resolves_to_nq_defaults_with_only_eth_exception(state, monkeypatch):
    from icarus_engine.workspace_universe import dashboard_assets

    monkeypatch.setattr(defaults, "ensure_stopped", lambda *args, **kwargs: None)
    plan = defaults.plan_defaults(state)
    defaults.apply_plan(plan)
    baseline = plan["baseline"]["inputs"]
    symbols = dashboard_assets()
    assert set(symbols) <= set(plan["symbols"])
    for symbol in symbols:
        inputs, meta, _ = resolve_inputs(
            copy.deepcopy(REGISTRY[symbol]), str(state), "nq", defaults.DEFAULT_PRESET
        )
        expected = dict(baseline)
        if symbol == "ETH":
            expected.update(qty_contracts=25, use_session=False)
            assert meta["timeframe"] == "30", symbol
        else:
            assert meta["timeframe"] == plan["baseline"]["chart"]["timeframe"], symbol
        assert inputs.to_dict() == expected, symbol


def test_second_application_is_idempotent_and_template_supplies_future_assets(state, monkeypatch):
    monkeypatch.setattr(defaults, "ensure_stopped", lambda *args, **kwargs: None)
    defaults.apply_plan(defaults.plan_defaults(state))
    before = {p.relative_to(state): p.read_bytes() for p in state.rglob("*") if p.is_file()}
    plan = defaults.plan_defaults(state)
    assert plan["changed_files"] == []
    assert defaults.apply_plan(plan)["status"] == "UNCHANGED"
    assert before == {p.relative_to(state): p.read_bytes() for p in state.rglob("*") if p.is_file()}
    assert defaults.owner_default_overrides(state, "ES")["qty_contracts"] == 7
    for alias in ("ETH", "ETHUSD", "COINBASE:ETHUSD"):
        special = defaults.owner_default_overrides(state, alias)
        assert special["qty_contracts"] == 25 and special["use_session"] is False
        assert special["_meta"]["timeframe"] == "30"
    for alias in ("ES", "MES", "SOL", "SOLUSD", "COINBASE:SOLUSD"):
        ordinary = defaults.owner_default_overrides(state, alias)
        assert ordinary["qty_contracts"] == 7
        assert ordinary["_meta"]["timeframe"] == plan["baseline"]["chart"]["timeframe"]


def test_missing_preset_malformed_file_or_symlink_fails_before_any_write(state):
    (state / "presets/NQ-20m-ultracoded.json").unlink()
    with pytest.raises(ValueError, match="preset"):
        defaults.plan_defaults(state)
    write(state / "presets/NQ-20m-ultracoded.json", {})
    (state / "inputs.ES.json").write_text('{broken')
    with pytest.raises(ValueError, match="JSON"):
        defaults.plan_defaults(state)
    (state / "inputs.ES.json").unlink()
    outside = state.parent / "outside-inputs.json"
    outside.write_text('{}')
    try:
        (state / "inputs.ES.json").symlink_to(outside)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(ValueError, match="symlink"):
        defaults.plan_defaults(state)
    assert outside.read_text() == '{}'


def test_busy_runtime_changed_source_and_partial_write_failure_do_not_leave_partial_config(state, monkeypatch):
    plan = defaults.plan_defaults(state)
    monkeypatch.setattr(defaults, "ensure_stopped", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("still running")))
    with pytest.raises(ValueError, match="still running"):
        defaults.apply_plan(plan)
    monkeypatch.setattr(defaults, "ensure_stopped", lambda *args, **kwargs: None)
    (state / "inputs.NQ.json").write_text('{"qty_contracts":8}')
    with pytest.raises(ValueError, match="changed"):
        defaults.apply_plan(plan)
    plan = defaults.plan_defaults(state)
    before = {p.relative_to(state): p.read_bytes() for p in state.rglob("*") if p.is_file()}
    original = defaults._atomic_write
    calls = []
    def fail_once(path, data):
        if str(path).endswith('inputs.ES.json') and not calls:
            calls.append(True)
            raise OSError('fixture write failed')
        return original(path, data)
    monkeypatch.setattr(defaults, "_atomic_write", fail_once)
    with pytest.raises(OSError, match="fixture"):
        defaults.apply_plan(plan)
    for relative, data in before.items():
        assert (state / relative).read_bytes() == data
    assert not (state / defaults.TEMPLATE_FILE).exists()


def test_live_capture_is_loopback_authenticated_configuration_consistent_and_private(state, capsys):
    values = Inputs().to_dict()
    values.update(tp1_pts=73, qty_contracts=9)
    count = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def do_GET(self):
            assert self.headers['Authorization'] == 'Bearer fixture-owner-token'
            count.append(self.path)
            if self.path=='/api/workspace-runtime':
                body={'schema_version':'icarus.workspace-power.v1','execution_authorized':False}
            elif self.path.startswith('/api/inputs/'):
                body = {'asset':'NQ','base':values,'preset':'runtime-only-preset',
                    'chart':{'timeframe':'10','chart_type':'heikin_ashi','fill_on':'real','security_source':'chart'},
                    'chart_capabilities':{'changing_cache_rows':len(count)}}
            else:
                body = {'symbol':'NQ','tf':10,'chart_type':'heikin_ashi',
                        'fill_on':'real','security_source':'chart','session':'eth'}
            raw = json.dumps(body).encode()
            self.send_response(200)
            self.send_header('Content-Length',str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
    server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread = threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        result = defaults.capture_current(state,port=server.server_port,token='fixture-owner-token')
    finally:
        server.shutdown(); thread.join(3); server.server_close()
    snapshot = json.loads(Path(result['capture_file']).read_text())
    assert snapshot['baseline']['session']=='eth'
    assert snapshot['baseline']['inputs']['tp1_pts']==73
    assert snapshot['baseline']['basis']=='captured_live_main_nq'
    assert count==['/api/workspace-runtime','/api/inputs/NQ','/api/chart/NQ?n=1','/api/inputs/NQ']
    assert 'fixture-owner-token' not in json.dumps(snapshot)
    assert 'fixture-owner-token' not in capsys.readouterr().out
    assert defaults.plan_defaults(state,capture_file=result['capture_file'])['baseline']['inputs']['qty_contracts']==9


def test_capture_rejects_redirect_and_never_forwards_owner_auth(state):
    count = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def do_GET(self):
            count.append(self.path)
            self.send_response(302)
            self.send_header('Location',f'http://127.0.0.1:{self.server.server_port}/other')
            self.send_header('Content-Length','0')
            self.end_headers()
    server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread = threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        with pytest.raises(ValueError,match='redirect'):
            defaults.capture_current(state,port=server.server_port,token='fixture-owner-token')
    finally:
        server.shutdown(); thread.join(3); server.server_close()
    assert count==['/api/workspace-runtime']
    assert not (state/'current-nq-restart-capture.json').exists()


def test_empty_or_tampered_template_is_not_silently_treated_as_no_policy(state):
    write(state/defaults.TEMPLATE_FILE,{})
    with pytest.raises(ValueError,match='identity'):
        defaults.owner_default_overrides(state,'ES')


def test_future_main_and_cc_assets_and_missing_profiles_use_real_startup_defaults(state, monkeypatch):
    from icarus_engine.paper_workspaces import PaperWorkspaceManager, WorkspacePortfolio
    from icarus_engine.runtime import Journal
    monkeypatch.setattr(defaults,'ensure_stopped',lambda *args,**kwargs:None)
    defaults.apply_plan(defaults.plan_defaults(state))
    baseline=defaults.read_default_template(state)['baseline']
    # A future Main asset has no per-asset file to make the test pass accidentally.
    (state/'inputs.BTC.json').unlink()
    values,meta,_=resolve_inputs(copy.deepcopy(REGISTRY['BTC']),str(state),'nq',defaults.DEFAULT_PRESET)
    assert values.to_dict()==baseline['inputs'] and meta['timeframe']=='15'
    existing=(state/'command_centers/cc1.json').read_bytes()
    parent=SimpleNamespace(base_dir=str(state),feeds={})
    manager=PaperWorkspaceManager(parent)
    assert (state/'command_centers/cc1.json').read_bytes()==existing
    fresh=manager.profiles['cc2']
    assert fresh['inputs']==baseline['inputs'] and fresh['chart']==baseline['chart']
    assert fresh['asset_overrides']=={}
    class NoNetwork:
        def __getattr__(self,name):
            raise AssertionError('offline defaults must not call a provider: '+name)
    journal=Journal(':memory:')
    portfolio=WorkspacePortfolio(journal,str(state),workspace=fresh,
        preset=defaults.DEFAULT_PRESET,feeds={'yahoo':NoNetwork(),'coinbase':NoNetwork()})
    try:
        for symbol in ('ES','SOL','ETH'):
            original=copy.deepcopy(REGISTRY[symbol])
            spec,values,_=portfolio._resolved(copy.deepcopy(original))
            expected=dict(baseline['inputs'])
            if symbol == 'ETH':
                expected.update(qty_contracts=25,use_session=False)
                assert spec.chart_tf=='30' and spec.calendar=='crypto'
            else:
                assert spec.chart_tf=='15' and spec.session=='rth'
            assert values.to_dict()==expected
            assert spec.multiplier==original.multiplier and spec.mintick==original.mintick
            assert spec.commission==original.commission and spec.capital==original.capital
        # Later explicit per-asset owner edits remain the last layer.
        fresh['asset_overrides']['SOL']={'inputs':{'qty_contracts':26},'chart':{'timeframe':'60'}}
        spec,values,_=portfolio._resolved(copy.deepcopy(REGISTRY['SOL']))
        assert spec.chart_tf=='60' and values.qty_contracts==26
    finally:
        journal.close()


@pytest.mark.parametrize('action',['--capture-current','--prepare'])
def test_verified_helper_can_capture_before_checkout_and_apply_on_actual_python310(state,action):
    python=os.environ.get('ICARUS_NATIVE_PYTHON310')
    if not python:
        python=sys.executable if sys.version_info[:2]==(3,10) else shutil.which('python3.10')
    if not python:
        pytest.skip('set ICARUS_NATIVE_PYTHON310 for actual Python3.10 command rehearsal')
    values=Inputs().to_dict()
    values.update(tp1_pts=81,qty_contracts=12)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def do_GET(self):
            assert self.headers['Authorization']=='Bearer fixture-owner-token'
            body=({'schema_version':'icarus.workspace-power.v1','execution_authorized':False}
                  if self.path=='/api/workspace-runtime' else
                  {'asset':'NQ','base':values,'preset':'runtime-custom',
                   'session':'eth','chart':{'timeframe':'10','chart_type':'heikin_ashi',
                   'fill_on':'real','security_source':'chart'}})
            raw=json.dumps(body).encode()
            self.send_response(200);self.send_header('Content-Length',str(len(raw)))
            self.end_headers();self.wfile.write(raw)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    source=Path(defaults.__file__).read_text()
    driver="import sys;code=sys.stdin.read();sys.argv=['verified-restart-defaults','--root',sys.argv[1],'--port',sys.argv[2],sys.argv[3]];exec(compile(code,'verified-restart-defaults','exec'),{'__name__':'__main__','__package__':'icarus_engine'})"
    environment=dict(os.environ,PYTHONPATH=str(Path(__file__).resolve().parents[1]),ICARUS_TOKEN='fixture-owner-token',PYTHONDONTWRITEBYTECODE='1')
    try:
        captured=subprocess.run([python,'-S','-c',driver,str(state),str(server.server_port),action],
            input=source,text=True,capture_output=True,env=environment,timeout=30)
    finally:
        server.shutdown();thread.join(3);server.server_close()
    assert captured.returncode==0,captured.stdout+captured.stderr
    receipt=json.loads(captured.stdout)
    assert receipt['status']==('PREPARED' if action=='--prepare' else 'CAPTURED')
    assert 'fixture-owner-token' not in captured.stdout
    # The old engine is stopped; reuse its now-free loopback port for preflight.
    applied=subprocess.run([python,'-S','-m','icarus_engine.restart_defaults','--root',str(state),
        '--port',str(server.server_port),'--capture-file',receipt['capture_file'],'--apply'],
        text=True,capture_output=True,env=environment,timeout=30)
    assert applied.returncode==0,applied.stdout+applied.stderr
    assert json.loads(applied.stdout)['status']=='APPLIED'
    assert json.loads((state/'inputs.ES.json').read_text())['tp1_pts']==81
    sol_settings=json.loads((state/'inputs.SOL.json').read_text())
    nq_settings=json.loads((state/'inputs.NQ.json').read_text())
    assert sol_settings['qty_contracts']==nq_settings['qty_contracts']
    assert sol_settings['use_session']==nq_settings['use_session']
    assert sol_settings['_meta']['timeframe']==nq_settings['_meta']['timeframe']


def test_prepare_uses_active_current_nq(workspace_http,state):
    server,parent,_=workspace_http
    result=defaults.prepare_current(state,port=server.server_port,token='api-owner')
    assert result['status']=='PREPARED'
    assert result['basis']=='captured_live_main_nq'
    assert result['overview']=={'timeframe':parent.runners['NQ'].spec.chart_tf,
        'session':parent.runners['NQ'].spec.session,
        'qty_contracts':parent.runners['NQ'].inputs_base.qty_contracts,
        'asset_exceptions':{
            'ETH':{'timeframe':'30','use_session':False,'qty_contracts':25},
        }}
    capture=Path(result['capture_file'])
    assert json.loads(capture.read_text())['baseline']['inputs']==parent.runners['NQ'].inputs_base.to_dict()
    assert 'api-owner' not in json.dumps(result)


def test_prepare_after_ctrl_c_resolves_saved_nq_and_rejects_missing_source(state):
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    result=defaults.prepare_current(state,port=port)
    assert result['status']=='PREPARED' and result['basis']=='saved_main_nq_resolution'
    assert result['overview']['timeframe']=='15'
    assert result['overview']['qty_contracts']==7
    capture=Path(result['capture_file'])
    saved=json.loads(capture.read_text())
    assert saved['schema_version']==defaults.CAPTURE_SCHEMA
    assert type(saved['prepared_at_ns']) is int and saved['prepared_at_ns']>0
    before=capture.read_bytes()
    (state/'inputs.NQ.json').unlink()
    with pytest.raises(ValueError,match='inputs.NQ.json'):
        defaults.prepare_current(state,port=port)
    assert capture.read_bytes()==before


def test_prepare_treats_loopback_timeout_as_stopped_only_after_exclusive_bind(state, monkeypatch):
    # Windows can time out on a recently closed loopback socket. The helper may
    # use saved settings only after the normal PID and exclusive-bind proof.
    monkeypatch.setattr(defaults.socket, 'create_connection',
                        lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError('TIME_WAIT')))
    result = defaults.prepare_current(state, port=18791)
    assert result['status'] == 'PREPARED'
    assert Path(result['capture_file']).is_file()


def test_safe_does_not_treat_realpath_short_name_expansion_as_reparse_point(tmp_path, monkeypatch):
    # Windows realpath expands 8.3 aliases; the filesystem attribute checks are
    # authoritative for links, while lexical normalization accepts that alias.
    path = tmp_path / 'ordinary.json'
    monkeypatch.setattr(defaults.os.path, 'realpath',
                        lambda *_: (_ for _ in ()).throw(AssertionError('realpath must not gate')))
    assert defaults._safe(path) == path.absolute()


@pytest.mark.parametrize('failure',['authentication','deadline'])
def test_prepare_active_api_failure_never_substitutes_saved_nq(state,failure):
    release=threading.Event()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def do_GET(self):
            if failure=='authentication':
                self.send_response(401);self.send_header('Content-Length','0');self.end_headers()
            else:
                release.wait(2)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    capture=state/'current-nq-restart-capture.json'
    capture.write_bytes(b'previous capture must remain unchanged')
    try:
        expected=HTTPError if failure=='authentication' else TimeoutError
        with pytest.raises(expected):
            defaults.prepare_current(state,port=server.server_port,token='fixture-token',timeout=.05)
    finally:
        release.set();server.shutdown();thread.join(3);server.server_close()
    assert capture.read_bytes()==b'previous capture must remain unchanged'


def test_actual_engine_current_main_nq_api_can_be_captured_without_status_poll(workspace_http,tmp_path):
    server,parent,_=workspace_http
    result=defaults.capture_current(tmp_path,port=server.server_port,token='api-owner')
    baseline=json.loads(Path(result['capture_file']).read_text())['baseline']
    nq=parent.runners['NQ']
    assert baseline['inputs']==nq.inputs_base.to_dict()
    assert baseline['chart']['timeframe']==nq.spec.chart_tf
    assert baseline['session']==nq.spec.session


@pytest.mark.parametrize('source_kind', ['preset', 'capture'])
def test_baseline_source_change_after_planning_fails_before_backup_or_settings_writes(state, monkeypatch, source_kind):
    monkeypatch.setattr(defaults, 'ensure_stopped', lambda *args, **kwargs: None)
    if source_kind == 'capture':
        baseline = defaults.plan_defaults(state)['baseline']
        baseline.update(basis='captured_live_main_nq', captured_at_ns=time.time_ns())
        source = state / 'current-nq-restart-capture.json'
        write(source, {'schema_version': defaults.CAPTURE_SCHEMA, 'asset': 'NQ',
                       'baseline': baseline, 'execution_authorized': False})
        plan = defaults.plan_defaults(state, capture_file=source)
        changed = json.loads(source.read_text())
        changed['baseline']['inputs']['qty_contracts'] += 1
    else:
        source = state / 'presets/NQ-20m-ultracoded.json'
        plan = defaults.plan_defaults(state)
        changed = json.loads(source.read_text())
        changed['qty_contracts'] += 1
    write(source, changed)
    before = {p.relative_to(state): p.read_bytes() for p in state.rglob('*') if p.is_file()}
    with pytest.raises(ValueError, match='source.*changed|changed.*source'):
        defaults.apply_plan(plan)
    assert before == {p.relative_to(state): p.read_bytes() for p in state.rglob('*') if p.is_file()}
    assert not (state / 'audit').exists()

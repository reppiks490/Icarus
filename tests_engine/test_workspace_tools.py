import pytest
from types import SimpleNamespace

from tests_engine.test_command_center_routes import engine


def test_expansion_preserves_inputs_and_chart_and_skips_already_complete():
    from icarus_engine.workspace_tools import expand
    from icarus_engine.workspace_universe import dashboard_assets
    calls = []
    selected = {'cc1':['NQ'], 'cc2':dashboard_assets()}
    def request(path, body=None):
        calls.append((path, body))
        key = path.split('/')[-1]
        if body is not None:
            assert set(body) == {'assets'}
            selected[key] = body['assets']
            return {'ok':True}
        return {'mode':'concurrent_paper','runtime_feed_mode':'file','execution_authorized':False,
                'profile':{'id':key,'assets':selected[key],'runtime_available':True},
                'available_assets':[{'symbol':symbol,'selectable':True} for symbol in dashboard_assets()]}
    assert expand(request, ['cc1','cc2']) == {'cc1':'EXPANDED','cc2':'ALREADY_COMPLETE'}
    assert sum(body is not None for _,body in calls) == 1
    assert selected['cc1'] == dashboard_assets()


@pytest.mark.parametrize('mutate', [
    lambda row: row.update(mode='live'),
    lambda row: row.update(execution_authorized=True),
    lambda row: row.update(runtime_feed_mode='databento'),
    lambda row: row['profile'].update(id='cc4'),
    lambda row: row['profile'].update(runtime_available=False),
    lambda row: row['available_assets'][0].update(selectable=False),
])
def test_expansion_rejects_unsafe_or_unavailable_runtime_without_mutation(mutate):
    from icarus_engine.workspace_tools import expand
    from icarus_engine.workspace_universe import dashboard_assets
    writes = []
    row={'mode':'concurrent_paper','runtime_feed_mode':'file','execution_authorized':False,
         'profile':{'id':'cc1','assets':['NQ'],'runtime_available':True},
         'available_assets':[{'symbol':symbol,'selectable':True} for symbol in dashboard_assets()]}
    mutate(row)
    def request(path,body=None):
        if body is not None: writes.append(body)
        return row
    with pytest.raises(RuntimeError): expand(request,['cc1'])
    assert writes == []


def test_expansion_does_not_claim_success_when_server_retains_old_assets():
    from icarus_engine.workspace_tools import expand
    from icarus_engine.workspace_universe import dashboard_assets
    def request(path,body=None):
        if body is not None:return {'ok':True}
        return {'mode':'concurrent_paper','runtime_feed_mode':'file','execution_authorized':False,
                'profile':{'id':'cc1','assets':['NQ'],'runtime_available':True},
                'available_assets':[{'symbol':symbol,'selectable':True} for symbol in dashboard_assets()]}
    with pytest.raises(RuntimeError,match='readback'): expand(request,['cc1'])


def test_profile_identifiers_are_bounded_before_requests():
    from icarus_engine.workspace_tools import expand
    with pytest.raises(ValueError):expand(lambda *_:pytest.fail('no requests'),['../cc5'])


def test_cli_refuses_to_use_a_fixed_token_when_environment_is_empty(monkeypatch, capsys):
    from icarus_engine import workspace_tools
    monkeypatch.delenv('ICARUS_TOKEN', raising=False)
    monkeypatch.delenv('ICARUS_ADMIN_TOKEN', raising=False)
    monkeypatch.delenv('ADMIN_TOKEN', raising=False)
    monkeypatch.setattr(workspace_tools, 'request', lambda *_args, **_kwargs:pytest.fail('request must not occur without a token'))
    with pytest.raises(SystemExit) as error:
        workspace_tools.main(['status'])
    assert error.value.code == 2
    assert 'ICARUS_TOKEN' in capsys.readouterr().err


def test_engine_cli_refuses_missing_token_before_runtime_start(monkeypatch, capsys):
    from icarus_engine import cli
    monkeypatch.delenv('ICARUS_TOKEN', raising=False)
    monkeypatch.delenv('ICARUS_ADMIN_TOKEN', raising=False)
    monkeypatch.delenv('ADMIN_TOKEN', raising=False)
    monkeypatch.setattr(cli, '_portfolio', lambda *_args, **_kwargs:pytest.fail('runtime must not start without a token'))
    with pytest.raises(SystemExit) as error:
        cli.main(['run'])
    assert error.value.code == 2
    assert 'ICARUS_TOKEN' in capsys.readouterr().err


def test_engine_cli_never_prints_configured_token(monkeypatch, capsys):
    from icarus_engine import cli, server

    class FakeJournal:
        path = 'private-test-journal'
        def log(self, *_args): pass

    class FakePortfolio:
        order = ['NQ']
        def start(self): pass
        def stop(self): pass

    monkeypatch.setenv('ICARUS_TOKEN', 'configured-owner-token-test-only')
    monkeypatch.setattr(cli, 'Journal', lambda *_args, **_kwargs:FakeJournal())
    monkeypatch.setattr(cli, '_portfolio', lambda *_args, **_kwargs:FakePortfolio())
    monkeypatch.setattr(cli, '_base_dir', lambda:'private-test-root')
    monkeypatch.setattr(server, 'serve', lambda *_args, **_kwargs:None)

    assert cli.main(['run', '--assets', 'NQ']) == 0
    output = capsys.readouterr().out
    assert 'configured-owner-token-test-only' not in output
    assert 'authentication token configured' in output.lower()


def test_local_requests_use_real_runtime_and_authentication(engine):
    from icarus_engine.workspace_tools import request
    srv, _ = engine
    state = request(srv.server_port, 'owner-test', '/api/command-centers/cc1')
    assert state['profile']['id'] == 'cc1'
    assert state['runtime_feed_mode'] == 'file'
    with pytest.raises(RuntimeError, match='401'):
        request(srv.server_port, 'invalid-token', '/api/engine-control')


def test_restart_refuses_to_claim_an_occupied_engine_port(engine, monkeypatch, tmp_path):
    from icarus_engine import workspace_tools
    srv, _ = engine
    monkeypatch.setattr(workspace_tools.subprocess, 'run', lambda *args,**kwargs:None)
    monkeypatch.setattr(workspace_tools.subprocess, 'Popen', lambda *_args,**_kwargs:pytest.fail('must not spawn'))
    with pytest.raises(RuntimeError, match='occupied'):
        workspace_tools.restart(SimpleNamespace(root=str(tmp_path),port=srv.server_port,token='owner-test',keep_selection=False))

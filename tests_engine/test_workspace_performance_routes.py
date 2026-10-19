import time
from types import SimpleNamespace

import pytest

from tests_engine.test_command_center_routes import engine
from icarus_engine.paper_workspaces import _PROFILE_DEFAULTS
from icarus_engine.runtime import Journal
from icarus_engine.workspace_universe import dashboard_assets, ORIGINAL_ASSETS


def test_every_default_workspace_contains_original_and_expanded_assets():
    for row in _PROFILE_DEFAULTS:
        assert set(ORIGINAL_ASSETS) <= set(row['assets'])
        assert set(dashboard_assets()) <= set(row['assets'])
        assert len(row['assets']) == len(set(row['assets']))


@pytest.mark.parametrize('profile_id', ['cc1', 'cc2', 'cc3', 'cc4'])
def test_performance_reads_only_selected_persisted_journal(engine, profile_id):
    srv, request = engine
    code, _ = request('/api/command-centers/'+profile_id+'/performance')
    assert code == 503
    journals = []
    try:
        for index, key in enumerate(('cc1', 'cc2', 'cc3', 'cc4'), 1):
            journal = Journal(':memory:'); journals.append(journal)
            ts = int(time.time())-10
            trade = SimpleNamespace(entry_id='saved', direction=1, qty=1, entry_price=10.,
                                    entry_ts=ts-60, exit_price=11., exit_ts=ts,
                                    exit_comment='persisted', profit=index*10.)
            journal.add_trade('NQ', trade, True)
            journal.add_trade('NQ', SimpleNamespace(**{**trade.__dict__, 'entry_id':'replay','profit':999.}), False)
            runner = SimpleNamespace(spec=SimpleNamespace(capital=10000))
            srv.command_centers.portfolios[key] = SimpleNamespace(journal=journal,runner_list=lambda:[runner])
        code, data = request('/api/command-centers/'+profile_id+'/performance?profile=cc4')
        assert code == 200
        assert data['workspace_id'] == profile_id
        assert data['realized_pnl'] == int(profile_id[-1])*10
        assert data['closed_pieces'] == 1
        assert data['trades'][0]['entry_id'] == 'saved'
        assert data['paper_only'] is True
        assert data['execution_authorized'] is False
        assert data['ratios']['capital'] == 10000
        code, _ = request('/api/command-centers/'+profile_id+'/performance', host='evil.example')
        assert code == 403
    finally:
        srv.command_centers.portfolios.clear()
        for journal in journals: journal.close()


def test_performance_script_is_served_on_each_dashboard_and_legacy_navigation(engine):
    _, request = engine
    for key in ('cc1','cc2','cc3','cc4'):
        code, page = request('/dashboards/'+key)
        assert code == 200
        assert '/workspace-performance-ui.js' in page
        assert 'id="expand-assets"' in page
    code, script = request('/workspace-performance-ui.js')
    assert code == 200
    assert '/performance' in script
    code, legacy = request('/')
    assert code == 200
    for key in ('cc1','cc2','cc3','cc4'):
        assert '/dashboards/'+key in legacy

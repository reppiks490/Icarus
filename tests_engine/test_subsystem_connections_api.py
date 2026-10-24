"""Actual native connections through authenticated Main and selected APIs."""
import time
import sqlite3
import threading

import pytest

from tests_engine.test_workspace_api import workspace_http  # noqa: F401


@pytest.mark.parametrize('scope',['main','cc1','cc2','cc3','cc4'])
def test_native_connection_reader_has_selected_identity_and_no_get_sampling(workspace_http,monkeypatch,scope):
    server,parent,request=workspace_http
    path='/api/subsystem-connections' if scope=='main' else f'/api/command-centers/{scope}/panels/subsystem-connections'
    code,data,_=request(path)
    assert code==200,data
    assert data['schema_version']=='icarus-nexus-aion-v1'
    assert data['workspace_id']==scope
    assert data['execution_authorized'] is False
    assert data['production_decision_authorized'] is False
    if scope!='main':assert data['config_revision']==server.command_centers.profiles[scope]['config_revision']
    service=(server.subsystem_connections if scope=='main' else server.workspace_panels._runtimes[scope].subsystem_connections)
    monkeypatch.setattr(service,'tick',lambda:(_ for _ in ()).throw(AssertionError('GET must not sample')))
    assert request(path)[0]==200
    assert data['aion']['event_count']==0


def test_native_connection_routes_preserve_auth_scope_and_selector_boundaries(workspace_http):
    server,_,request=workspace_http
    assert request('/api/subsystem-connections',token=None)[0]==401
    assert request('/api/command-centers/cc1/panels/subsystem-connections',token=None)[0]==401
    assert request('/api/subsystem-connections?asset=NQ')[0]==400
    assert request('/api/command-centers/cc1/panels/subsystem-connections?asset=NQ')[0]==400
    assert request('/api/subsystem-connections',extra_headers={'X-Icarus-Workspace':'cc1'})[0]==503
    assert request('/api/command-centers/cc1/panels/subsystem-connections',extra_headers={'X-Icarus-Workspace':'cc2'})[0]==409
    code,created,_=request('/admin/access/add',body={'label':'native-observer'})
    assert code==201
    token=created['user']['token']
    assert request('/api/subsystem-connections',token=token)[0]==200
    assert request('/api/command-centers/cc1/panels/subsystem-connections',token=token)[0]==200


def test_real_published_caches_reach_native_health_and_durable_scoped_memory(workspace_http):
    server,parent,request=workspace_http
    selected=server.command_centers.portfolios['cc1']
    for portfolio in (parent,selected):
        for runner in portfolio.runner_list():
            with runner.lock:runner.publish_read_views()
    assert request('/api/command-centers/cc1/panels/subsystem-connections')[0]==200
    selected_service=server.workspace_panels._runtimes['cc1'].subsystem_connections
    for service in (server.subsystem_connections,selected_service):service.tick()
    main=request('/api/subsystem-connections')[1]
    cc=request('/api/command-centers/cc1/panels/subsystem-connections')[1]
    assert {row['symbol'] for row in main['assets']}=={'NQ','ES'}
    assert {row['symbol'] for row in cc['assets']}=={'NQ'}
    for data in (main,cc):
        assert data['aion']['event_count']>0,data
        assert data['aion']['chain_verified'] is True,data
        assert len(data['nexus']['plane_hash'])==64,data
        assert 'price' not in data['assets'][0]
        assert data['production_decision_authorized'] is False
    assert main['nexus']['plane_hash']!=cc['nexus']['plane_hash']


def test_native_selected_worker_drains_with_existing_power_off_and_main_stays_available(workspace_http,monkeypatch):
    server,parent,request=workspace_http
    path='/api/command-centers/cc1/panels/subsystem-connections'
    assert request(path)[0]==200
    service=server.workspace_panels._runtimes['cc1'].subsystem_connections
    closed=[]
    original=service.close
    def close():
        original()
        closed.append(True)
    monkeypatch.setattr(service,'close',close)
    metadata=request('/api/workspace-runtime')[1]
    revision=next(row['revision'] for row in metadata['workspaces'] if row['id']=='cc1')
    assert request('/admin/command-centers/cc1/runtime',body={'enabled':False,'expected_revision':revision})[0]==202
    deadline=time.monotonic()+3
    while time.monotonic()<deadline:
        state=next(row for row in request('/api/workspace-runtime')[1]['workspaces'] if row['id']=='cc1')
        if state['runtime_state']=='OFF':break
        time.sleep(.01)
    assert state['runtime_state']=='OFF',state
    assert closed==[True]
    assert request(path)[0]==503
    assert request('/api/subsystem-connections')[0]==200
    assert request('/status/public')[0]==200


def test_selected_native_observation_is_not_relabelled_after_configuration_changes(workspace_http):
    server,_,request=workspace_http
    portfolio=server.command_centers.portfolios['cc1']
    for runner in portfolio.runner_list():
        with runner.lock:runner.publish_read_views()
    path='/api/command-centers/cc1/panels/subsystem-connections'
    assert request(path)[0]==200
    service=server.workspace_panels._runtimes['cc1'].subsystem_connections
    service.tick()
    before=request(path)[1]
    assert before['observed_config_revision']==before['config_revision']==0
    server.command_centers.update_asset('cc1','NQ',{'expected_revision':0,'inputs':{'tp1_pts':17}})
    after=request(path)[1]
    assert after['config_revision']==1
    assert after['observed_config_revision']==0
    assert after['state']=='UNAVAILABLE'
    assert after['assets']==[] and after['nexus']['plane_hash'] is None
    assert 'OBSERVED_CONFIGURATION_MISMATCH' in after['warnings']
    assert after['aion']['event_count']==before['aion']['event_count']
    service.tick()
    recovered=request(path)[1]
    assert recovered['observed_config_revision']==recovered['config_revision']==1
    assert 'OBSERVED_CONFIGURATION_MISMATCH' not in recovered['warnings']
    assert recovered['assets']


def test_busy_native_sqlite_write_does_not_delay_main_or_selected_http_reads(workspace_http,monkeypatch):
    server,parent,request=workspace_http
    portfolio=server.command_centers.portfolios['cc1']
    runner=portfolio.runners['NQ']
    with runner.lock:runner.publish_read_views()
    path='/api/command-centers/cc1/panels/subsystem-connections'
    assert request(path)[0]==200
    service=server.workspace_panels._runtimes['cc1'].subsystem_connections
    service.tick()
    entered=threading.Event()
    original=service._store.append
    def append(event):
        entered.set()
        return original(event)
    monkeypatch.setattr(service._store,'append',append)
    runner._public_views[0][0]['bar_index']+=1
    database=sqlite3.connect(service.store_path)
    database.execute('BEGIN IMMEDIATE')
    worker=threading.Thread(target=service.tick)
    worker.start()
    try:
        assert entered.wait(2),'native worker did not reach its blocked write'
        began=time.monotonic()
        assert request(path)[0]==200
        assert request('/api/subsystem-connections')[0]==200
        assert request('/status/public')[0]==200
        assert time.monotonic()-began<1,'HTTP reads waited on native SQLite work'
    finally:
        database.rollback()
        database.close()
        worker.join(5)
    assert not worker.is_alive()


@pytest.mark.parametrize('scope',['main','cc1'])
def test_native_subsystems_page_renders_actual_cached_native_receipts(workspace_http,scope):
    from tests_engine.test_workspace_dashboard_browser import common_page
    server,parent,request=workspace_http
    portfolio=parent if scope=='main' else server.command_centers.portfolios[scope]
    for runner in portfolio.runner_list():
        with runner.lock:runner.publish_read_views()
    path='/api/subsystem-connections' if scope=='main' else f'/api/command-centers/{scope}/panels/subsystem-connections'
    assert request(path)[0]==200
    service=server.subsystem_connections if scope=='main' else server.workspace_panels._runtimes[scope].subsystem_connections
    service.tick()
    expected=request(path)[1]
    assert expected['aion']['chain_verified'] is True
    with common_page(workspace_http,scope,pause_periodic=True) as (page,_):
        page.evaluate("()=>setView('subsystems')")
        page.wait_for_function("()=>document.querySelector('#subsystem-chain')?.textContent.includes('verified at observation')")
        assert expected['nexus']['plane_hash'] in page.locator('#subsystem-nexus').inner_text()
        assert str(expected['aion']['event_count'])+' persisted context receipts' in page.locator('#subsystem-aion').inner_text()
        assert scope.upper() in page.locator('#subsystem-title').inner_text()
        assert not page.icarus_errors

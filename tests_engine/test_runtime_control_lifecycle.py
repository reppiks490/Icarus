"""Live browser regressions for admitted power changes and stored audit identity."""
import json
from tests_engine.test_workspace_api import workspace_http  # noqa: F401
from tests_engine.test_workspace_dashboard_browser import common_page


def test_power_retries_only_a_rejected_transient_admission(workspace_http):
    with common_page(workspace_http, 'cc4', pause_periodic=True) as (page, base):
        page.wait_for_function("()=>!document.querySelector('#workspace-power-cc4').disabled")
        calls=[]
        def transient(route):
            calls.append(route.request.post_data_json)
            if len(calls)==1:
                route.fulfill(status=409,content_type='application/json',body=json.dumps({'detail':'Workspace is busy; retry after its current operation.'}))
            else:
                route.continue_()
        page.route(base+'/admin/command-centers/cc4/runtime',transient)
        page.locator('#workspace-power-cc4').click()
        page.wait_for_function("()=>document.querySelector('[data-power-state=cc4]').textContent==='OFF'",timeout=4000)
        assert len(calls)==2
        assert calls[0]==calls[1], 'retry must keep the original requested state and revision'
        assert calls[0]['expected_revision']==0
        assert page.locator('[data-power-error=cc4]').inner_text()==''


def test_system_snapshot_does_not_claim_verification_of_running_revision(workspace_http):
    with common_page(workspace_http, 'main', pause_periodic=True) as (page, _):
        page.locator('[data-v="system"]').click()
        text=page.locator('#view').inner_text().lower()
        assert 'recorded repository audit' in text
        assert 'recorded-head failures' in text
        assert 'does not verify the running checkout' in text
        assert 'current-head failures' not in text

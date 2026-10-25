"""Real pointer and drawer bounds on the wrapped dashboard header."""
import pytest

from tests_engine.test_workspace_api import workspace_http  # noqa: F401
from tests_engine.test_workspace_dashboard_browser import common_page


@pytest.mark.parametrize("detail", ["light", "rich"])
def test_wrapped_settings_trigger_remains_clickable_at_800_by_600(workspace_http, detail):
    with common_page(workspace_http, "main", viewport={"width": 800, "height": 600}) as (page, _):
        page.emulate_media(reduced_motion="no-preference")
        summary = page.locator('.experience-settings > summary')
        drawer = page.locator('.experience-settings > div')
        summary.click()
        page.locator('#experienceVisualDetail').select_option(detail)
        drawer.evaluate("async el=>{await Promise.all(el.getAnimations().map(a=>a.finished.catch(()=>{})))}")
        page.wait_for_function("""()=>{const p=document.querySelector('.experience-settings > div').getBoundingClientRect();return p.top>=0&&p.bottom<=600}""", timeout=2000)
        geometry = page.evaluate("""() => {
          const summary = document.querySelector('.experience-settings > summary');
          const anchor = summary.getBoundingClientRect();
          const panel = summary.nextElementSibling.getBoundingClientRect();
          return {anchor:anchor.toJSON(),panel:panel.toJSON(),
            triggerReceivesPointer:summary.contains(document.elementFromPoint(anchor.left+anchor.width/2,anchor.top+anchor.height/2)),
            styles:summary.nextElementSibling.getAttribute("style"),offsetParent:summary.nextElementSibling.offsetParent?.outerHTML.slice(0,150)};
        }""")
        assert geometry["anchor"]["top"] > 90, geometry
        assert geometry["triggerReceivesPointer"], geometry
        assert 0 <= geometry["panel"]["left"] < geometry["panel"]["right"] <= 800, geometry
        assert 0 <= geometry["panel"]["top"] < geometry["panel"]["bottom"] <= 600, geometry
        page.locator('#experienceReplay').scroll_into_view_if_needed()
        replay = page.locator('#experienceReplay').bounding_box()
        assert replay and 0 <= replay["y"] < replay["y"] + replay["height"] <= 600, replay
        after_scroll = page.evaluate("""() => {
          const summary = document.querySelector('.experience-settings > summary');
          const anchor = summary.getBoundingClientRect(), panel = summary.nextElementSibling.getBoundingClientRect();
          const hit = document.elementFromPoint(anchor.left+anchor.width/2,anchor.top+anchor.height/2);
          return {anchor:anchor.toJSON(),panel:panel.toJSON(),hit:hit?.outerHTML,
            triggerReceivesPointer:summary.contains(hit)};
        }""")
        assert after_scroll["triggerReceivesPointer"], after_scroll
        anchor=after_scroll["anchor"]
        page.mouse.click(anchor["left"]+anchor["width"]/2, anchor["top"]+anchor["height"]/2)
        assert page.locator('.experience-settings').get_attribute('open') is None
        assert not page.icarus_errors, page.icarus_errors


def test_open_settings_reanchors_after_header_layout_changes(workspace_http):
    with common_page(workspace_http, 'main', viewport={'width': 800, 'height': 600}) as (page, _):
        summary = page.locator('.experience-settings > summary')
        summary.click()
        page.wait_for_timeout(350)
        page.evaluate("""()=>{
          const controls=document.querySelector('.experience-controls');
          controls.parentElement.style.paddingTop='70px';
        }""")
        page.wait_for_timeout(150)
        geometry=page.evaluate("""()=>{
          const el=document.querySelector('.experience-settings > summary'), r=el.getBoundingClientRect();
          const panel=el.nextElementSibling.getBoundingClientRect();
          return {trigger:el.contains(document.elementFromPoint(r.left+r.width/2,r.top+r.height/2)),
            anchor:r.toJSON(),panel:panel.toJSON()};
        }""")
        assert geometry['trigger'], geometry
        assert 0 <= geometry['panel']['top'] < geometry['panel']['bottom'] <= 600, geometry
        assert not page.icarus_errors

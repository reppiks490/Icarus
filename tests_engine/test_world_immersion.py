"""Presentation-only invariants for full-dashboard ICARUS immersion."""
from pathlib import Path
import os
import re
import shutil

import pytest


ROOT = Path(__file__).parents[1]
IMMERSION = ROOT / "icarus_engine" / "world-immersion.js"
DASHBOARD = ROOT / "icarus_engine" / "dashboard.html"
CSS = ROOT / "icarus_engine" / "experience-ui.css"


def test_immersion_runtime_has_no_market_or_control_io():
    source = IMMERSION.read_text(encoding="utf-8")
    forbidden = (
        "fetch(",
        "XMLHttpRequest",
        "WebSocket",
        "sendBeacon",
        "/api/",
        "/admin/",
        "localStorage",
        "sessionStorage",
    )
    for token in forbidden:
        assert token not in source, f"presentation runtime must not perform I/O: {token}"


def test_immersion_runtime_is_loaded_before_dashboard_world_motion():
    html = DASHBOARD.read_text(encoding="utf-8")
    immersion = html.index('<script src="/world-immersion.js"></script>')
    motion = html.index('<script src="/world-motion.js"></script>')
    experience = html.index('<script src="/experience-ui.js"></script>')
    assert immersion < motion < experience


def test_immersion_runtime_keeps_motion_and_visibility_gates():
    source = IMMERSION.read_text(encoding="utf-8")
    for guard in (
        "prefers-reduced-motion: reduce",
        "root.dataset.motion==='live'",
        "root.dataset.experience==='cinematic'",
        "!document.hidden",
        "root.dataset.introActive!=='true'",
    ):
        assert guard in source


def test_adaptive_brain_visuals_follow_world_tokens():
    source = (ROOT / "icarus_engine" / "brain-ui.js").read_text(encoding="utf-8")
    for fixed in (
        "rgba(86,225,255,.16)",
        "rgba(145,92,255,.12)",
        "rgba(95,232,255,.35)",
        "background:#67e8f9",
    ):
        assert fixed not in source
    assert "var(--view-accent" in source



def test_visual_keyframe_names_are_unique():
    source = CSS.read_text(encoding="utf-8")
    names = re.findall(r"@keyframes\s+([\w-]+)", source)
    duplicates = sorted({name for name in names if names.count(name) > 1})
    assert duplicates == [], f"duplicate animation names can silently override choreography: {duplicates}"


def test_immersion_runtime_keeps_hard_visual_budgets():
    source = IMMERSION.read_text(encoding="utf-8")
    for budget in (
        "slice(0,18)",
        "edges.length>=24",
        "slice(0,80)",
        "'<i></i>'.repeat(12)",
    ):
        assert budget in source
    assert "setInterval(" not in source


def test_visual_layers_keep_accessibility_fallbacks():
    source = CSS.read_text(encoding="utf-8")
    assert "@media (prefers-reduced-motion:reduce)" in source
    assert "@media (forced-colors:active)" in source
    assert 'data-visual-resolved="light"' in source
    assert ".world-inspection-field" in source
    assert ".world-handoff" in source


def test_immersion_idle_cards_do_not_reschedule_refresh_and_external_changes_coalesce():
    try:
        from playwright.sync_api import Error as PlaywrightError, sync_playwright
    except ImportError:
        if os.environ.get("ICARUS_REQUIRE_WORKSPACE_BROWSER") == "1":
            raise
        pytest.skip("optional Playwright unavailable")

    with sync_playwright() as runtime:
        try:
            browser = runtime.chromium.launch(
                headless=True,
                executable_path=os.environ.get("ICARUS_BROWSER_BINARY") or shutil.which("chromium"),
            )
        except PlaywrightError as error:
            if os.environ.get("ICARUS_REQUIRE_WORKSPACE_BROWSER") == "1":
                raise
            pytest.skip("optional Chromium unavailable: " + str(error).splitlines()[0])
        try:
            page = browser.new_page(reduced_motion="reduce")
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.set_content('<div id="tabs"></div><main id="view">' + ''.join(
                f'<section class="asset"><h2>Instrument {index}</h2><span class="px tnum">100</span></section>'
                for index in range(35)
            ) + '</main>')
            page.evaluate("""() => {
              const schedule=window.requestAnimationFrame.bind(window);
              window.immersionRefreshes=0;
              window.requestAnimationFrame=callback=>schedule(time=>{
                if(callback.name==='refresh')immersionRefreshes++;
                callback(time);
              });
            }""")
            page.add_script_tag(path=str(IMMERSION))
            result = page.evaluate("""async () => {
              const frames=async count=>{
                for(let i=0;i<count;i++)await new Promise(resolve=>requestAnimationFrame(resolve));
              };
              await frames(5);
              const view=document.querySelector('#view'),cards=[...view.querySelectorAll('.asset')];
              let indexChanges=0;
              const observer=new MutationObserver(records=>{
                indexChanges+=records.filter(record=>record.target.matches?.('.world-panel-index')).length;
              });
              observer.observe(view,{childList:true,subtree:true});
              const idleStart=immersionRefreshes;
              await frames(5);
              const idleRefreshes=immersionRefreshes-idleStart,idleIndexChanges=indexChanges;
              const externalStart=immersionRefreshes;
              cards[0].querySelector('.px').textContent='101';
              await Promise.resolve();
              cards[1].querySelector('.px').textContent='102';
              await Promise.resolve();
              await frames(5);
              observer.disconnect();
              return {idleRefreshes,idleIndexChanges,externalRefreshes:immersionRefreshes-externalStart,
                retained:cards.every((card,index)=>card===view.querySelectorAll('.asset')[index]),
                prices:cards.slice(0,2).map(card=>card.querySelector('.px').textContent),
                firstIndex:cards[0].querySelector('.world-panel-index').textContent};
            }""")
            print("35-card immersion refresh activity:", result)
            assert result["idleRefreshes"] == result["idleIndexChanges"] == 0, result
            assert result["externalRefreshes"] == 1, result
            assert result["retained"] and result["prices"] == ["101", "102"], result
            assert result["firstIndex"] == "P01 / 35 · INSTRUMENT", result
            assert errors == []
        finally:
            browser.close()


def test_scroll_focus_bounds_layout_reads_without_disabling_scroll_feedback():
    try:
        from playwright.sync_api import Error as PlaywrightError, sync_playwright
    except ImportError:
        if os.environ.get("ICARUS_REQUIRE_WORKSPACE_BROWSER") == "1":
            raise
        pytest.skip("optional Playwright unavailable")

    with sync_playwright() as runtime:
        try:
            browser = runtime.chromium.launch(
                headless=True,
                executable_path=os.environ.get("ICARUS_BROWSER_BINARY") or shutil.which("chromium"),
            )
        except PlaywrightError as error:
            if os.environ.get("ICARUS_REQUIRE_WORKSPACE_BROWSER") == "1":
                raise
            pytest.skip("optional Chromium unavailable: " + str(error).splitlines()[0])
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 800})
            page.set_content('<div id="tabs"></div><main id="view">' + "".join(
                f'<section class="asset" style="height:180px"><h2>Instrument {index}</h2><span class="px tnum">100</span></section>'
                for index in range(35)
            ) + "</main>")
            page.evaluate("""() => Object.assign(document.documentElement.dataset, {
              world:'divine', experience:'cinematic', motion:'live', visualResolved:'rich'
            })""")
            page.add_script_tag(path=str(IMMERSION))
            page.wait_for_function("() => document.querySelectorAll('.world-topology circle').length >= 2")
            reads = page.evaluate("""async () => {
              const original=Element.prototype.getBoundingClientRect;
              window.__panelGeometryReads=0;
              Element.prototype.getBoundingClientRect=function(){
                if(this.matches?.('[data-world-topology-node]'))window.__panelGeometryReads++;
                return original.call(this);
              };
              const end=performance.now()+700;
              let step=0;
              while(performance.now()<end){
                scrollTo(0,step++%5*500);
                await new Promise(resolve=>requestAnimationFrame(resolve));
              }
              scrollTo({top:document.documentElement.scrollHeight,behavior:'instant'});
              await new Promise(resolve=>setTimeout(resolve,300));
              return {reads:window.__panelGeometryReads,phase:document.documentElement.dataset.scrollPhase};
            }""")
            assert reads["reads"] <= 300, reads
            assert reads["reads"] > 0, reads
            assert reads["phase"] == "abyss", reads
        finally:
            browser.close()

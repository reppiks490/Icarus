"""Connections must retain readable records and usable controls on narrow screens."""
import os
import shutil

import pytest

from tests_engine.test_workspace_api import workspace_http  # noqa: F401


@pytest.mark.parametrize("width", [320, 390])
def test_connections_long_alias_and_controls_fit_narrow_viewport(workspace_http, width):
    playwright = pytest.importorskip("playwright.sync_api")
    server, _, _ = workspace_http
    alias = "Account_" + "A" * 192
    server.account_connections.upsert(dict(id="layout_account", alias=alias,
        platform="manual_inventory", environment="simulated", firm="independent",
        program="paper", credential_refs={}))
    base = f"http://127.0.0.1:{server.server_port}"
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True,
            executable_path=os.environ.get("ICARUS_BROWSER_BINARY") or shutil.which("chromium"))
        try:
            page = browser.new_page(viewport={"width": width, "height": 844})
            errors, writes = [], []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("request", lambda request: writes.append(request.url) if request.method != "GET" else None)
            page.route("**/*", lambda route: route.continue_() if route.request.url.startswith(base + "/") else route.abort())
            page.goto(base + "/connections", wait_until="load")
            page.locator('[name="owner_token"]').fill("api-owner")
            page.get_by_role("button", name="Refresh account inventory", exact=True).click()
            heading = page.locator('[aria-label="Account connections"] h3')
            heading.wait_for()
            assert heading.text_content() == alias
            bounds = page.evaluate("""() => {
              const heading = document.querySelector('[aria-label="Account connections"] h3');
              const range = document.createRange(); range.selectNodeContents(heading);
              return {width:innerWidth,scrollWidth:document.documentElement.scrollWidth,
                aliasLines:[...range.getClientRects()].map(r=>({left:r.left,right:r.right})),
                controls:[...document.querySelectorAll('#connections input,#connections select,#connections button')]
                  .map(el=>({name:el.name||el.id||el.textContent,left:el.getBoundingClientRect().left,right:el.getBoundingClientRect().right}))};
            }""")
            assert bounds["scrollWidth"] <= width, bounds
            assert len(bounds["aliasLines"]) > 1, bounds
            assert all(0 <= line["left"] < line["right"] <= width for line in bounds["aliasLines"]), bounds
            assert all(0 <= control["left"] < control["right"] <= width for control in bounds["controls"]), bounds
            assert not errors and not writes, (errors, writes)
        finally:
            browser.close()

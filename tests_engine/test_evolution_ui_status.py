"""Exercise status styling through the shipped Evolution UI's public loader."""

import json
from html.parser import HTMLParser
from pathlib import Path
import shutil
import subprocess

import pytest


STATUS_CASES = [
    ("verified", "b"),
    ("qualified", "b"),
    ("active", "b"),
    ("success", "b"),
    ("green", "b"),
    ("VeRiFiEd", "b"),
    ("SUCCESS", "b"),
    ("unverified", "w"),
    ("UNVERIFIED", "w"),
    ("UNSUCCESSFUL", "w"),
    ("NOT_VERIFIED", "w"),
    ("SUCCESS_PENDING", "w"),
    ("verified_extra", "w"),
    ("observed", "w"),
    ("staged", "w"),
    ("degraded", "w"),
    ("retired", "w"),
    ("not_started", "w"),
    ("syncing", "w"),
    ("disabled", "w"),
    ("info", "w"),
    ("warn", "w"),
    ("unknown", "w"),
    ("", "w"),
    (None, "w"),
    ("error", "r"),
    ("failed", "r"),
    ("blocked", "r"),
    ("rejected", "r"),
    ("BLOCKED_VERIFIED", "r"),
    ("VERIFIED_ERROR", "r"),
    ("FAILED_SUCCESS", "r"),
    ("SUCCESS_REJECTED", "r"),
]


class StatusClasses(HTMLParser):
    def __init__(self):
        super().__init__()
        self.classes = []

    def handle_starttag(self, tag, attrs):
        classes = dict(attrs).get("class", "").split()
        if "chip" in classes or "evo-sub" in classes:
            self.classes.append(classes)


@pytest.fixture(scope="module")
def rendered_statuses():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required to execute the shipped Evolution UI")
    source = Path(__file__).resolve().parents[1] / "icarus_engine" / "evolution-ui.js"
    script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const statuses = JSON.parse(fs.readFileSync(0, 'utf8'));
const panel = {innerHTML: ''};
let state;
let requests = 0;
const context = {
  window: {},
  document: {querySelector(selector) {
    assert.equal(selector, '#evolutionPanel');
    return panel;
  }},
  localStorage: {getItem() {return 'fixture-token';}},
  async fetch(url, options) {
    assert.equal(url, '/api/evolution');
    assert.equal(options.headers.Authorization, 'Bearer fixture-token');
    requests += 1;
    return {ok: true, async json() {return state;}};
  },
};
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), context);
(async () => {
  const rendered = [];
  for (const status of statuses) {
    state = {
      status,
      subsystems: {argus: {status, title: 'Fixture subsystem'}},
      events: [{severity: status, category: 'AUDIT', title: 'Fixture event'}],
    };
    panel.innerHTML = '';
    await context.window.loadEvolution();
    rendered.push(panel.innerHTML);
  }
  assert.equal(requests, statuses.length);
  process.stdout.write(JSON.stringify(rendered));
})().catch(error => {console.error(error); process.exitCode = 1;});
"""
    result = subprocess.run(
        [node, "-e", script, str(source)],
        input=json.dumps([status for status, _ in STATUS_CASES]),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize(
    "index,case", list(enumerate(STATUS_CASES)), ids=[str(s) for s, _ in STATUS_CASES]
)
def test_status_classes_in_rendered_evolution_panel(rendered_statuses, index, case):
    status, expected = case
    parsed = StatusClasses()
    parsed.feed(rendered_statuses[index])
    # Sync badge, subsystem card, subsystem badge, and event severity badge.
    assert parsed.classes == [
        ["chip", expected],
        ["evo-sub", expected],
        ["chip", expected],
        ["chip", expected],
    ], f"Incorrect rendered status classes for {status!r}"

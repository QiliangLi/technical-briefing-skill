from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "site" / "atlas-interaction-v3.js"


def _run_node(source: str) -> dict:
    result = subprocess.run(
        ["node", "-e", source],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_atlas_url_identity_preserves_meaningful_query_parameters() -> None:
    output = _run_node(
        f"""
        global.window = {{location: {{href: 'https://example.test/'}}}};
        global.norm = value => String(value || '').toLowerCase();
        const fs = require('fs');
        const vm = require('vm');
        vm.runInThisContext(fs.readFileSync({json.dumps(str(SCRIPT))}, 'utf8'));
        const first = canonicalIdentity({{url: 'https://example.com/paper?id=one'}});
        const second = canonicalIdentity({{url: 'https://example.com/paper?id=two'}});
        const tracked = canonicalIdentity({{url: 'https://example.com/paper?id=one&utm_source=newsletter'}});
        process.stdout.write(JSON.stringify({{first, second, tracked}}));
        """
    )

    assert output["first"] != output["second"]
    assert output["tracked"] == output["first"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_pan_zoom_captures_pointer_only_after_drag_threshold() -> None:
    output = _run_node(
        f"""
        const fs = require('fs');
        const vm = require('vm');
        const handlers = {{}};
        const captures = [];
        const svg = {{
          dataset: {{}},
          classList: {{add() {{}}, remove() {{}}}},
          addEventListener(type, handler) {{ handlers[type] = handler; }},
          setPointerCapture(pointerId) {{ captures.push(pointerId); }},
          getBoundingClientRect() {{ return {{left: 0, top: 0, width: 100, height: 100}}; }}
        }};
        global.window = {{location: {{href: 'https://example.test/'}}}};
        global.state = {{view: {{x: 0, y: 0, w: 100, h: 100}}, drag: null}};
        global.$ = () => svg;
        global.clamp = (value, low, high) => Math.max(low, Math.min(high, value));
        global.applyView = () => {{}};
        global.zoomGraph = () => {{}};
        global.norm = value => String(value || '').toLowerCase();
        vm.runInThisContext(fs.readFileSync({json.dumps(str(SCRIPT))}, 'utf8'));
        initPanZoom();
        handlers.pointerdown({{button: 0, pointerId: 6, clientX: 10, clientY: 10, target: {{closest: () => ({{}})}}}});
        const nodeStartedDrag = state.drag !== null;
        handlers.pointerdown({{button: 0, pointerId: 7, clientX: 10, clientY: 10, target: {{closest: () => null}}}});
        const afterDown = captures.length;
        handlers.pointermove({{pointerId: 7, clientX: 13, clientY: 13}});
        const afterClickSizedMove = captures.length;
        handlers.pointermove({{pointerId: 7, clientX: 18, clientY: 18}});
        process.stdout.write(JSON.stringify({{nodeStartedDrag, afterDown, afterClickSizedMove, afterDrag: captures.length}}));
        """
    )

    assert output == {
        "nodeStartedDrag": False,
        "afterDown": 0,
        "afterClickSizedMove": 0,
        "afterDrag": 1,
    }

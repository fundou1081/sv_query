"""[iter_364 / PLAN P62.1] finding 局部 review artifact 测试。"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = """
module leaf(input a, b, output y);
  assign y = a & b;
endmodule
module top(input a, b, output y0, y1);
  leaf u0(.a(a), .b(b), .y(y0));
  leaf u1(.a(a), .y(y1));
endmodule
"""


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    sv = tmp_path / "t.sv"
    sv.write_text(SRC)
    r = subprocess.run(["sv_query", "verify", "structural", "-f", str(sv), "--json"],
                       capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    assert r.returncode == 0, r.stderr[-300:]
    findings = tmp_path / "findings.json"
    findings.write_text(r.stdout)
    return sv, findings


def test_review_render_svg_html(tmp_path):
    sv, findings = _setup(tmp_path)
    svg = tmp_path / "r.svg"
    page = tmp_path / "r.html"
    r = subprocess.run(
        ["sv_query", "review", "render", str(findings), "-f", str(sv),
         "--svg", str(svg), "--html", str(page), "--json"],
        capture_output=True, text=True, timeout=60, cwd=str(ROOT),
    )
    assert r.returncode == 0, r.stderr[-500:]
    data = json.loads(r.stdout)
    assert data["ok"] is True and data["missing"] == ["top.u1.b"]
    text = svg.read_text()
    assert text.startswith("<svg") and "top.u1.b" in text
    assert "sibling instance(s) missing port" in page.read_text()


def test_review_render_unknown_finding(tmp_path):
    sv, findings = _setup(tmp_path)
    r = subprocess.run(
        ["sv_query", "review", "render", str(findings), "--finding-id", "nope",
         "-f", str(sv), "--json"],
        capture_output=True, text=True, timeout=60, cwd=str(ROOT),
    )
    assert r.returncode != 0
    d = json.loads(r.stdout)
    assert d["ok"] is False


def test_review_render_is_deterministic(tmp_path):
    sv, findings = _setup(tmp_path)
    a = tmp_path / "a.svg"
    b = tmp_path / "b.svg"
    for out in (a, b):
        r = subprocess.run(
            ["sv_query", "review", "render", str(findings), "-f", str(sv), "--svg", str(out)],
            capture_output=True, text=True, timeout=60, cwd=str(ROOT),
        )
        assert r.returncode == 0, r.stderr[-300:]
    assert a.read_text() == b.read_text()

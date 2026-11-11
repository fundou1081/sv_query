"""[P91/A] filelist prune CLI."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_filelist_prune_cli(tmp_path):
    top = tmp_path / "top.sv"
    child = tmp_path / "child.sv"
    unused = tmp_path / "unused.sv"
    top.write_text("module top; child u(); endmodule\n")
    child.write_text("module child; endmodule\n")
    unused.write_text("module unused; endmodule\n")
    fl = tmp_path / "all.f"
    fl.write_text("\n".join(str(p) for p in (top, child, unused)) + "\n")
    r = subprocess.run(["sv_query", "filelist", "prune", "--filelist", str(fl),
                        "--top", "top", "--json"],
                       capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    assert r.returncode == 0, r.stderr[-300:]
    data = json.loads(r.stdout)
    selected = {Path(p).name for p in data["result"]["selected_files"]}
    assert selected == {"top.sv", "child.sv"}
    assert data["result"]["selected_count"] == 2


def test_filelist_prune_output_and_top_missing(tmp_path):
    top = tmp_path / "top.sv"
    child = tmp_path / "child.sv"
    unused = tmp_path / "unused.sv"
    top.write_text("module top; child u(); endmodule\n")
    child.write_text("module child; endmodule\n")
    unused.write_text("module unused; endmodule\n")
    fl = tmp_path / "all.f"
    fl.write_text("\n".join(str(p) for p in (top, child, unused)) + "\n")

    out = tmp_path / "pruned.f"
    r = subprocess.run(["sv_query", "filelist", "prune", "--filelist", str(fl),
                        "--top", "nope", "--output", str(out), "--apply", "--json"],
                       capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    assert r.returncode == 0, r.stderr[-300:]
    data = json.loads(r.stdout)["result"]
    assert data["reason"] == "top_not_found"
    assert data["selected_count"] == 3
    assert len(out.read_text().splitlines()) == 3


def _prune_args(fl, out, *extra):
    return ["sv_query", "filelist", "prune", "--filelist", str(fl),
            "--top", "top", "--output", str(out), *extra, "--json"]


def test_filelist_prune_dry_run_and_safe_overwrite(tmp_path):
    top = tmp_path / "top.sv"; top.write_text("module top; endmodule\n")
    fl = tmp_path / "all.f"; fl.write_text(str(top) + "\n")

    out = tmp_path / "pruned.f"
    r = subprocess.run(_prune_args(fl, out), capture_output=True, text=True,
                       timeout=60, cwd=str(ROOT))
    assert r.returncode == 0, r.stderr[-300:]
    data = json.loads(r.stdout)["result"]
    assert data["written"] is False
    assert data["dry_run"] is True
    assert not out.exists()

    # RTL suffix is never a valid output.
    victim = tmp_path / "victim.sv"
    victim.write_text("module victim; endmodule\n")
    r = subprocess.run(_prune_args(fl, victim, "--apply"), capture_output=True,
                       text=True, timeout=60, cwd=str(ROOT))
    assert r.returncode == 1
    assert victim.read_text() == "module victim; endmodule\n"

    # Existing file requires force; force leaves a backup.
    out.write_text("old\n")
    r = subprocess.run(_prune_args(fl, out, "--apply"), capture_output=True,
                       text=True, timeout=60, cwd=str(ROOT))
    assert r.returncode == 1
    assert out.read_text() == "old\n"
    r = subprocess.run(_prune_args(fl, out, "--apply", "--force"),
                       capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    assert r.returncode == 0, r.stderr[-300:]
    assert out.read_text().strip() == str(top)
    assert (tmp_path / "pruned.f.bak").read_text() == "old\n"

#!/usr/bin/env python3
"""Build a snapshot + environment for the svq_query tool.

P111: one command from a fresh project to a query-ready snapshot. It does not
modify project files; snapshot/env artifacts go to --snapshot-dir.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INSTALL = ROOT / "tools" / "agent" / "install_svq_query_tool.sh"


def die(msg: str) -> "NoReturn":
    print(f"setup_snapshot: {msg}", file=sys.stderr)
    raise SystemExit(2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True,
                    help="source file or project directory passed to snapshot save")
    ap.add_argument("--tag", required=True, help="snapshot tag")
    ap.add_argument("--filelist", default=None,
                    help="optional .f/.fl filelist for a multi-file project")
    ap.add_argument("--snapshot-dir", default=None,
                    help="default: $SVQ_SNAPSHOT_DIR or ~/.svq/snapshots")
    ap.add_argument("--source-root", default=None,
                    help="root for evidence file paths; default: project dir")
    ap.add_argument("--install-tool", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    tag = args.tag
    if not tag or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-" for c in tag):
        die("tag must contain only letters, digits, underscore, dot or dash")

    path = Path(args.path).expanduser().resolve()
    if not path.exists():
        die(f"source path not found: {path}")
    filelist = Path(args.filelist).expanduser().resolve() if args.filelist else None
    if filelist and not filelist.is_file():
        die(f"filelist not found: {filelist}")

    snapshot_dir = Path(
        args.snapshot_dir
        or os.environ.get("SVQ_SNAPSHOT_DIR")
        or Path.home() / ".svq" / "snapshots"
    ).expanduser().resolve()
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    if args.source_root:
        source_root = Path(args.source_root).expanduser().resolve()
    elif filelist:
        files = []
        for line in filelist.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith(("//", "#")):
                continue
            if line.startswith(("-", "+")):
                continue
            f = Path(line.strip('"').strip("'"))
            if not f.is_absolute():
                f = filelist.parent / f
            files.append(f.resolve())
        if files:
            source_root = Path(os.path.commonpath([str(f) for f in files]))
            if source_root.is_file():
                source_root = source_root.parent
        else:
            source_root = path if path.is_dir() else path.parent
    else:
        source_root = path if path.is_dir() else path.parent

    env = os.environ.copy()
    env["SVQ_SNAPSHOT_DIR"] = str(snapshot_dir)
    bin_path = env.get("SVQ_QUERY_BIN") or shutil.which("sv_query")
    if not bin_path:
        die("sv_query not found on PATH (set SVQ_QUERY_BIN)")

    cmd = [bin_path, "snapshot", "save", str(path), "--tag", tag, "--json"]
    if filelist:
        cmd += ["--filelist", str(filelist)]
    proc = subprocess.run(cmd, cwd=str(source_root), env=env,
                          capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr[-2000:])
        die(f"snapshot save failed with rc={proc.returncode}")
    snap = snapshot_dir / f"{tag}.json"
    if not snap.is_file() or snap.stat().st_size == 0:
        die(f"snapshot was not written: {snap}")

    meta = {
        "tag": tag,
        "snapshot": str(snap),
        "snapshot_dir": str(snapshot_dir),
        "source_root": str(source_root),
        "source": str(path),
        "filelist": str(filelist) if filelist else None,
        "query_bin": str(bin_path),
    }
    meta_path = snapshot_dir / f"{tag}.meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    env_path = snapshot_dir / f"{tag}.env.sh"
    env_path.write_text(
        "export SVQ_SNAPSHOT_DIR=%s\n" % shlex.quote(str(snapshot_dir))
        + "export SVQ_SOURCE_ROOT=%s\n" % shlex.quote(str(source_root))
        + "export SVQ_QUERY_BIN=%s\n" % shlex.quote(str(bin_path))
    )

    if args.install_tool:
        install = subprocess.run(["bash", str(INSTALL)], capture_output=True, text=True)
        if install.returncode != 0:
            sys.stderr.write(install.stderr[-2000:])
            die("tool install failed")

    result = dict(meta, meta_path=str(meta_path), env_path=str(env_path),
                  snapshot_bytes=snap.stat().st_size)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"snapshot: {snap}")
        print(f"source:   {source_root}")
        print(f"env:      source {env_path}")
        if args.install_tool:
            print("tool:     installed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

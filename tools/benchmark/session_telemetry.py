#!/usr/bin/env python3
"""[P90.3] Extract real DSH session telemetry for a workspace.

The agent's final `queries` list is self-reported and lossy. This reads the DSH
session JSONL (zstd) and reports actual tool durations, sv_query commands,
tokens, and wall/model residual. It does not modify the workspace.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

SESSIONS = Path.home() / ".dsh" / "sessions"


def _session_dir(workspace: Path) -> Path:
    resolved = str(workspace.resolve())
    key = "--" + resolved.lstrip("/").replace("/", "-") + "--"
    direct = SESSIONS / key
    if direct.is_dir():
        return direct
    # /tmp may be reported as /private/tmp; try both spellings.
    alt = "--" + resolved.replace("/private", "").replace("/", "-") + "--"
    alt_path = SESSIONS / alt
    if alt_path.is_dir():
        return alt_path
    raise FileNotFoundError(f"session dir not found for {workspace}")


def _latest(session_dir: Path) -> Path:
    files = sorted(session_dir.glob("session-*/session.v4.jsonl.zstd"),
                   key=lambda p: p.stat().st_mtime)
    if not files:
        raise FileNotFoundError(f"no session log in {session_dir}")
    return files[-1]


def _events(path: Path) -> list[dict]:
    text = subprocess.run(["zstd", "-dc", str(path)], capture_output=True,
                          text=True, check=True).stdout
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def extract(workspace: Path) -> dict:
    path = _latest(_session_dir(workspace))
    ev = _events(path)
    calls: dict[str, tuple[str, str]] = {}
    call_time: dict[str, int] = {}
    jobs: dict[str, int] = {}
    results: dict[str, int] = {}
    for x in ev:
        t, data = x["type"], x.get("data", {})
        if t == "tool/call":
            cid = data["callId"]
            calls[cid] = (data.get("name", ""), data.get("arguments", ""))
            call_time[cid] = x["time"]
        elif t == "job/settled":
            cid = (data.get("toolCall") or {}).get("callId")
            if cid:
                jobs[cid] = data["finishedAt"] - data["startedAt"]
        elif t == "tool/result":
            cid = data.get("toolCallId")
            if cid:
                results[cid] = x["time"]
    start = next(x["time"] for x in ev if x["type"] == "turn/start")
    end = next(x["time"] for x in ev if x["type"] == "turn/end")
    usage = [x["data"].get("usage", {}) for x in ev
             if x["type"] == "assistant/message"]
    tokens = {k: sum(u.get(k, 0) for u in usage) for k in
              ("inputTokens", "outputTokens", "cacheReadTokens",
               "cacheWriteTokens", "totalTokens")}
    tools = []
    total = 0
    for cid, (name, args) in calls.items():
        dur = jobs.get(cid)
        if dur is None and cid in results:
            dur = results[cid] - call_time.get(cid, results[cid])
        dur = max(0, int(dur or 0))
        total += dur
        cmd = ""
        if name == "bash":
            try:
                cmd = json.loads(args).get("command", "")
            except json.JSONDecodeError:
                cmd = str(args)
        tools.append({"name": name, "duration_ms": dur,
                      "command": cmd})
    return {
        "workspace": str(workspace),
        "session": str(path),
        "wall_ms": end - start,
        "tool_ms": total,
        "model_residual_ms": end - start - total,
        "steps": len(usage),
        "tokens": tokens,
        "tools": len(tools),
        "sv_query_calls": sum(1 for t in tools if "sv_query" in t["command"]),
        "tool_detail": tools,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workspace", type=Path)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    data = extract(args.workspace)
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

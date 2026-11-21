#!/usr/bin/env python3
"""P193.8: product runtime must not import network/telemetry clients.

Scans only `src/` (the installed product). Development tools may use network
for cloning benchmarks; they are outside the shipped runtime.
"""
from __future__ import annotations

import argparse
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NETWORK_MODULES = {"requests", "urllib", "http", "socket", "aiohttp", "httpx", "websocket"}
TELEMETRY_WORDS = ("posthog", "sentry", "analytics", "mixpanel", "segment_io", "telemetry_upload")


def scan(root: Path = ROOT) -> list[str]:
    issues = []
    for path in (root / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(text)
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
            for name in names:
                if name in NETWORK_MODULES:
                    issues.append(f"{path}: network import {name}")
        low = text.lower()
        for word in TELEMETRY_WORDS:
            if word in low:
                issues.append(f"{path}: telemetry marker {word}")
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args(argv)
    issues = scan(Path(args.root))
    if issues:
        for issue in issues[:30]:
            print(f"FAIL\t{issue}")
        print(f"no-telemetry: FAIL ({len(issues)} issues)")
        return 1
    print("no-telemetry: PASS (no network/telemetry imports in src/)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

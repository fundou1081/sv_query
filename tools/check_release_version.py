#!/usr/bin/env python3
"""P195.4 — fail unless pyproject/session/tag versions agree.

Used by .github/workflows/release.yml before build/publish. Locally:
    python3 tools/check_release_version.py --tag v0.3.6
"""
from __future__ import annotations

import argparse
import os
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _session_version(root: Path) -> str:
    sys.path.insert(0, str(root / "src"))
    try:
        from sv_query.session import PACKAGE_VERSION  # noqa: PLC0415
    finally:
        sys.path.pop(0)
    return PACKAGE_VERSION


def _identity_version(root: Path) -> str:
    sys.path.insert(0, str(root / "src"))
    try:
        from sv_query.trace.core.cache.build_identity import BuildIdentity
    finally:
        sys.path.pop(0)
    return BuildIdentity(source_hash="release-check").sv_query_version


def check_versions(root: Path = ROOT, tag: str | None = None) -> tuple[str, str]:
    """Return (pyproject_version, tag) after validating all identities."""
    with open(root / "pyproject.toml", "rb") as fh:
        pyproject = tomllib.load(fh)["project"]["version"]
    session = _session_version(root)
    identity = _identity_version(root)
    if pyproject != session or pyproject != identity:
        raise ValueError(
            f"version mismatch: pyproject={pyproject!r} session={session!r} "
            f"BuildIdentity={identity!r}")
    if tag is None:
        tag = os.environ.get("GITHUB_REF_NAME")
    if tag and tag.startswith("v"):
        if tag[1:] != pyproject:
            raise ValueError(
                f"version mismatch: tag={tag!r} pyproject={pyproject!r}")
    return pyproject, tag or ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default=None,
                        help="tag to verify (vX.Y.Z); default: GITHUB_REF_NAME")
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args(argv)
    try:
        version, tag = check_versions(Path(args.root), args.tag)
    except (OSError, ValueError, KeyError) as exc:
        print(f"release version check failed: {exc}", file=sys.stderr)
        return 1
    print(f"release version ok: {version} (tag={tag or 'not-a-tag'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

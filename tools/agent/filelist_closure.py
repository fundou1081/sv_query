#!/usr/bin/env python3
"""P165.4: build a filelist from a FuseSoC CAPI=2 .core dependency graph.

This is an *adapter* for projects that use .core files; it is deliberately not
part of the query core.  It resolves the target filesets, follows `depend`
entries, applies core `mapping` entries / the profile mapping, removes
include-only headers from the compile list, and emits +incdir+ lines.

Usage:
  python3 tools/agent/filelist_closure.py \
    --root ~/my_dv_proj/openrtl/opentitan \
    --core hw/ip/uart/uart.core --top uart \
    --profile tools/agent/filelist_profiles/opentitan_uart.json \
    --output /tmp/uart_closure.f --json

The output is a candidate, not a semantic proof: it must still be elaborated
(`snapshot save --filelist ...`) before use.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - reported as an actionable error
    print("filelist_closure: PyYAML is required (pip install pyyaml)", file=sys.stderr)
    raise SystemExit(2)


def _norm(name: str) -> str:
    """Normalize a CAPI name: strip the :version suffix."""
    return re.sub(r":\d+(?:\.\d+)*$", "", str(name).strip())


def _selected_filesets(core: dict[str, Any], target: str) -> list[str]:
    targets = core.get("targets") or {}
    tgt = targets.get(target) or targets.get("default") or {}
    names: list[str] = []
    for item in tgt.get("filesets", []) or []:
        if isinstance(item, str):
            if "?" in item:  # optional tool-specific fileset
                continue
            names.append(item.strip())
        elif isinstance(item, dict):
            for key, value in item.items():
                if "?" in key:
                    continue
                names.append(value)
    return names


def _files_from_entry(entry: Any) -> list[str]:
    if isinstance(entry, str):
        return [entry]
    if isinstance(entry, dict):
        for key, value in entry.items():
            if "?" in key:
                continue
            return [value] if isinstance(value, str) else []
    return []


class CoreIndex:
    def __init__(self, root: Path, profile: dict[str, Any]):
        self.root = root
        self.profile = profile
        self.cores: dict[str, tuple[dict[str, Any], Path]] = {}
        self.mapping: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        # Deterministic: sorted paths. A later duplicate wins, but UART's root
        # has one canonical core per name in normal checkouts.
        for path in sorted(self.root.rglob("*.core")):
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
            except (OSError, yaml.YAMLError):
                continue
            if not isinstance(data, dict) or not data.get("name"):
                continue
            name = _norm(data["name"])
            self.cores[name] = (data, path)
        # profile mapping is authoritative; otherwise collect core mappings.
        for source, target in (self.profile.get("mapping") or {}).items():
            self.mapping[_norm(source)] = _norm(target)
        mapping_core = self.profile.get("mapping_core")
        if mapping_core:
            self._add_mapping_from(_norm(mapping_core))
        else:
            for name in sorted(self.cores):
                self._add_mapping_from(name, only_if_absent=True)

    def _add_mapping_from(self, name: str, only_if_absent: bool = False) -> None:
        if name not in self.cores:
            return
        for source, target in (self.cores[name][0].get("mapping") or {}).items():
            source, target = _norm(source), _norm(target)
            if only_if_absent and source in self.mapping:
                continue
            self.mapping[source] = target

    def resolve(self, name: str) -> str:
        name = _norm(name)
        return self.mapping.get(name, name)

    def closure(self, start: str, target: str = "default") -> "Closure":
        core_name = _norm(start)
        if core_name not in self.cores:
            # accept a path to a .core file
            p = Path(start)
            if not p.is_absolute():
                p = self.root / p
            if p.is_file():
                data = yaml.safe_load(p.read_text(encoding="utf-8"))
                core_name = _norm(data["name"])
                self.cores[core_name] = (data, p.resolve())
        return Closure(self, core_name, target)


class Closure:
    def __init__(self, index: CoreIndex, start: str, target: str):
        self.index = index
        self.target = target
        self.files: list[Path] = []
        self.headers: list[Path] = []
        self.incdirs: list[Path] = []
        self.visited: set[tuple[str, str | None]] = set()
        self.missing: dict[str, str] = {}
        self._walk(start, None)

    def _walk(self, name: str, fileset: str | None) -> None:
        original = _norm(name)
        name = self.index.resolve(original)
        if name not in self.index.cores:
            self.missing[original] = "core not found"
            return
        key = (name, fileset)
        if key in self.visited:
            return
        self.visited.add(key)
        data, path = self.index.cores[name]
        filesets = data.get("filesets") or {}
        if fileset:
            names = [fileset] if fileset in filesets else []
            if not names:
                self.missing[f"{original}:{fileset}"] = "fileset not found"
        else:
            names = _selected_filesets(data, self.target)
            if not names:
                # no target: use all RTL filesets
                names = [n for n in filesets if "rtl" in n.lower()]
        for fs in names:
            if fs not in filesets:
                self.missing[f"{name}:{fs}"] = "fileset not found"
                continue
            spec = filesets[fs] or {}
            for dep in spec.get("depend", []) or []:
                self._walk(dep, None)
            for entry in spec.get("files", []) or []:
                for rel in _files_from_entry(entry):
                    fp = (path.parent / rel).resolve()
                    if fp.suffix in (".svh", ".vh"):
                        self.headers.append(fp)
                        self.incdirs.append(fp.parent)
                    elif fp.suffix in (".sv", ".v"):
                        self.files.append(fp)
                        self.incdirs.append(fp.parent)
                    else:
                        # keep non-RTL files out of the compile list
                        continue

    def apply_profile(self) -> None:
        excludes = self.index.profile.get("exclude") or []
        includes = self.index.profile.get("include") or []
        extra_incdirs = self.index.profile.get("incdirs") or []
        if excludes:
            self.files = [f for f in self.files
                          if not any(fnmatch.fnmatch(str(f), pat) for pat in excludes)]
            self.headers = [f for f in self.headers
                            if not any(fnmatch.fnmatch(str(f), pat) for pat in excludes)]
        for rel in includes:
            fp = (self.index.root / rel).resolve()
            if fp.is_file() and fp.suffix in (".sv", ".v"):
                self.files.append(fp)
                self.incdirs.append(fp.parent)
        for rel in extra_incdirs:
            fp = (self.index.root / rel).resolve()
            if fp.is_dir():
                self.incdirs.append(fp)
        self.files = list(dict.fromkeys(self.files))
        self.incdirs = list(dict.fromkeys(self.incdirs))

    def prune(self, top: str) -> None:
        """Use the existing top-reachable pruner; candidate, not a proof."""
        import importlib.util
        mod_path = Path(__file__).resolve().parents[2] / "src" / "trace" / "core" / "top_prune.py"
        spec = importlib.util.spec_from_file_location("_svq_top_prune", mod_path)
        mod = importlib.util.module_from_spec(spec)
        import sys as _sys
        _sys.modules["_svq_top_prune"] = mod
        spec.loader.exec_module(mod)
        sources = {str(f): f.read_text(encoding="utf-8", errors="replace")
                   for f in self.files}
        result = mod.prune_sources(sources, top)
        self.files = [Path(f) for f in result.selected]

    def write(self, output: Path) -> None:
        lines = [f"+incdir+{p}" for p in self.incdirs if p.is_dir()]
        lines += [str(p) for p in self.files]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def as_dict(self) -> dict[str, Any]:
        return {
            "files": len(self.files),
            "headers": len(self.headers),
            "incdirs": len(self.incdirs),
            "missing": self.missing,
            "missing_count": len(self.missing),
        }


def _load_profile(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="project source root")
    ap.add_argument("--core", required=True, help=".core path or CAPI core name")
    ap.add_argument("--target", default="default")
    ap.add_argument("--profile", default=None, help="JSON profile (mapping/exclude/include/incdirs)")
    ap.add_argument("--prune-top", default=None,
                    help="optional top module for conservative reachability pruning")
    ap.add_argument("--output", required=True, help="output .f/.fl path")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        print(f"source root not found: {root}", file=sys.stderr)
        return 2
    out = Path(args.output).expanduser().resolve()
    if out.suffix.lower() not in (".f", ".fl"):
        print("output must end in .f or .fl", file=sys.stderr)
        return 2
    profile = _load_profile(args.profile)
    index = CoreIndex(root, profile)
    closure = index.closure(args.core, args.target)
    closure.apply_profile()
    if args.prune_top:
        closure.prune(args.prune_top)
    closure.write(out)
    result = dict(closure.as_dict(), output=str(out), core=str(args.core),
                  target=args.target, profile=args.profile,
                  prune_top=args.prune_top)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"wrote {out}: {result['files']} compile files, "
              f"{result['incdirs']} incdirs, {result['missing_count']} missing")
    return 0 if not result["missing"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

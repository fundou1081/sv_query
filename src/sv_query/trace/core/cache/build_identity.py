"""BuildIdentity — single source for graph-cache keys (P194.2a).

A cache key is only as trustworthy as the inputs in it. This module centralizes
every graph-affecting input; commands must never assemble cache keys manually.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from importlib import metadata

from sv_query.session import PACKAGE_VERSION

GRAPH_SEMANTICS_VERSION = "1"
GRAPH_CAPABILITY = "graph"


def _version(package: str) -> str:
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return "unknown"


@dataclass(frozen=True)
class BuildIdentity:
    """All inputs that can change the serialized graph."""

    source_hash: str
    include_dirs: tuple[str, ...] = ()
    preprocess_macros: bool = True
    inject_timescale: bool = True
    top_modules: tuple[str, ...] = ()
    target_module: str | None = None
    bit_bridge: str = "one"
    cache_schema: str = ""
    graph_semantics: str = GRAPH_SEMANTICS_VERSION
    pyslang_version: str = field(default_factory=lambda: _version("pyslang"))
    sv_query_version: str = field(default_factory=lambda: PACKAGE_VERSION)

    def canonical(self) -> dict:
        return {
            "source_hash": self.source_hash,
            "include_dirs": sorted(self.include_dirs),
            "preprocess_macros": self.preprocess_macros,
            "inject_timescale": self.inject_timescale,
            "top_modules": sorted(self.top_modules),
            "target_module": self.target_module,
            "bit_bridge": self.bit_bridge,
            "cache_schema": self.cache_schema,
            "graph_semantics": self.graph_semantics,
            "pyslang_version": self.pyslang_version,
            "sv_query_version": self.sv_query_version,
        }

    def key(self) -> str:
        raw = json.dumps(self.canonical(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def manifest(self) -> dict:
        return {
            "capabilities": [GRAPH_CAPABILITY],
            "graph_semantics": self.graph_semantics,
            "cache_schema": self.cache_schema,
            "build_identity": self.canonical(),
        }

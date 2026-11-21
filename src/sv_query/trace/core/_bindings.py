"""Optional pyslang bindings override (P194.1).

Development machines may build pyslang bindings outside site-packages. This
must be explicit and environment-driven; never hardcode an author's home path.
"""
from __future__ import annotations

import os
import sys

ENV_VAR = "SVQ_PYSLANG_BINDINGS"


def add_bindings_from_env() -> str | None:
    """Insert ``SVQ_PYSLANG_BINDINGS`` into sys.path when set and valid."""
    path = os.environ.get(ENV_VAR)
    if not path or not os.path.isdir(path):
        return None
    if path not in sys.path:
        sys.path.insert(0, path)
    return path

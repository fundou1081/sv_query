#!/usr/bin/env python3
"""
CLI wrapper - run with: python run_cli.py dataflow --help
"""
import sys
from pathlib import Path

# 添加项目根目录到 sys.path (包含 src/)
_project_root = Path(__file__).parent
_src_dir = _project_root / "src"
sys.path.insert(0, str(_src_dir))

from src.cli.main import app
app()

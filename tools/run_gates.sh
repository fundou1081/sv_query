#!/usr/bin/env bash
# Single canonical gate entry (P158.10). CI and local use the same command.
# [P158.12 / R-024] -p no:randomly 现在真正生效: pytest-randomly 已入 dev 依赖
# (pyproject addopts 默认也禁用); 随机顺序需显式 "-p randomly"。
set -euo pipefail
cd "$(dirname "$0")/.."

python3 -m pytest sim/tests/ -m "not opensource" -q -p no:randomly
python3 tools/check_docs.py
python3 tools/check_except_pass.py
python3 tools/check_semantic_regex.py
python3 tools/check_cli_layers.py
python3 tools/gen_cli_surface.py --check
if [[ -n "${SVQ_GATE_BASE:-}" ]]; then
  python3 tools/check_crap.py --base "${SVQ_GATE_BASE}"
else
  python3 tools/check_crap.py
fi
python3 tools/check_plan.py

#!/bin/bash
# 跑 sv_query 双版本测试 (pyslang 10 + 11)
# 用法: ./run_dual_version_tests.sh

set -e

SV_DIR="$HOME/my_dv_proj/sv_query"

if [ ! -d "$SV_DIR" ]; then
    echo "ERROR: sv_query not found at $SV_DIR"
    exit 1
fi

cd "$SV_DIR"

run_tests() {
    local VERSION=$1
    echo ""
    echo "=========================================="
    echo "Testing with pyslang $VERSION"
    echo "=========================================="
    pip install --quiet "pyslang==$VERSION"
    python3 -c "import pyslang; print(f'Installed pyslang {pyslang.__version__}')"
    python3 -m pytest sim/tests/ -q 2>&1 | tail -3
}

run_tests "10.0.0"
run_tests "11.0.0"

echo ""
echo "=========================================="
echo "✅ Both versions tested"
echo "=========================================="

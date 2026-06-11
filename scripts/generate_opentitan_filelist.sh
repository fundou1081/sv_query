#!/bin/bash
# generate_opentitan_filelist.sh - 生成 opentitan IP block 的 filelist + stub
#
# Usage: ./generate_opentitan_filelist.sh <opentitan_root> <ip_name>
#
# Example:
#   ./generate_opentitan_filelist.sh ~/my_dv_proj/opentitan tlul
#   ./generate_opentitan_filelist.sh ~/my_dv_proj/opentitan prim
#
# 输出:
#   /tmp/opentitan_stub/top_pkg.sv    - minimal stub
#   /tmp/opentitan_<ip_name>.f        - 完整 filelist
#
# 跑命令:
#   python run_cli.py protocol detect --filelist /tmp/opentitan_<ip_name>.f --module <module_name>

set -e

OT_ROOT="${1:-$HOME/my_dv_proj/opentitan}"
IP_NAME="${2:-tlul}"
STUB_DIR="/tmp/opentitan_stub"
FILELIST="/tmp/opentitan_${IP_NAME}.f"

if [ ! -d "$OT_ROOT/hw/ip" ]; then
    echo "❌ Error: $OT_ROOT 不像 opentitan 仓库 (缺 hw/ip/)"
    exit 1
fi

if [ ! -d "$OT_ROOT/hw/ip/$IP_NAME" ]; then
    echo "❌ Error: $OT_ROOT/hw/ip/$IP_NAME 不存在"
    echo "   试试: ls $OT_ROOT/hw/ip/  # 看有哪些 IP"
    exit 1
fi

mkdir -p "$STUB_DIR"

# 写 stub (idempotent)
cat > "$STUB_DIR/top_pkg.sv" << 'STUB'
// Minimal stub of OpenTitan top_pkg for sv_query parse-only analysis
// tlul_pkg 实际只引用 7 个 TL_* parameter, 用典型值
package top_pkg;
  parameter int TL_DW   = 32;   // Data Width
  parameter int TL_AW   = 32;   // Address Width
  parameter int TL_DBW  = 4;    // Data Byte Width
  parameter int TL_DIW  = 1;    // Data Integrity Width
  parameter int TL_AIW  = 4;    // Address Source ID Width
  parameter int TL_AUW  = 32;   // Address User Width
  parameter int TL_SZW  = 2;    // Size Width
endpackage : top_pkg

// 同样 stub prim_mubi_pkg
package prim_mubi_pkg;
  parameter int MuBi4Width = 4;
endpackage : prim_mubi_pkg
STUB

# 拼 filelist: stub 放最前, 然后 prim_*, 然后 ip 自身
> "$FILELIST"
echo "$STUB_DIR/top_pkg.sv" >> "$FILELIST"
find "$OT_ROOT/hw/ip/prim/rtl" -name "*.sv" 2>/dev/null | sort >> "$FILELIST" || true
find "$OT_ROOT/hw/ip/$IP_NAME/rtl" -name "*.sv" 2>/dev/null | sort >> "$FILELIST" || true

# 把 *_pkg.sv 移到最前 (parse 顺序很关键)
PACKAGES=$(find "$OT_ROOT/hw/ip/prim/rtl" -name "*_pkg.sv" 2>/dev/null | sort)
TMP=$(mktemp)
echo "$STUB_DIR/top_pkg.sv" > "$TMP"
for pkg in $PACKAGES; do
    echo "$pkg" >> "$TMP"
done
grep -v "/top_pkg.sv$\|/_pkg.sv$" "$FILELIST" >> "$TMP"
mv "$TMP" "$FILELIST"

NUM_PRIM=$(grep -c "/prim/rtl/" "$FILELIST" || echo 0)
NUM_IP=$(grep -c "/$IP_NAME/rtl/" "$FILELIST" || echo 0)
TOTAL=$(wc -l < "$FILELIST")

echo "✅ Generated:"
echo "   Stub:      $STUB_DIR/top_pkg.sv"
echo "   Filelist:  $FILELIST"
echo "   Files:     $TOTAL total ($NUM_PRIM prim + $NUM_IP $IP_NAME)"
echo ""
echo "Run:"
echo "   python run_cli.py protocol detect \\"
echo "       --filelist $FILELIST \\"
echo "       --module <module_name>"

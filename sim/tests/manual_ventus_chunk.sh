#!/bin/bash
# Per-module analysis: each module in a separate Python invocation
# to avoid accumulating memory.
set -e

VENTUS="/Users/fundou/my_dv_proj/ventus-gpgpu-verilog"
PYSV=/Users/fundou/my_dv_proj/sv_query
OUT=/tmp/ventus_core_chunks
mkdir -p "$OUT"

analyze_module() {
    local name=$1
    local filelist=$2
    local target=$3
    
    echo "=== Analyzing $name ==="
    cd "$PYSV"
    python3 -c "
import sys, gc
sys.path.insert(0, '$PYSV/src')
from cli._common import _build_tracer
from trace.core.module_extractor import extract_module_from_graph
from cli.commands.arch import _render_dot
tracer = _build_tracer(filelist='$filelist', strict=False)
g = tracer.build_graph()
ext = extract_module_from_graph(g, target_module='$target', max_depth=4)
inst_tuples = [(i.id, i.def_name, i.depth) for i in ext.instances]
print(f'  Graph: {len(g.nodes())} nodes, {len(g.edges())} edges', file=sys.stderr)
print(f'  Extracted: {len(inst_tuples)} instances', file=sys.stderr)
for i in inst_tuples:
    print(f'    {i}', file=sys.stderr)
edges = [{'src': c.src, 'dst': c.dst} for c in ext.connections]
del g
del tracer
del ext
gc.collect()
dot = _render_dot(inst_tuples, edges, '$target', True, cluster_by_type=True, max_nodes=50)
with open('$OUT/${name}.dot', 'w') as f:
    f.write(dot)
print(f'  Wrote $OUT/${name}.dot ({len(dot)} bytes)', file=sys.stderr)
" 2>&1
    echo ""
}

# 1. L2 cache Scheduler (13 files, biggest core module)
cat > /tmp/v_l2.f << EOF
+incdir+$VENTUS/src/define
+incdir+$VENTUS/src/common_cell
$VENTUS/src/define/define.v
$VENTUS/src/define/undefine.v
$VENTUS/src/gpgpu_top/l2cache/Scheduler.v
$VENTUS/src/gpgpu_top/l2cache/SourceA.v
$VENTUS/src/gpgpu_top/l2cache/sinkA.v
$VENTUS/src/gpgpu_top/l2cache/sourceD.v
$VENTUS/src/gpgpu_top/l2cache/sinkD.v
$VENTUS/src/gpgpu_top/l2cache/MSHR.v
$VENTUS/src/gpgpu_top/l2cache/Listbuffer.v
$VENTUS/src/gpgpu_top/l2cache/banked_store.v
$VENTUS/src/gpgpu_top/l2cache/lru_matrix.v
$VENTUS/src/common_cell/dualportSRAM.v
$VENTUS/src/common_cell/find_first.v
$VENTUS/src/common_cell/fifo.v
$VENTUS/src/common_cell/fifo_with_count.v
EOF
analyze_module "scheduler" "/tmp/v_l2.f" "Scheduler"

# 2. sm2cluster_arb
cat > /tmp/v_s2c.f << EOF
+incdir+$VENTUS/src/define
+incdir+$VENTUS/src/common_cell
$VENTUS/src/define/define.v
$VENTUS/src/define/undefine.v
$VENTUS/src/gpgpu_top/sm2cluster_arb.v
$VENTUS/src/gpgpu_top/cluster_to_l2_arb.v
$VENTUS/src/gpgpu_top/l2_distribute.v
$VENTUS/src/common_cell/round_robin_arb.v
$VENTUS/src/common_cell/fixed_pri_arb.v
$VENTUS/src/common_cell/find_first.v
$VENTUS/src/common_cell/fifo.v
EOF
analyze_module "sm2cluster_arb" "/tmp/v_s2c.f" "sm2cluster_arb"

# 3. l2_distribute (leaf)
cat > /tmp/v_l2d.f << EOF
+incdir+$VENTUS/src/define
+incdir+$VENTUS/src/common_cell
$VENTUS/src/define/define.v
$VENTUS/src/define/undefine.v
$VENTUS/src/gpgpu_top/l2_distribute.v
$VENTUS/src/common_cell/find_first.v
$VENTUS/src/common_cell/fifo.v
$VENTUS/src/common_cell/fifo_with_count.v
$VENTUS/src/common_cell/fifo_with_flush.v
EOF
analyze_module "l2_distribute" "/tmp/v_l2d.f" "l2_distribute"

echo "=== ALL CHUNKS DONE ==="
ls -la "$OUT"/

#!/usr/bin/env python3
"""
verify_native_parity.py — ARCHITECTURE_TODOLIST #7 (option A) diff 验证脚本
============================================================================

目标
----
在 **不替换 MIG 实现** 的前提下, 量化两条实例枚举路径的 MIG 全量输出差异:

  A) 现行路径 (递归):  MIG.build(SemanticAdapter) → semantic_adapter.get_module_instances()
  B) native 路径:       MIG.build(NativeAdapterShim) → native_adapter.get_module_instances_native()

只有两条路径的 MIG 输出 **四张表全部一致** 时, 才允许后续把 MIG 的实例枚举
切到 native (G3 实施)。本脚本是 #7 子任务 2 的交付物。

比较对象 (MIG 四张表)
---------------------
1. instances          {id: (module_type, parent)}
2. port_to_internal   {port_path: internal}
3. internal_to_port   {internal: port_path}
4. _module_ports      {module_type: {port_name: (direction, width, internal_signal)}}

用法
----
  python tools/verify_native_parity.py                          # 内置 fixtures
  python tools/verify_native_parity.py --project <dir> \
      --filelist <path.f> [--top <module>]                      # 单个真实项目 (filelist)
  python tools/verify_native_parity.py --project <dir> \
      --files <a.sv,b.sv> [--top <module>]                      # 单个真实项目 (文件列表)
  python tools/verify_native_parity.py --all                    # fixtures + 已注册真实项目

退出码: 0 = 全部 EQUIVALENT; 1 = 存在 DIFF (或编译失败显式报错, 不静默跳过)

纪律: 本脚本不修任何 src/ 代码, 只做验证与报告。发现的差异记入
      docs/task_tree/iterations/ 的迭代记录, 供 G3 计划决策。
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from trace.core.compiler import SVCompiler  # noqa: E402
from trace.core.module_instance_graph import ModuleInstanceGraph  # noqa: E402
from trace.core.native_adapter import get_module_instances_native  # noqa: E402
from trace.core.semantic_adapter import SemanticAdapter  # noqa: E402

# ----------------------------------------------------------------------------
# Fixtures — 覆盖现有 parity 测试场景 + #7 需要新增探测的边界场景
# ----------------------------------------------------------------------------

FIXTURES: dict[str, str] = {
    "simple": """
module top();
    wire clk, rst;
    sub_a u_a(.clk(clk), .rst(rst));
    sub_b u_b(.clk(clk));
endmodule

module sub_a(input clk, input rst);
    leaf u_l();
endmodule

module sub_b(input clk);
endmodule

module leaf();
endmodule
""",
    "generate_block": """
module top();
    genvar i;
    for (i = 0; i < 4; i++) begin: gen_loop
        sub u_sub();
    end
endmodule

module sub();
endmodule
""",
    "conditional_generate": """
module top #(parameter ENABLE = 1) ();
    if (ENABLE) begin: enable_block
        sub u_sub();
    end
endmodule

module sub();
endmodule
""",
    "multi_depth": """
module top();
    level1 u1();
endmodule

module level1();
    level2 u2();
    level2 u3();
endmodule

module level2();
    level3 u4();
endmodule

module level3();
endmodule
""",
    # [GAP-2 探测] 数组实例化: 递归有 InstanceArray 分支, native 无
    "instance_array": """
module top();
    sub u_arr[3]();
endmodule

module sub(input clk = 1'b0);
endmodule
""",
    # [GAP-1 探测] generate 嵌套 generate: parent_module 对齐问题放大
    "nested_generate": """
module top();
    genvar i, j;
    for (i = 0; i < 2; i++) begin: gen_i
        for (j = 0; j < 2; j++) begin: gen_j
            sub u_sub();
        end
    end
endmodule

module sub();
endmodule
""",
    # [边界] 无子实例的 leaf top: 两条路径都应产出空列表
    "leaf_top": """
module top();
    wire x;
endmodule
""",
    # 端口连接: 校验 port_to_internal / internal_to_port / _module_ports 三张表
    "port_connections": """
module top();
    logic clk, data;
    sub u_dut(.clk(clk), .data(data));
endmodule

module sub(input logic clk, input logic [7:0] data);
endmodule
""",
    # [GAP-5 探测 2026-08-29] target=None: top 只有 generate-for 实例 (无直接
    # InstanceSymbol)。_is_user_module 启发式会把它误判 utility cell → 整棵跳过。
    # 注意: 此 fixture 在 report_fixture 里用 target=None (见 FIXTURE_TARGETS).
    "no_target_loop_gen": """
module top();
    genvar i;
    for (i = 0; i < 2; i++) begin: GEN
        sub u_dut();
    end
endmodule

module sub();
endmodule
""",
}

# [GAP-5 2026-08-29] 每个 fixture 的 target_module; 缺省 "top".
# no_target_loop_gen 走 target=None (生产默认路径), 验证递归/native 都不过滤 top.
FIXTURE_TARGETS: dict[str, str | None] = {
    "no_target_loop_gen": None,
}


class NativeAdapterShim:
    """让 MIG.build 走 native 枚举路径的 shim (只做适配, 不改 MIG).

    与 SemanticAdapter 暴露相同的最小接口:
      - get_module_instances() -> list of wrapper (native 枚举)
      - get_module_name(module) -> 模块类型名 (复用 SemanticAdapter 实现)
    """

    def __init__(self, root, target_module: str | None = None):
        self._root = root
        self._target_module = target_module
        self._instances: list | None = None

    def get_module_instances(self) -> list:
        if self._instances is None:
            self._instances = get_module_instances_native(
                self._root, target_module=self._target_module
            )
        return self._instances

    def get_module_name(self, module) -> str:
        # 委托给 SemanticAdapter 的静态实现 (只用模块级 helper, 无 self 状态依赖)
        return SemanticAdapter.get_module_name(self, module)


# ----------------------------------------------------------------------------
# 快照与 diff
# ----------------------------------------------------------------------------

def snapshot_mig(mig: ModuleInstanceGraph) -> dict[str, list]:
    """把 MIG 四张表拍成可比较的排序列表."""
    instances = sorted(
        (iid, node.module_type, node.parent or "")
        for iid, node in mig.instances.items()
    )
    port_to_internal = sorted(
        (k, v) for k, v in mig.port_to_internal.items()
    )
    internal_to_port = sorted(
        (k, v) for k, v in mig.internal_to_port.items()
    )
    module_ports = sorted(
        (mod, port, info.direction, info.width, info.internal_signal)
        for mod, ports in getattr(mig, "_module_ports", {}).items()
        for port, info in sorted(ports.items())
    )
    return {
        "instances": instances,
        "port_to_internal": port_to_internal,
        "internal_to_port": internal_to_port,
        "module_ports": module_ports,
    }


def diff_snapshots(a: dict, b: dict) -> dict[str, tuple[list, list]]:
    """返回每张表的 (only_a, only_b)."""
    out: dict[str, tuple[list, list]] = {}
    for table in ("instances", "port_to_internal", "internal_to_port", "module_ports"):
        sa = set(a[table])
        sb = set(b[table])
        out[table] = (sorted(sa - sb), sorted(sb - sa))
    return out


def report_fixture(name: str, source: str, target: str | None = "top") -> dict:
    """对单个 fixture 跑 A/B 两条 MIG 路径并报告差异.

    target: 传给两条枚举路径的 target_module (None = 生产默认, 不过滤 top).
    """
    comp = SVCompiler({"t.sv": source})
    root = comp.get_root()

    mig_a = ModuleInstanceGraph(None)
    mig_a.build(SemanticAdapter(root, target_module=target), instance_source="recursive")

    mig_b = ModuleInstanceGraph(None)
    mig_b.build(NativeAdapterShim(root, target_module=target), instance_source="native")

    snap_a = snapshot_mig(mig_a)
    snap_b = snapshot_mig(mig_b)
    diffs = diff_snapshots(snap_a, snap_b)
    equivalent = all(not only_a and not only_b for only_a, only_b in diffs.values())
    return {
        "name": name,
        "equivalent": equivalent,
        "count_a": len(snap_a["instances"]),
        "count_b": len(snap_b["instances"]),
        "diffs": diffs,
    }


def report_project(files: list[str], top: str | None, project: str) -> dict:
    """对单个真实项目跑 A/B 两条 MIG 路径并报告差异.

    编译失败 → 显式抛错 (不静默跳过, 遵守 AGENTS.md 纪律 2/2.5).
    """
    comp = SVCompiler(log_level="WARNING", strict=True)
    for f in files:
        if f.endswith(".f") or f.endswith(".filelist"):
            comp.add_filelist(f)
        else:
            comp.add_files([f])
    root = comp.get_root()

    mig_a = ModuleInstanceGraph(None)
    mig_a.build(SemanticAdapter(root, target_module=top), instance_source="recursive")

    mig_b = ModuleInstanceGraph(None)
    mig_b.build(NativeAdapterShim(root, target_module=top), instance_source="native")

    snap_a = snapshot_mig(mig_a)
    snap_b = snapshot_mig(mig_b)
    diffs = diff_snapshots(snap_a, snap_b)
    equivalent = all(not only_a and not only_b for only_a, only_b in diffs.values())
    return {
        "name": f"{project} (top={top or 'ALL'})",
        "equivalent": equivalent,
        "count_a": len(snap_a["instances"]),
        "count_b": len(snap_b["instances"]),
        "diffs": diffs,
    }


def print_report(result: dict, verbose: bool = False) -> None:
    name = result["name"]
    verdict = "EQUIVALENT" if result["equivalent"] else "DIFF"
    print(f"[{verdict}] {name}: A={result['count_a']} B={result['count_b']} instances")
    if not result["equivalent"] or verbose:
        for table, (only_a, only_b) in result["diffs"].items():
            if not only_a and not only_b:
                continue
            print(f"  - table '{table}':")
            for row in only_a[:10]:
                print(f"      A-only: {row}")
            if len(only_a) > 10:
                print(f"      ... (+{len(only_a) - 10} more A-only)")
            for row in only_b[:10]:
                print(f"      B-only: {row}")
            if len(only_b) > 10:
                print(f"      ... (+{len(only_b) - 10} more B-only)")


# ----------------------------------------------------------------------------
# 真实项目注册表 (ARCHITECTURE_TODOLIST #7 子任务 1: 等价性评估对象)
# 只登记 **已验证存在** 的编译入口 (filelist 或 单文件).
# 待发现入口 (需要人工整理 filelist, 超出 option A 范围, 记入迭代记录):
#   - coralnpu: 无顶层 rtl filelist (hdl/ 分散)
#   - zipcpu:   rtl/ 分 core/ex/peripherals, 无现成 filelist
#   - riscv_core: 目录为空
#   - vortex:   vortex.cfg 是 OpenOCD 配置, 非 filelist
# ----------------------------------------------------------------------------

PROJECTS: list[dict] = [
    {"project": "cva6", "files": ["cva6/Flist.ariane"], "top": None},
    {"project": "darkriscv", "files": ["darkriscv/rtl/darkriscv.v"], "top": None},
]


def main() -> int:
    parser = argparse.ArgumentParser(description="native API vs 自建 MIG diff 验证")
    parser.add_argument("--project", help="真实项目目录 (相对 /Users/fundou/my_dv_proj)")
    parser.add_argument("--filelist", help="filelist 路径 (绝对或相对 project)")
    parser.add_argument("--files", help="逗号分隔的源文件列表 (相对 project)")
    parser.add_argument("--top", default=None, help="target module (默认 None = 全部 top)")
    parser.add_argument("--all", action="store_true", help="fixtures + 已注册真实项目")
    parser.add_argument("--verbose", action="store_true", help="即使等价也打印表内容")
    args = parser.parse_args()

    results: list[dict] = []

    # fixtures
    for name, source in FIXTURES.items():
        target = FIXTURE_TARGETS.get(name, "top")
        results.append(report_fixture(name, source, target=target))

    # 单个真实项目
    if args.project:
        base = "/Users/fundou/my_dv_proj"
        files: list[str] = []
        if args.filelist:
            fl = args.filelist if os.path.isabs(args.filelist) else os.path.join(base, args.filelist)
            files.append(fl)
        elif args.files:
            for f in args.files.split(","):
                f = f.strip()
                files.append(f if os.path.isabs(f) else os.path.join(base, f))
        else:
            parser.error("--project 需要 --filelist 或 --files")
        results.append(report_project(files, args.top, args.project))

    # --all: 已注册真实项目
    if args.all:
        base = "/Users/fundou/my_dv_proj"
        for p in PROJECTS:
            files = []
            missing = False
            for f in p["files"]:
                full = os.path.join(base, f)
                if not os.path.exists(full):
                    print(f"[SKIP] {p['project']}: 文件不存在 {full}")
                    missing = True
                    break
                files.append(full)
            if missing:
                continue
            results.append(report_project(files, p["top"], p["project"]))

    print("=" * 70)
    print("native API vs 自建 MIG — MIG 四表 diff 报告")
    print("=" * 70)
    for r in results:
        print_report(r, verbose=args.verbose)
        print()

    n_equiv = sum(1 for r in results if r["equivalent"])
    n_diff = len(results) - n_equiv
    print(f"总计: {len(results)} 项, EQUIVALENT={n_equiv}, DIFF={n_diff}")
    return 0 if n_diff == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

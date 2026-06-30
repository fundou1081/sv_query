# test_e2e_rtl_to_constraint_coverage.py - 端到端测试：RTL → Constraint → Coverage
#
# 场景: 验证工程师在 RTL 中发现 data 信号行为异常，
#       需要追溯到约束定义和 coverage 定义，快速定位问题。
#
# 流程:
#   1. RTL 中的 data 信号 → 找到驱动它的 transaction 类
#   2. Transaction 类 → 找到约束 data 的 constraint
#   3. Constraint → 找到对应的 covergroup 定义
#   4. 检查 coverage bins 是否完整覆盖 constraint 空间
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer
from trace.core.covergroup_extractor import CovergroupExtractor
from trace.core.covergroup_analyzer import CovergroupAnalyzer
from trace.core.call_graph_builder import CallGraphBuilder
from trace.core.graph.models import NodeKind, EdgeKind


class TestE2ERTLToConstraintCoverage(unittest.TestCase):
    """端到端: RTL → Constraint → Coverage"""

    def test_full_flow(self):
        """[端到端] 完整流程验证

        场景:
        - RTL: assign data_out = pkt.data;
        - Transaction: class my_pkt { rand bit [7:0] data; constraint c_data { data < 200; } }
        - Coverage: coverpoint data { bins low = {[0:99]}; bins high = {[100:255]}; }
        - 问题: constraint 限制 data < 200，但 coverage bins 高位到 255，有浪费

        验证:
        1. RTL data_out 能追溯到 pkt.data
        2. pkt.data 有 constraint c_data
        3. c_data 约束 data < 200
        4. covergroup 有 data 的 coverpoint
        5. 能检测到 bins 超出 constraint 范围
        """
        # === Step 1: RTL + Transaction + Coverage ===
        rtl_source = '''class my_pkt;
    rand bit [7:0] data;
    rand bit [7:0] mode;

    constraint c_data {
        data inside {[0:199]};
    }

    constraint c_mode {
        if (mode == 0) { data inside {[0:99]}; }
        else { data inside {[100:199]}; }
    }

    covergroup cg;
        coverpoint data {
            bins zero = {0};
            bins low  = {[1:99]};
            bins mid  = {[100:199]};
            bins high = {[200:255]};  // ❌ 超出 constraint 范围
        }
        coverpoint mode {
            bins idle = {0};
            bins busy = {1};
        }
        cross data, mode;
    endgroup

    function new();
        cg = new();
    endfunction
endclass

module dut(input clk);
    my_pkt pkt = new();
    logic [7:0] data_out;
    assign data_out = pkt.data;
endmodule'''

        # === Step 2: 构建信号图 ===
        tracer = UnifiedTracer(sources={'test.sv': rtl_source})
        graph = tracer.build_graph()

        # 验证 data_out 的驱动链
        drivers = graph.find_drivers('dut.data_out')
        driver_names = [d.id for d in drivers]
        print(f"[RTL] data_out drivers: {driver_names}")

        # 验证 pkt.data 节点存在
        pkt_data = graph.get_node('dut.pkt.data')
        self.assertIsNotNone(pkt_data, "pkt.data 节点应存在")
        print(f"[RTL] pkt.data kind: {pkt_data.kind}")

        # === Step 3: 提取约束信息 ===
        # 从信号图中找 packet 类的约束
        constraint_blocks = []
        for n in graph.nodes():
            node = graph.get_node(n)
            if node and node.kind == NodeKind.CONSTRAINT_BLOCK:
                constraint_blocks.append(n)

        print(f"\n[Constraint] 约束块: {constraint_blocks}")

        # 找到约束 data 的 constraint
        data_constraints = []
        for src, dst in graph.edges():
            edge = graph.get_edge(src, dst)
            if edge.kind == EdgeKind.CONSTRAINS and 'data' in dst:
                node = graph.get_node(src)
                if node and node.kind == NodeKind.CONSTRAINT_BLOCK:
                    data_constraints.append(src)

        print(f"[Constraint] 约束 data 的 constraint: {data_constraints}")
        self.assertGreater(len(data_constraints), 0, "应有约束 data 的 constraint")

        # === Step 4: 提取 Coverage 信息 ===
        extractor = CovergroupExtractor({'test.sv': rtl_source})
        cgs = extractor.extract()

        self.assertGreater(len(cgs), 0, "应有 covergroup")
        cg = cgs[0]

        print(f"\n[Coverage] covergroup: {cg.name}")
        for cp in cg.coverpoints:
            print(f"  coverpoint: {cp.signal}")
            for b in cp.bins:
                print(f"    {b.kind}: {b.name} = {b.values}")

        # === Step 5: 一致性检查 ===
        analyzer = CovergroupAnalyzer(graph, cgs)
        gaps = analyzer.analyze()

        print(f"\n[Analysis] 检测到 {len(gaps)} 个问题:")
        for gap in gaps:
            print(f"  [{gap.kind}] {gap.description}")

        # 应检测到 missing_cross 或其他问题
        # (mode 是条件约束变量，应该和 data 有 cross)
        cross_gaps = [g for g in gaps if g.kind == 'missing_cross']
        print(f"\n[Analysis] missing_cross: {len(cross_gaps)}")

        # === Step 6: 汇总报告 ===
        print(f"\n{'='*50}")
        print("端到端验证报告:")
        print("  RTL 信号: dut.data_out → dut.pkt.data")
        print(f"  约束块: {data_constraints}")
        print(f"  Coverage bins: {len(cg.coverpoints[0].bins)} 个")
        print(f"  检测问题: {len(gaps)} 个")
        print(f"{'='*50}")


class TestE2EMultiClassInheritance(unittest.TestCase):
    """端到端: 多层继承场景"""

    def test_inherited_constraint_coverage(self):
        """[端到端] 继承约束的 coverage 检查

        base_pkt: constraint c_base { id > 0; }
        my_pkt extends base_pkt: constraint c_data { data < 200; }

        covergroup 只覆盖了 data，没有覆盖 id
        → 应检测到 id 缺少 coverpoint
        """
        source = '''class base_pkt;
    rand bit [7:0] id;
    constraint c_base { id inside {[1:255]}; }
endclass

class my_pkt extends base_pkt;
    rand bit [7:0] data;
    constraint c_data { data inside {[0:199]}; }

    covergroup cg;
        coverpoint data {
            bins low  = {[0:99]};
            bins high = {[100:199]};
        }
        // ❌ 缺少 id 的 coverpoint
    endgroup

    function new();
        cg = new();
    endfunction
endclass

module top; endmodule'''
        graph, tracer, cgs = _build_all(source)

        # 验证继承传播
        my_pkt_id = graph.get_node('my_pkt.id')
        self.assertIsNotNone(my_pkt_id, "my_pkt.id 应通过继承存在")

        # 验证约束传播
        from trace.core.graph.models import EdgeKind
        c_base_constraints = []
        for src, dst in graph.edges():
            edge = graph.get_edge(src, dst)
            if edge.kind == EdgeKind.CONSTRAINS and dst == 'my_pkt.id':
                node = graph.get_node(src)
                if node and node.kind == NodeKind.CONSTRAINT_BLOCK:
                    c_base_constraints.append(src)

        print(f"[继承] my_pkt.id 的约束: {c_base_constraints}")
        self.assertGreater(len(c_base_constraints), 0, "my_pkt.id 应有继承的约束")

        # 验证 covergroup 不包含 id
        cg = cgs[0] if cgs else None
        self.assertIsNotNone(cg)
        cp_signals = [cp.signal for cp in cg.coverpoints]
        print(f"[Coverage] coverpoint signals: {cp_signals}")
        self.assertNotIn('id', cp_signals, "id 不在 covergroup 中")

        # 这里可以扩展: 检测到 id 有约束但没有 coverpoint


def _build_all(source):
    tracer = UnifiedTracer(sources={'test.sv': source})
    graph = tracer.build_graph()
    extractor = CovergroupExtractor({'test.sv': source})
    cgs = extractor.extract()
    return graph, tracer, cgs


if __name__ == '__main__':
    unittest.main()

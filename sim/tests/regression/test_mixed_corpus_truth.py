# test_mixed_corpus_truth.py — 混合真实场景语料库 (iter_179, C 路线第一项)
#
# 方豆 C 路线: "把混合真实场景沉淀成常态化对抗语料库"。
#
# 背景: iter_164~178 的对抗轮发现,**单域对抗全绿 ≠ 安全** — 真正的缺口
# (env 嵌套的槽展开 / 嵌套约束解析 / logic 实参 Conversion 壳 / 参数化嵌套成员链)
# 都只在 class+module+covergroup **混合语料**上才现形。本文件把那些场景固化为
# **常驻语料** + 端到端不变量断言, 使后续任何改动都要过这一关。
#
# 语料: sim/tests/fixtures/mixed_corpus/*.sv (7 个)
# 断言维度: 提取 (cg 名/归属/实例规则) → 建图节点 → Q1 采样链 fanin →
#           Q2 反向 → Q3 约束 → 数据端点 fanin
#
# 维护约定: 新增语料 = 加 .sv + 在本文件 CASES 加一条; 断言必须基于**实测**,
# 若实测与预期不符 → 先判断是缺陷还是预期需修正 (禁止"改断言让它过")。
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer  # noqa: E402

CORPUS = Path(__file__).resolve().parents[1] / "fixtures" / "mixed_corpus"

# ── 语料规格表 (全部实测自 iter_179; 见 docs/task_tree/iterations/iter_179_*) ──
CASES = {
    "env_nested_cg.sv": {
        "desc": "env{packet p; cg on p.addr} + module 驱动链 (类中类 + 方法链)",
        "covergroups": {("cg_p", "packet", "ctor_new"), ("cg_env", "tb_env", "ctor_new")},
        "q1": {
            "cg_p": {"cp": (["top.e.p.addr"], {"top.din"})},
            "cg_env": {"cp_p": (["top.e.p.addr"], {"top.din"})},
        },
        "q2": {"top.e.p.addr": {("cg_p", "cp", "top.e.p"), ("cg_env", "cp_p", "top.e")}},
        "fanin": {"top.e.p.addr": {"top.din"}},
    },
    "env_nested_constraint.sv": {
        "desc": "env{packet p (带 constraint); cg} — Q3 嵌套实例约束",
        "covergroups": {("cg_env", "tb_env", "ctor_new")},
        "q1": {"cg_env": {"cp_p": (["top.e.p.addr"], {"top.din"})}},
        "q3": {"cg_env": {"cp_p": {"packet.c_addr"}}},
        "fanin": {"top.e.p.addr": {"top.din"}},
    },
    "full_stack_mixed.sv": {
        "desc": "module assign + submodule 端口 + class 方法 + module/class 双 cg",
        "covergroups": {("cg_acc", "packet", "ctor_new"), ("cg_mod", "", "module_scope")},
        "q1": {
            "cg_mod": {"cp_w": (["top.w", "top.din"], {"top.din", "top.din2"}),
                       "cp_x": (["top.xored"], {"top.u_sub.s"})},
            "cg_acc": {"cp": (["top.p.acc"], {"top.u_sub.s", "top.xored"})},
        },
        "q2": {"top.w": {("cg_mod", "cp_w", "")}},
        "fanin": {"top.xored": {"top.u_sub.s"},
                  "top.u_sub.s": {"top.din", "top.u_sub.a", "top.u_sub.b", "top.w"},
                  "top.w": {"top.din", "top.din2"}},
    },
    "generate_class.sv": {
        "desc": "generate-for 实例链 + 类实例 + module cg",
        "covergroups": {("cg", "", "module_scope")},
        "q1": {"cg": {"cp": (["top.chain"],
                             {"top.G[0].u_leaf.y", "top.G[1].u_leaf.y",
                              "top.G[2].u_leaf.y", "top.din"})}},
        "fanin": {"top.chain[3]": {"top.G[2].u_leaf.y"}, "top.p.data": {"top.din"}},
    },
    "interface_monitor.sv": {
        "desc": "子模块层次 + module cg (宿主锚 top.u_sub)",
        "covergroups": {("cg_sub", "", "module_scope")},
        "q1": {"cg_sub": {"cp": (["top.u_sub.mid"], {"top.din", "top.u_sub.vin"})}},
        "q2": {"top.u_sub.mid": {("cg_sub", "cp", "")}},
        "fanin": {"top.u_sub.mid": {"top.din", "top.u_sub.vin"},
                  "top.out": {"top.u_sub.vout"}},
    },
    "logic_arg_method.sv": {
        "desc": "logic 4 态实参 → bit 形参 (Conversion 壳) 的类方法展开",
        "covergroups": {("cg", "packet", "ctor_new")},
        "q1": {"cg": {"cp": (["top.p.addr"], {"top.din"})}},
        "fanin": {"top.p.addr": {"top.din"}},
    },
    "param_class_nested.sv": {
        "desc": "参数化 class 内嵌参数化 class (packet#(W) 成员 inner#(W))",
        "covergroups": {("cg", "packet", "ctor_new")},
        "q1": {"cg": {"cp": (["top.p.data"], set())}},  # data 未被驱动 (drive 写 i.val)
        "fanin": {"top.p.i.val": {"top.din"}, "top.p.data": set()},
    },
}


def _tracer(fixture: str):
    p = CORPUS / fixture
    tr = UnifiedTracer(sources={str(p): p.read_text(encoding='utf-8')}, log_level='ERROR')
    tr.build_graph(use_cache=False, target_module='top')
    return tr


class TestMixedCorpusTruth(unittest.TestCase):
    """语料库端到端不变量 (提取 → 图 → Q1/Q2/Q3 → fanin)"""

    def test_fixtures_present(self):
        self.assertEqual(sorted(p.name for p in CORPUS.glob('*.sv')), sorted(CASES))

    def test_covergroup_extraction(self):
        """每个语料的 cg 定义 (名/归属/实例规则) 精确匹配"""
        for fixture, spec in CASES.items():
            with self.subTest(fixture=fixture):
                tr = _tracer(fixture)
                got = {(c.name, c.in_class, c.instance_rule) for c in tr._get_covergroup_cgs()}
                self.assertEqual(got, spec["covergroups"], f"{fixture}: {spec['desc']}")

    def test_q1_sampling_chains(self):
        """Q1: 每个 cp 的采样信号 id + fanin 驱动集精确匹配"""
        for fixture, spec in CASES.items():
            with self.subTest(fixture=fixture):
                tr = _tracer(fixture)
                for cg_name, cps in spec.get("q1", {}).items():
                    infos = {i.cp_name: i for i in tr.trace_covergroup_sampling(cg_name)}
                    for cp_name, (want_sampled, want_drivers) in cps.items():
                        info = infos[cp_name]
                        self.assertEqual(info.sampled, want_sampled,
                                         f"{fixture}/{cg_name}.{cp_name} 采样信号")
                        self.assertEqual(set(info.drivers), want_drivers,
                                         f"{fixture}/{cg_name}.{cp_name} 驱动集")

    def test_q2_reverse_lookup(self):
        """Q2: 信号 → 采样它的 (cg, cp, 实例) 集合精确匹配"""
        for fixture, spec in CASES.items():
            with self.subTest(fixture=fixture):
                tr = _tracer(fixture)
                for signal, want in spec.get("q2", {}).items():
                    got = {(m.cg_name, m.cp_name, m.instance)
                           for m in tr.trace_coverpoints(signal)}
                    self.assertEqual(got, want, f"{fixture}: Q2({signal})")

    def test_q3_rand_linkage(self):
        """Q3: class cg 采样属性 → 约束块 id 精确匹配"""
        for fixture, spec in CASES.items():
            with self.subTest(fixture=fixture):
                tr = _tracer(fixture)
                for cg_name, cps in spec.get("q3", {}).items():
                    links = {}
                    for r in tr.trace_covergroup_rand_linkage(cg_name):
                        links.setdefault(r.cp_name, set()).update(
                            c.block_id for c in r.constraints)
                    for cp_name, want in cps.items():
                        self.assertEqual(links.get(cp_name, set()), want,
                                         f"{fixture}/{cg_name}.{cp_name} 约束集")

    def test_data_endpoint_fanin(self):
        """数据端点 fanin (跨域链: 方法体/端口桥/generate 实例) 精确匹配"""
        for fixture, spec in CASES.items():
            with self.subTest(fixture=fixture):
                tr = _tracer(fixture)
                for signal, want in spec.get("fanin", {}).items():
                    got = {r.id for r in tr.trace_fanin(signal)}
                    self.assertEqual(got, want, f"{fixture}: fanin({signal})")


if __name__ == '__main__':
    unittest.main()

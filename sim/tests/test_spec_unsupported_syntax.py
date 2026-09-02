"""
test_spec_unsupported_syntax.py — Golden fixtures for SV syntax spec.

[2026-08-27 15:30+] Phase 3 落实: 给 spec "❌ 不支持" 行提供可执行证据。
每个 fixture 一个测试, 断言 build 行为符合 spec 声称。

Spec 来源: docs/SIGNAL_GRAPH_SPEC.md §1.3, docs/SV_SYNTAX_MAPPING.md §1.

注意: 这些测试**记录当前 (已知不支持) 行为**, 不应被视为"应该通过的"。
如果未来 driver_extractor 修复支持了, 这些测试需要改 spec 而不是改代码。
"""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))

FIXTURE_DIR = REPO / 'sim/tests/fixtures/spec_golden'


def _build_stats(sv_path: Path) -> dict:
    """Run run_cli.py stats --file <sv> --json, return parsed result dict."""
    proc = subprocess.run(
        [sys.executable, 'run_cli.py', 'stats', '--file', str(sv_path), '--json'],
        cwd=REPO, capture_output=True, text=True, timeout=60,
    )
    return json.loads(proc.stdout)


class TestUnsupportedSyntaxGolden:
    """[2026-08-27] Phase 3 — Lock down current 'unsupported' behavior.

    这些测试是 spec 的"反例 golden"。它们断言:
    - 语法不报错 (driver_extractor 不崩) OR 报预期 elaboration error
    - 不生成预期的 driver 边 (因为该语法不被支持)
    """

    def test_initial_block_no_driver(self):
        """initial q = 1'b0 不应生成 DRIVER 边 (driver_extractor.py:3346-3349 显式 pass)."""
        result = _build_stats(FIXTURE_DIR / 'probe_initial.sv')
        assert result['ok']
        # always_ff q <= ~q 产生 2 个 DRIVER (q load + clk clock), 但 1'b0 不应进入 DRIVER
        # 节点集不应包含 '1'b0' 或 'initial_q' 等 initial 痕迹
        for node_kind in result['result']['nodes']:
            assert 'INITIAL' not in node_kind.upper(), \
                f"initial 块不应产生节点, got {node_kind}"

    def test_casez_processed_as_normal_case(self):
        """casez 应被按普通 case 处理 (z 通配符语义丢失)."""
        result = _build_stats(FIXTURE_DIR / 'probe_casez.sv')
        assert result['ok']
        # casez (sel) 2'b1? / 2'b?1 / default 共 3 个 case item → 3 个 DRIVER
        # 注: casez 通配符语义 (?, x, z) 被 pyslang 当作普通 case 处理, 无警告
        edges = result['result']['edges']
        assert edges.get('DRIVER', 0) >= 3, \
            f"casez 期望 >=3 DRIVER (a, b, c 各驱动 q), got {edges}"

    def test_casex_processed_as_normal_case(self):
        """casex 应被按普通 case 处理 (x 通配符语义丢失)."""
        result = _build_stats(FIXTURE_DIR / 'probe_casex.sv')
        assert result['ok']
        edges = result['result']['edges']
        assert edges.get('DRIVER', 0) >= 3, \
            f"casex 期望 >=3 DRIVER, got {edges}"

    def test_unique_case_strips_modifier(self):
        """unique case 修饰符被 strip, 按普通 case 处理 + CaseRedundantDefault warning."""
        proc = subprocess.run(
            [sys.executable, 'run_cli.py', 'stats',
             '--file', str(FIXTURE_DIR / 'probe_unique_case.sv'), '--json'],
            cwd=REPO, capture_output=True, text=True, timeout=60,
        )
        result = json.loads(proc.stdout)
        assert result['ok']
        # unique 修饰符被 strip → 仅 [CaseRedundantDefault] warning, unique 语义 (冲突检测/并行优先级) 全无
        warnings = proc.stderr.count('[CaseRedundantDefault]')
        assert warnings == 1, f"期望唯一 [CaseRedundantDefault] warning, got {warnings}"
        edges = result['result']['edges']
        assert edges.get('DRIVER', 0) >= 3, \
            f"unique case 期望 >=3 DRIVER (按普通 case 处理), got {edges}"

    def test_generate_if_wire_extracted(self):
        """[iter_107 #23 修复] generate-if 内 wire 声明现在被提取.

        原 limitation (G3): get_generate_net_declarations 只处理 GenerateBlockArray
        (for/case), generate-if 单块 (GenerateBlock) 的 wire 漏掉 → prod1 节点
        缺失、driver 边缺失. 修复后: 激活分支 (USE=1 → g_use1) 的
        `wire prod1 = a * b` 提取 a→prod1, b→prod1 边; 未激活分支
        (g_use0) 的 prod0 不出现."""
        result = _build_stats(FIXTURE_DIR / 'probe_generate_if_wire.sv')
        assert result['ok']
        edges = result['result']['edges']
        assert edges.get('DRIVER', 0) == 2, \
            f"generate-if 激活分支 wire 期望 2 条 DRIVER (a*b), got {edges}"

    def test_generate_case_wire_extracted(self):
        """[iter_107 #24 验证] generate-case 单块内 wire 声明也被提取.

        #23 修复的 GenerateBlock 分支同样覆盖 generate-case 的 case item
        (每个 case item 是 GenerateBlockSymbol). SEL=2 → g_use2 激活
        (wire prod2 = a - b → 2 条 DRIVER) + assign y 假分支 a→y 1 条 = 3."""
        result = _build_stats(FIXTURE_DIR / 'probe_generate_case_wire.sv')
        assert result['ok']
        edges = result['result']['edges']
        assert edges.get('DRIVER', 0) == 3, \
            f"generate-case 期望 3 条 DRIVER (prod2×2 + a→y), got {edges}"

    def test_replication_rhs_supported(self):
        """RHS replication `{3{q}}` 应正常生成 DRIVER 边 (正例对照 probe_repl_lhs 是 SV 禁止)."""
        result = _build_stats(FIXTURE_DIR / 'probe_replication_rhs.sv')
        assert result['ok']
        edges = result['result']['edges']
        assert edges.get('DRIVER', 0) == 1, \
            f"RHS replication 期望 1 DRIVER (q → y), got {edges}"


class TestKnownSvStandardForbidden:
    """[2026-08-27] probe_repl_lhs 实测: SV 标准禁止 Replication 作 LHS.

    不同于 driver_extractor 不支持, 这是 SV 语法本身不允许.
    spec 应明确标 'SV 规范禁止' 而非 'pyslang 不支持'.
    """

    def test_replication_lhs_is_sv_illegal(self):
        """`{4{q}} = q` 是 SV 非法语法 (replication 不能作 LHS).

        [iter_082 fix] 原测试引用 /tmp/spec_probe_repl_lhs.sv (幽灵文件, 从未创建);
        且断言消息 "expression is not allowed as a statement" 是错误文本 —
        pyslang 实测报 [ExpressionNotAssignable] / "expression is not assignable".
        改用 spec_golden/probe_repl_lhs.sv (与 probe_replication_rhs.sv 对称).
        """
        proc = subprocess.run(
            [sys.executable, 'run_cli.py', 'stats',
             '--file', str(FIXTURE_DIR / 'probe_repl_lhs.sv'), '--json'],
            cwd=REPO, capture_output=True, text=True, timeout=60,
        )
        # 期望: elaboration error (ExpressionNotAssignable), NOT a clean JSON
        combined = proc.stderr + proc.stdout
        assert 'ExpressionNotAssignable' in combined, \
            f"期望 SV 标准禁止 Replication-LHS (ExpressionNotAssignable), got: {combined[-300:]}"

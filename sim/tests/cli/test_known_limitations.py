"""
test_known_limitations.py - V6.3+5 2026-07-28: document known limitations.

This file documents pyslang and architecture limitations that
V6.3+5 cannot fix but future versions should address:

1. generate-if/else: when a parameter controls which always block runs,
   pyslang's `get_always_blocks()` may not enumerate the active branch.
   Real-world impact: picorv32 alu_shr, alu_add_sub, alu_eq, alu_lts,
   alu_ltu have no leaf drivers in the graph (even though they have
   many ternary/binary ops in their RHS).

2. ElementSelect (arr[N]): array indexing is not yet decomposed to
   the array name as a driver. Existing tests in
   test_visualize_teach_nested_mux.py::test_array_index_mux document
   this.

3. $signed() / $unsigned() in parens around ternary: works correctly
   when NOT inside a generate-if (see test_visualize_teach_binary_ops).
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
GOLDEN = PROJECT_ROOT / "sim" / "tests" / "fixtures" / "golden_mini" / "generate_if_alu.sv"
PYTHONPATH = str(PROJECT_ROOT / "src") + ":" + str(PROJECT_ROOT / "tools")


def _strip_pycache():
    import shutil
    for p in (PROJECT_ROOT / "src").rglob("__pycache__"):
        shutil.rmtree(p, ignore_errors=True)


def _build_graph(file_path: Path, target: str = "generate_if_alu"):
    _strip_pycache()
    from trace.unified_tracer import UnifiedTracer
    src = file_path.read_text()
    tracer = UnifiedTracer(sources={file_path.name: src}, strict=False)
    return tracer.build_graph()


class TestGenerateIfLimitation:
    """generate if (PARAM) ... else begin always @* ... end endgenerate
    may not be enumerated by pyslang's get_always_blocks when the param
    evaluates to 0 (the else branch is active but pyslang may miss it).

    This is a pyslang semantic AST limitation, not a bug in our extraction.
    """

    def test_generate_if_with_param_zero_has_zero_always_blocks(self):
        """TWO_CYCLE_ALU=0 (default) → pyslang returns 0 always blocks
        from get_always_blocks(), even though the else branch has a
        working always @* block."""
        from trace.core.compiler import SVCompiler
        from trace.core.semantic_adapter import SemanticAdapter

        # Re-import inside test to be safe
        compiler = SVCompiler(sources={'gen.sv': GOLDEN.read_text()})
        adapter = SemanticAdapter(compiler.get_root())

        modules = adapter.get_modules()
        # Skip if no module
        assert modules, "fixture should have at least one module"

        for m in modules:
            blocks = list(adapter.get_always_blocks(m))
            # With TWO_CYCLE_ALU=0, we expect 0 always blocks (limitation)
            assert len(blocks) == 0, (
                f"expected 0 always blocks under pyslang generate-if "
                f"limitation (TWO_CYCLE_ALU=0), got {len(blocks)}. "
                "If pyslang now handles generate-if else branches, "
                "this test should be updated."
            )

    def test_generate_if_alu_shr_has_drivers(self):
        """[iter_103 缺陷 F 修复] generate-if/else 激活分支的 always @*
        现在被 get_generate_always_blocks 收集 → alu_shr 有 DRIVER 边.

        原 limitation (2026-07-28): generate-if 单块 (GenerateBlock, 非 Array)
        内的 always 不被遍历, alu_shr 0 驱动边. 修复后 else 分支
        (TWO_CYCLE_ALU=0 激活) 的赋值正常提取."""
        g = _build_graph(GOLDEN)
        # alu_shr should exist as a node (parameter declaration registers it)
        alu_shr_nodes = [n for n in g.nodes() if n.endswith('alu_shr')]
        assert len(alu_shr_nodes) == 1, (
            f"expected alu_shr node, got {alu_shr_nodes}"
        )

        # 修复后: 激活分支 (else, always @*) 的赋值应有 DRIVER 边
        from trace.core.graph.models import EdgeKind
        incoming_drivers = 0
        for u, v in g.edges():
            if v.endswith('alu_shr'):
                edge = g.get_edge(u, v)
                if edge and edge.kind == EdgeKind.DRIVER:
                    incoming_drivers += 1
        assert incoming_drivers > 0, (
            f"alu_shr 应有 DRIVER 边 (缺陷 F 修复: generate-if else 分支 "
            f"always @* 被收集), got {incoming_drivers}"
        )

    def test_outside_generate_if_still_works(self):
        """Verify the limitation is specific to generate-if, not our
        extraction. An isolated `always @*` with the same alu_shr
        expression should produce drivers."""
        fixture = '''
        module test_no_gen;
          reg [31:0] alu_shr, reg_op1, reg_op2;
          reg instr_sra, instr_srai;

          always @* begin
            alu_shr = $signed({instr_sra || instr_srai ? reg_op1[31] : 1'b0, reg_op1})
                      >>> reg_op2[4:0];
          end
        endmodule
        '''
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.sv', delete=False, mode='w') as f:
            f.write(fixture)
            tmp_path = Path(f.name)

        try:
            g = _build_graph(tmp_path, target='test_no_gen')
            from trace.core.graph.models import EdgeKind
            drivers = []
            for u, v in g.edges():
                if v.endswith('alu_shr'):
                    edge = g.get_edge(u, v)
                    if edge and edge.kind == EdgeKind.DRIVER:
                        drivers.append(u)
            # Outside generate-if, drivers should appear
            assert len(drivers) >= 4, (
                f"without generate-if, alu_shr should have ≥4 drivers "
                f"(reg_op1, reg_op1[31], reg_op2, instr_sra, instr_srai). "
                f"Got {drivers}"
            )
        finally:
            tmp_path.unlink()

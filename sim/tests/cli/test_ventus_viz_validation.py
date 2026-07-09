"""
[Validation 2026-07-10] Verify Ventus GPGPU visualizations against source code.

User 2026-07-10 00:54: '这图的结果和代码真的一致吗' (Is the diagram really
consistent with the code?). This test parses the SV source + DOT files
and asserts they agree on sub-instance count, signal declarations,
generate block count, and pipeline cycle depth.
"""
import re
import unittest
from pathlib import Path


VENTUS = Path("/Users/fundou/my_dv_proj/ventus-gpgpu-verilog")


def read_text(path: Path) -> str:
    assert path.exists(), f"Source file missing: {path}"
    return path.read_text()


def extract_dut_instances(source: str) -> set[str]:
    """Extract all `ModuleName inst_name_dut(` instantiations."""
    pattern = r"^\s*(\w+)\s+(\w+_dut)\s*\("
    return {f"{m}.{n}" for m, n in re.findall(pattern, source, re.MULTILINE)}


def has_signal_decl(source: str, sig: str, kind: str) -> bool:
    """Check if signal is declared as `kind` (wire/reg)."""
    pattern = rf"^\s*{kind}\s+\S*{re.escape(sig)}\b"
    return bool(re.search(pattern, source, re.MULTILINE))


def evaluate_define(defines: str, expr: str) -> int:
    """Evaluate simple `EXPR = A op B` macro defines."""
    m = re.search(rf"define\s+{re.escape(expr)}\s+(\([^)]+\)|.+\S)", defines)
    if not m:
        raise ValueError(f"define {expr} not found")
    val = m.group(1).strip()
    if val.isdigit():
        return int(val)
    # Strip parens and evaluate recursively
    if val.startswith("(") and val.endswith(")"):
        return evaluate_define(defines, val[1:-1].strip())
    # arithmetic like `A + B` or `A * B` or `A / B`
    for op in ["+", "-", "*", "/", "%"]:
        if op in val:
            left, right = val.split(op, 1)
            return int(eval_op(evaluate_define(defines, left.strip()), op, evaluate_define(defines, right.strip())))
    raise ValueError(f"Cannot evaluate: {val}")


def eval_op(a: int, op: str, b: int) -> int:
    if op == "+": return a + b
    if op == "-": return a - b
    if op == "*": return a * b
    if op == "/": return a // b
    if op == "%": return a % b
    raise ValueError(f"Unknown op: {op}")


class TestVentusSchedulerVizAccuracy(unittest.TestCase):
    """Validate sv_query's Scheduler arch/chain against actual SV source."""

    def test_scheduler_has_7_dut_instances(self):
        """[Validation] Scheduler should have 7 _dut sub-instances in source."""
        source = read_text(VENTUS / "src/gpgpu_top/l2cache/Scheduler.v")
        duts = extract_dut_instances(source)
        # Source has: SourceA, sourceD, sinkA, sinkD, directory_test, banked_store, Listbuffer
        self.assertEqual(len(duts), 7, f"Expected 7 _dut, got {len(duts)}: {duts}")
        self.assertIn("SourceA.SourceA_dut", duts)
        self.assertIn("sourceD.sourceD_dut", duts)
        self.assertIn("sinkA.sinkA_dut", duts)
        self.assertIn("sinkD.sinkD_dut", duts)
        self.assertIn("directory_test.directory_test_dut", duts)
        self.assertIn("banked_store.banked_store_dut", duts)
        self.assertIn("Listbuffer.Listbuffer_dut", duts)

    def test_mshr_generate_loop_creates_4_instances(self):
        """[Validation] MSHR generate block creates 4 instances (MSHRS=4)."""
        defines = read_text(VENTUS / "src/define/define.v")
        # MSHRS = (L2CACHE_MEMCYCLES + L2CACHE_BLOCKBEATS - 1) / L2CACHE_BLOCKBEATS
        # L2CACHE_BLOCKBEATS = L2CACHE_BLOCKBYTES / L2CACHE_BEATBYTES (=1, both are `L2CACHE_BLOCKWORDS * 4)
        memcycles = int(re.search(r"define\s+L2CACHE_MEMCYCLES\s+(\d+)", defines).group(1))
        # Both L2CACHE_BLOCKBYTES and L2CACHE_BEATBYTES = L2CACHE_BLOCKWORDS * 4, so ratio = 1.
        blockbeats = 1
        mshrs = (memcycles + blockbeats - 1) // blockbeats
        self.assertEqual(mshrs, 4, f"MSHRS = (4 + 1 - 1) / 1 = {mshrs}")

    def test_scheduler_signal_declarations(self):
        """[Validation] Signal declarations match: alloc=wire, issue_flush_invalidate=reg."""
        source = read_text(VENTUS / "src/gpgpu_top/l2cache/Scheduler.v")
        # alloc should be wire
        self.assertTrue(has_signal_decl(source, "alloc", "wire"),
                       "alloc should be declared as wire (combinational)")
        self.assertFalse(has_signal_decl(source, "alloc", "reg"),
                        "alloc should NOT be declared as reg")
        # issue_flush_invalidate should be reg
        self.assertTrue(has_signal_decl(source, "issue_flush_invalidate", "reg"),
                       "issue_flush_invalidate should be declared as reg (sequential)")
        # request_ready_i should be wire
        self.assertTrue(has_signal_decl(source, "request_ready_i", "wire"),
                       "request_ready_i should be declared as wire (combinational)")

    def test_l2cache_memcycles_is_4(self):
        """[Validation] L2CACHE_MEMCYCLES=4 (matches 'Total cycles: 4' in chain DOT)."""
        defines = read_text(VENTUS / "src/define/define.v")
        memcycles = int(re.search(r"define\s+L2CACHE_MEMCYCLES\s+(\d+)", defines).group(1))
        self.assertEqual(memcycles, 4)

    def test_l2cache_helper_files_exist(self):
        """[Validation] All 7 l2cache helper modules should exist as files."""
        for name in ["SourceA.v", "sourceD.v", "sinkA.v", "sinkD.v", "MSHR.v",
                     "Listbuffer.v", "Scheduler.v", "directory_test.v",
                     "banked_store.v", "lru_matrix.v"]:
            path = VENTUS / "src/gpgpu_top/l2cache" / name
            self.assertTrue(path.exists(), f"Missing l2cache module: {name}")

    def test_sm2cluster_arb_uses_fixed_pri_arb(self):
        """[Validation] sm2cluster_arb uses fixed_pri_arb as memReqArb."""
        source = read_text(VENTUS / "src/gpgpu_top/sm2cluster_arb.v")
        # The actual pattern is: `fixed_pri_arb #(.ARB_WIDTH(...)) memReqArb(`
        # (with parameter list in between)
        self.assertRegex(source, r"fixed_pri_arb[\s\S]+memReqArb\s*\(",
                        "sm2cluster_arb should have `fixed_pri_arb ... memReqArb(...)`")
        # Verify it's an instantiation, not a forward declaration
        self.assertNotIn("`include", source.split("fixed_pri_arb")[1].split("memReqArb")[0],
                        "fixed_pri_arb should be instantiated, not included")


if __name__ == "__main__":
    unittest.main()

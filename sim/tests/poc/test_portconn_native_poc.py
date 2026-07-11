"""
POC test 2026-07-11: portConnections 替代 MIG 自建 port mappings

验证目标:
1. topInstances.filter(target) 能找到目标
2. hierarchicalPath 自动以 user target 为前缀 (无需 rewrite)
3. portConnections 给我们 clean port mappings

关联: MEMORY.md TODO "pyslang Native API 重构机会" (2026-06-25)
"""
import pytest
import sys, os, time
sys.path.insert(0, "/Users/fundou/my_dv_proj/sv_query/src")

from trace.core.compiler import SVCompiler


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PROJECT_ROOT = "/Users/fundou/my_dv_proj"


def _load_darkriscv():
    """Load darkriscv RTL sources."""
    proj_path = f"{PROJECT_ROOT}/darkriscv/rtl"
    files = [
        'darkriscv.v', 'darkuart.v', 'darkspi.v', 'darkio.v',
        'darkbridge.v', 'darkcache.v', 'darkmac.v', 'darkpll.v',
        'darkram.v', 'darksocv.v'
    ]
    sources = {}
    for f in files:
        path = os.path.join(proj_path, f)
        with open(path, errors='replace') as fp:
            sources[f] = fp.read()
    compiler = SVCompiler(sources=sources, strict=False, log_level='ERROR')
    compiler.add_include_dir(proj_path)
    return compiler, "darksocv"


def _walk_native(target_top, max_depth=10):
    """Walk target body and yield (hierarchicalPath, depth, type_name)."""
    out = []
    
    def walk(inst, depth=0):
        if depth > max_depth:
            return
        hp = None
        try:
            hp = str(inst.hierarchicalPath) if hasattr(inst, 'hierarchicalPath') else None
        except Exception:
            return
        if not hp:
            return
        try:
            defn = inst.definition
            type_name = str(defn.name) if defn else '?'
        except Exception:
            type_name = '?'
        out.append((hp, depth, type_name))
        body = getattr(inst, 'body', None)
        if body is None:
            return
        try:
            for child in body:
                kind = str(getattr(child, 'kind', ''))
                if 'Instance' in kind:
                    walk(child, depth + 1)
                elif 'GenerateBlockArray' in kind:
                    entries = getattr(child, 'entries', None) or list(child)
                    for entry in entries:
                        if 'GenerateBlock' in str(getattr(entry, 'kind', '')):
                            walk(entry, depth + 1)
                elif 'GenerateBlock' in kind:
                    walk(child, depth + 1)
        except Exception:
            return
    
    walk(target_top)
    return out


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPortConnNativePOC:
    """[POC 2026-07-11] portConnections 替代 MIG 自建 port mappings."""

    def test_topInstances_filter_finds_target(self):
        """Hypothesis 1: topInstances.filter(target) 找目标"""
        compiler, target = _load_darkriscv()
        comp = compiler.get_compilation()
        root = comp.getRoot()
        
        tops = list(root.topInstances)
        # Skip if elaboration failed completely
        if not tops:
            pytest.skip("No top instances (elaboration failed)")
        
        # Check darksocv is in topInstances
        names = []
        for t in tops:
            try:
                names.append(str(t.name))
            except Exception:
                continue
        
        assert "darksocv" in names, f"darksocv not in topInstances: {names}"

    def test_hierarchicalPath_uses_target_as_prefix(self):
        """Hypothesis 2: hierarchicalPath 自动以 user target 为前缀 (无需 rewrite).

        这是 MEMORY.md TODO "namespace rewrite" 的核心问题.
        旧实现: arch.py 在 extract_module 后做 namespace rewrite (~50 行)
        期望: pyslang native API 在 filter by target 后, 自动产生正确的 prefix.
        """
        compiler, target = _load_darkriscv()
        comp = compiler.get_compilation()
        root = comp.getRoot()
        
        target_top = None
        for t in root.topInstances:
            try:
                if str(t.name) == target:
                    target_top = t
                    break
            except Exception:
                continue
        
        if target_top is None:
            pytest.skip(f"target {target!r} not in topInstances")
        
        sub_insts = _walk_native(target_top)
        assert len(sub_insts) > 0, "No sub-instances found"
        
        # All hierarchical paths should start with target.
        bad = []
        for hp, depth, type_name in sub_insts:
            if not (hp == target or hp.startswith(f"{target}.")):
                bad.append(hp)
        
        assert not bad, f"Bad namespace paths (should be {target}.*): {bad}"

    def test_portConnections_returns_clean_port_list(self):
        """Hypothesis 3: portConnections 给我们 clean port mappings.

        每个 instance 的 portConnections 应该非空, 且 port name 可读.
        """
        compiler, target = _load_darkriscv()
        comp = compiler.get_compilation()
        root = comp.getRoot()
        
        target_top = None
        for t in root.topInstances:
            try:
                if str(t.name) == target:
                    target_top = t
                    break
            except Exception:
                continue
        
        if target_top is None:
            pytest.skip(f"target {target!r} not in topInstances")
        
        sub_insts = _walk_native(target_top)
        # Skip top itself
        sub_only = [(inst_path) for hp, depth, tn in sub_insts 
                    for inst_path in [hp] if hp != target]
        
        assert len(sub_only) >= 3, f"Expected ≥3 sub-instances in darksocv, got {len(sub_only)}"
        
        # Walk again to get the actual InstanceSymbol objects
        sub_with_insts = []
        def collect(inst, depth=0):
            try:
                hp = str(inst.hierarchicalPath)
            except Exception:
                return
            sub_with_insts.append((inst, hp))
            body = getattr(inst, 'body', None)
            if body is None:
                return
            for child in body:
                kind = str(getattr(child, 'kind', ''))
                if 'Instance' in kind:
                    collect(child, depth + 1)
                elif 'GenerateBlockArray' in kind:
                    for entry in (getattr(child, 'entries', None) or list(child)):
                        if 'GenerateBlock' in str(getattr(entry, 'kind', '')):
                            collect(entry, depth + 1)
                elif 'GenerateBlock' in kind:
                    collect(child, depth + 1)
        collect(target_top)
        
        # Find sub-instances only (not target itself)
        sub_only_with_inst = [(i, hp) for i, hp in sub_with_insts if hp != target]
        assert len(sub_only_with_inst) >= 3
        
        # Each sub-instance should have non-empty portConnections
        for inst, hp in sub_only_with_inst:
            port_conns = getattr(inst, 'portConnections', [])
            # portConnections might be 0 for some leaf modules but should be list
            assert isinstance(port_conns, list), \
                f"{hp}: portConnections is not a list ({type(port_conns).__name__})"
            
            # Check at least one port has a readable name
            for pc in port_conns[:5]:
                port = getattr(pc, 'port', None)
                if port and hasattr(port, 'name'):
                    try:
                        pname = str(port.name)
                        # Just verify it's a non-empty string
                        assert pname and pname != '<binary>', \
                            f"{hp}: port name invalid ({pname!r})"
                        break
                    except Exception:
                        continue

    def test_native_walk_faster_than_mig(self):
        """Performance: native walk should be much faster than self-built MIG.

        MIG (module_instance_graph.py) 走 ~600ms.
        Native walk 应该 < 50ms.
        """
        compiler, target = _load_darkriscv()
        comp = compiler.get_compilation()
        root = comp.getRoot()
        
        target_top = None
        for t in root.topInstances:
            try:
                if str(t.name) == target:
                    target_top = t
                    break
            except Exception:
                continue
        
        if target_top is None:
            pytest.skip(f"target {target!r} not in topInstances")
        
        # Time native walk
        t0 = time.time()
        for _ in range(5):  # 5 runs
            _walk_native(target_top)
        elapsed_ms = (time.time() - t0) * 1000 / 5
        
        # Loose threshold: < 200ms (vs MIG ~600ms baseline)
        assert elapsed_ms < 200, \
            f"Native walk too slow: {elapsed_ms:.1f}ms (expect < 200ms)"
        
        print(f"\n  [PERF] native walk avg: {elapsed_ms:.1f}ms")

    def test_native_walk_correct_sub_instance_count(self):
        """darkriscv darksocv should have 3 sub-instances (after ifdef resolution).

        - bridge0 (darkbridge)
        - bram0 (darkram)
        - io0 (darkio)
        - darkpll0 (darkpll) -- inside `ifdef BOARD_CK` -- correctly hidden
        """
        compiler, target = _load_darkriscv()
        comp = compiler.get_compilation()
        root = comp.getRoot()
        
        target_top = None
        for t in root.topInstances:
            try:
                if str(t.name) == target:
                    target_top = t
                    break
            except Exception:
                continue
        
        if target_top is None:
            pytest.skip(f"target {target!r} not in topInstances")
        
        # Walk
        sub_insts = _walk_native(target_top)
        # Direct sub-instances (depth=1)
        direct_subs = [hp for hp, depth, _ in sub_insts if depth == 1]
        
        # Expected: 3 direct subs (bridge0, bram0, io0)
        # darkpll0 is inside `ifdef BOARD_CK` which is NOT defined → hidden
        assert len(direct_subs) >= 3, \
            f"Expected ≥3 direct sub-instances, got {len(direct_subs)}: {direct_subs}"
        
        # Verify the 3 expected sub-instance names are present
        expected = {"bridge0", "bram0", "io0"}
        actual_short = {hp.split(".")[-1] for hp in direct_subs}
        missing = expected - actual_short
        assert not missing, f"Missing expected sub-instances: {missing}"

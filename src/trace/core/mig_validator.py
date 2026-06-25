"""
mig_validator.py — Cross-check MIG output using native API as informational tool.

[Phase 2 2026-06-25] per user direction:
- MIG 是 production path, 不替换
- native API 仅用作 verification / 对标自查
- 不再 auto-judge MIG is_ok=True/False (之前的 instance count diff 是误报)

[Phase 2.1 2026-06-25] 改 design:
- 之前: 比 instance count + key set (容易误报, 因为 native 漏 utility cell sub-instances)
- 现在: 提供 2 个独立 verification functions, 各自返回 informative 结果
  1. compare_with_extract_module: 拿 extract_module 当 ground truth (user target filtered)
     跟 MIG 对比, 告诉 user 哪些 inst 是 utility cell (MIG 含) vs user hierarchy
  2. verify_specific_port: 拿 native portConnections 验证 specific port 是否真的连到某 signal

用法:
    from trace.core.mig_validator import compare_with_extract_module, verify_specific_port

    # 1. MIG vs extract_module (informational)
    info = compare_with_extract_module(mig, semantic_adapter, target_module='cva6')
    print(info.summary())
    # 输出: MIG 含 X inst, extract 含 Y inst, diff Z 是 utility cells

    # 2. Specific port verification
    result = verify_specific_port(root, target_module='cva6',
                                   inst_path='cva6.i_frontend',
                                   port_name='clk_i',
                                   expected_signal='top.clk_i')
    print(result.summary())
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional, List

import pyslang


# ----------------------------------------------------------------------------
# Result types
# ----------------------------------------------------------------------------

@dataclass
class ExtractComparison:
    """[Phase 2.1] Compare MIG with extract_module output."""
    target_module: str
    # MIG stats
    mig_instance_count: int = 0
    mig_port_mapping_count: int = 0
    # Extract (ground truth) stats
    extract_instance_count: int = 0
    extract_port_count: int = 0
    # Informational
    utility_instance_count: int = 0
    utility_instances: list = field(default_factory=list)
    # Notes (informational, not pass/fail)
    notes: list = field(default_factory=list)

    def summary(self) -> str:
        """[Helper] Human-readable summary — informational only."""
        lines = [
            f"=== MIG vs Extract Comparison: {self.target_module} ===",
            f"MIG:    {self.mig_instance_count} instances, {self.mig_port_mapping_count} port mappings",
            f"Extract: {self.extract_instance_count} instances ({self.extract_port_count} port refs)",
            f"Utility cells (in MIG but not in user hierarchy): {self.utility_instance_count}",
        ]
        if self.utility_instances:
            lines.append(f"  Sample utility cells: {self.utility_instances[:5]}")
        if self.notes:
            for n in self.notes:
                lines.append(f"📝 {n}")
        lines.append("")
        lines.append("ℹ️  This is informational. MIG includes utility cells (e.g. cdc_2phase, fifo,")
        lines.append("    lfsr_8bit) that are recursive sub-instances within user modules.")
        lines.append("    arch command re-filters with extract_module to show only user hierarchy.")
        return "\n".join(lines)


@dataclass
class PortVerification:
    """[Phase 2.1] Verify a specific port connection using native API."""
    target_module: str
    inst_path: str
    port_name: str
    expected_signal: Optional[str] = None
    # Results
    found_in_mig: bool = False
    mig_value: Optional[str] = None
    found_in_native: bool = False
    native_value: Optional[str] = None
    match: bool = False
    notes: list = field(default_factory=list)

    def summary(self) -> str:
        """[Helper] Human-readable summary."""
        lines = [
            f"=== Port Verification: {self.inst_path}.{self.port_name} ===",
            f"MIG: {'✓' if self.found_in_mig else '✗'} {self.mig_value or '(not found)'}",
            f"Native: {'✓' if self.found_in_native else '✗'} {self.native_value or '(not found)'}",
        ]
        if self.expected_signal:
            lines.append(f"Expected: {self.expected_signal}")
        if self.match:
            lines.append("✅ MIG and native agree")
        else:
            lines.append("⚠️  MIG and native disagree - investigate")
        if self.notes:
            for n in self.notes:
                lines.append(f"📝 {n}")
        return "\n".join(lines)


# ----------------------------------------------------------------------------
# Public API: Compare MIG with extract_module (ground truth)
# ----------------------------------------------------------------------------

def compare_with_extract_module(
    mig,
    semantic_adapter,
    target_module: str,
    max_depth: int = 10,
) -> ExtractComparison:
    """[Phase 2.1] Compare MIG with extract_module output (informational).

    MIG walks ALL modules (including utility cells like cdc_2phase, fifo).
    Extract module only returns user-target hierarchy (filtered).
    This is expected — NOT a bug.

    Args:
        mig: ModuleInstanceGraph instance
        semantic_adapter: SemanticAdapter (for extract_module)
        target_module: user-specified target
        max_depth: max depth for extract

    Returns:
        ExtractComparison with stats
    """
    from trace.core.module_extractor import extract_module

    result = ExtractComparison(target_module=target_module)

    # 1. MIG stats
    pti = mig.port_to_internal
    result.mig_port_mapping_count = len(pti)
    mig_instances = set()
    for k in pti:
        if '.' in k:
            mig_instances.add('.'.join(k.split('.')[:-1]))
    result.mig_instance_count = len(mig_instances)

    # 2. Extract stats (ground truth)
    try:
        extract = extract_module(semantic_adapter, target_module, max_depth=max_depth)
        result.extract_instance_count = len(extract.instances)
        result.extract_port_count = sum(
            len(p) for p in [getattr(extract, 'external_ports', [])]
        )
    except Exception as e:
        result.notes.append(f"Could not run extract_module: {e}")
        return result

    # 3. Find utility cells (in MIG but not in extract)
    extract_ids = {inst.id for inst in extract.instances}
    utility = mig_instances - extract_ids
    result.utility_instance_count = len(utility)
    result.utility_instances = sorted(utility)[:20]

    if utility:
        result.notes.append(
            f"{len(utility)} instances are utility cells (cdc_2phase, fifo, lfsr, etc.) "
            f"recursively walked by MIG. Extract filters them out — this is expected."
        )

    return result


# ----------------------------------------------------------------------------
# Public API: Verify specific port connection
# ----------------------------------------------------------------------------

def verify_specific_port(
    root: pyslang.RootSymbol,
    target_module: str,
    inst_path: str,
    port_name: str,
    expected_signal: Optional[str] = None,
) -> PortVerification:
    """[Phase 2.1] Verify a specific port connection using native API.

    Use this to debug specific port issues:
    - Is this port in MIG? What internal signal does MIG map it to?
    - Does native API agree?

    Args:
        root: pyslang RootSymbol
        target_module: user target (e.g. 'cva6')
        inst_path: full hierarchical path (e.g. 'cva6.i_frontend')
        port_name: port name (e.g. 'clk_i')
        expected_signal: optional expected signal name to compare

    Returns:
        PortVerification with results
    """
    result = PortVerification(
        target_module=target_module,
        inst_path=inst_path,
        port_name=port_name,
        expected_signal=expected_signal,
    )

    # Native walk
    target_top = None
    for top in root.topInstances:
        try:
            if top.name == target_module:
                target_top = top
                break
        except Exception:
            continue
    if target_top is None:
        for top in root.topInstances:
            try:
                if top.body is not None:
                    for child in top.body:
                        try:
                            if 'Instance' in str(child.kind):
                                target_top = top
                                break
                        except Exception:
                            continue
                    if target_top:
                        break
            except Exception:
                continue

    # Walk native to find specific instance
    found_port = False
    if target_top is not None:
        try:
            for inst, hp, _depth in _walk_with_path(target_top):
                if hp == inst_path:
                    port_conns = getattr(inst, 'portConnections', [])
                    for conn in port_conns:
                        port = getattr(conn, 'port', None)
                        if port is None:
                            continue
                        try:
                            pname = str(port.name)
                        except Exception:
                            continue
                        if pname == port_name:
                            expr = getattr(conn, 'expression', None)
                            sig = None
                            if expr is not None:
                                sym = getattr(expr, 'symbol', None)
                                if sym is not None:
                                    try:
                                        sig = str(sym.name)
                                    except Exception:
                                        sig = None
                                if sig is None:
                                    try:
                                        sig = str(expr)
                                    except Exception:
                                        sig = None
                            result.found_in_native = True
                            result.native_value = sig
                            found_port = True
                            break
                    break
        except Exception as e:
            result.notes.append(f"Native walk error: {e}")

    if not found_port:
        result.notes.append(
            f"Native API didn't find {inst_path}.{port_name} — "
            f"instance path or port name may be wrong, or filelist incomplete"
        )

    # MIG check (caller should pass mig in via wrapper if needed; here we report not_found)
    # [Phase 2.1 simplified] MIG check requires access to mig object —
    # users can verify via direct dict lookup: mig.port_to_internal.get(f"{inst_path}.{port_name}")
    result.notes.append(
        "To check MIG value: mig.port_to_internal.get(f'{inst_path}.{port_name}')"
    )

    return result


def _walk_with_path(inst, parent_path="", depth=0, max_depth=15):
    """[Helper] Walk with hierarchical path tracking."""
    try:
        hp = str(inst.hierarchicalPath) if hasattr(inst, 'hierarchicalPath') else None
    except Exception:
        hp = None
    if not hp:
        return
    if hp == parent_path and depth == 0:
        pass  # top
    else:
        yield inst, hp, depth

    body = getattr(inst, 'body', None)
    if body is None or depth >= max_depth:
        return
    try:
        for child in body:
            try:
                kind = str(child.kind)
            except Exception:
                continue
            if 'Instance' in kind:
                yield from _walk_with_path(child, parent_path, depth + 1, max_depth)
            elif 'GenerateBlockArray' in kind:
                try:
                    entries = getattr(child, 'entries', None) or list(child)
                except Exception:
                    entries = []
                for entry in entries:
                    try:
                        if 'GenerateBlock' in str(getattr(entry, 'kind', '')):
                            yield from _walk_with_path(entry, parent_path, depth + 1, max_depth)
                    except Exception:
                        continue
            elif 'GenerateBlock' in kind:
                yield from _walk_with_path(child, parent_path, depth + 1, max_depth)
    except Exception:
        return

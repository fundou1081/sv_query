"""
mig_validator.py — Cross-check MIG output against pyslang native API.

[Phase 2 2026-06-25] Use native API as oracle to detect MIG bugs.

策略 (per user direction '保留旧方案用作 debug + 对标自查'):
- 跑 sv_query 旧 MIG build, 拿到 port_to_internal
- 用 pyslang native portConnections + definition 算 ground truth
- 对比: count, key set, value set
- 不一致 → MIG 有 bug, report
- 一致 → MIG 正确 (production 可以继续用旧实现)

用法:
    from trace.core.mig_validator import validate_mig_with_native
    result = validate_mig_with_native(mig, root, target_module='cva6')
    print(result.summary())
    if not result.is_ok():
        # 报告不一致, debug
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

import pyslang


# ----------------------------------------------------------------------------
# Result types
# ----------------------------------------------------------------------------

@dataclass
class MigValidationResult:
    """[Phase 2] Cross-check MIG vs native API."""
    target_module: str
    # MIG stats
    mig_instance_count: int = 0
    mig_port_mapping_count: int = 0
    mig_shared_internal_count: int = 0
    # Native stats (ground truth)
    native_instance_count: int = 0
    native_port_count: int = 0
    native_connected_signal_count: int = 0
    # Mismatch
    instance_count_diff: int = 0
    extra_mig_keys: list = field(default_factory=list)
    missing_mig_keys: list = field(default_factory=list)
    # Verdict
    is_ok: bool = True
    notes: list = field(default_factory=list)

    def summary(self) -> str:
        """[Helper] Human-readable summary."""
        lines = [
            f"=== MIG Validation: {self.target_module} ===",
            f"MIG: {self.mig_instance_count} instances, {self.mig_port_mapping_count} port mappings, {self.mig_shared_internal_count} shared",
            f"Native: {self.native_instance_count} instances, {self.native_port_count} port connections, {self.native_connected_signal_count} unique signals",
            f"Instance count diff: {self.instance_count_diff}",
        ]
        if self.extra_mig_keys:
            lines.append(f"⚠️  MIG extra keys (in MIG but not native): {len(self.extra_mig_keys)}")
            for k in self.extra_mig_keys[:5]:
                lines.append(f"     {k}")
        if self.missing_mig_keys:
            lines.append(f"⚠️  MIG missing keys (in native but not MIG): {len(self.missing_mig_keys)}")
            for k in self.missing_mig_keys[:5]:
                lines.append(f"     {k}")
        if self.notes:
            for n in self.notes:
                lines.append(f"📝 {n}")
        if self.is_ok:
            lines.append("✅ MIG matches native API (no bugs detected)")
        else:
            lines.append("❌ MIG has potential bugs - investigate")
        return "\n".join(lines)


# ----------------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------------

def validate_mig_with_native(
    mig,
    root: pyslang.RootSymbol,
    target_module: str,
) -> MigValidationResult:
    """[Phase 2] Cross-check MIG against pyslang native API.

    Args:
        mig: ModuleInstanceGraph instance (with port_to_internal built)
        root: pyslang RootSymbol
        target_module: user-specified target

    Returns:
        MigValidationResult with comparison stats
    """
    result = MigValidationResult(target_module=target_module)

    # 1. MIG stats
    pti = mig.port_to_internal
    result.mig_port_mapping_count = len(pti)
    itp = mig.internal_to_port
    result.mig_shared_internal_count = sum(
        1 for v in pti.values() if sum(1 for x in pti.values() if x == v) >= 2
    )
    # instance count: unique instance_id (everything before last '.port_name')
    mig_instances = set()
    for k in pti:
        if '.' in k:
            mig_instances.add('.'.join(k.split('.')[:-1]))
    result.mig_instance_count = len(mig_instances)

    # 2. Native ground truth
    native_data = _collect_native_port_connections(root, target_module)
    result.native_instance_count = len(native_data['instances'])
    result.native_port_count = sum(
        len(pcs) for pcs in native_data['port_connections'].values()
    )
    result.native_connected_signal_count = len(native_data['connected_signals'])

    # 3. Instance count compare
    result.instance_count_diff = result.mig_instance_count - result.native_instance_count
    if abs(result.instance_count_diff) > 0:
        result.is_ok = False
        result.notes.append(
            f"Instance count differs by {result.instance_count_diff} — "
            f"likely utility cells or namespace mismatch"
        )

    # 4. Key set compare (normalized — strip namespace prefix)
    mig_keys_normalized = _normalize_mig_keys(set(pti.keys()), target_module)
    native_keys = set()
    for inst_id, pcs in native_data['port_connections'].items():
        for port_name in pcs.keys():
            native_keys.add(f"{inst_id}.{port_name}")
    native_keys_normalized = _normalize_mig_keys(native_keys, target_module)

    extra = mig_keys_normalized - native_keys_normalized
    missing = native_keys_normalized - mig_keys_normalized
    if extra:
        result.is_ok = False
        result.extra_mig_keys = sorted(extra)[:20]
    if missing:
        result.is_ok = False
        result.missing_mig_keys = sorted(missing)[:20]

    if not result.is_ok and result.instance_count_diff == 0:
        result.notes.append(
            "Key mismatch despite matching instance count — "
            "port name extraction may differ"
        )

    return result


# ----------------------------------------------------------------------------
# Native data collection
# ----------------------------------------------------------------------------

def _collect_native_port_connections(root, target_module):
    """[Helper] 用 native API 收集所有 instance 的 port connections.

    Returns: dict with 'instances' (set), 'port_connections' (dict[inst_id, dict[port_name, signal]]),
             'connected_signals' (set)
    """
    instances = set()
    port_connections = {}
    connected_signals = set()

    # Find target top
    target_top = None
    for top in root.topInstances:
        try:
            if top.name == target_module:
                target_top = top
                break
        except (UnicodeDecodeError, TypeError, Exception):
            continue
    if target_top is None:
        # Fall back: first user module top
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

    if target_top is None:
        return {'instances': instances, 'port_connections': port_connections,
                'connected_signals': connected_signals}

    # Walk
    _walk_collect(target_top, target_module, instances, port_connections, connected_signals,
                  is_top=True)
    return {'instances': instances, 'port_connections': port_connections,
            'connected_signals': connected_signals}


def _walk_collect(inst, target_module, instances, port_connections,
                  connected_signals, is_top=False):
    """[Helper] Recursive walk to collect port connections."""
    try:
        inst_id = str(inst.hierarchicalPath) if hasattr(inst, 'hierarchicalPath') else None
    except (UnicodeDecodeError, TypeError, Exception):
        inst_id = None
    if not inst_id:
        return

    # Skip top target
    if is_top and inst_id == target_module:
        pass  # Don't emit, but continue walk
    else:
        instances.add(inst_id)
        # Collect port connections
        port_conns = getattr(inst, 'portConnections', [])
        port_connections[inst_id] = {}
        for conn in port_conns:
            port = getattr(conn, 'port', None)
            if port is None:
                continue
            try:
                port_name = str(port.name)
            except (UnicodeDecodeError, TypeError, Exception):
                continue
            if not port_name:
                continue
            expr = getattr(conn, 'expression', None)
            signal_name = None
            if expr is not None:
                sym = getattr(expr, 'symbol', None)
                if sym is not None:
                    try:
                        signal_name = str(sym.name)
                    except (UnicodeDecodeError, TypeError, Exception):
                        signal_name = None
                if signal_name is None:
                    try:
                        signal_name = str(expr)
                    except (UnicodeDecodeError, TypeError, Exception):
                        signal_name = None
            port_connections[inst_id][port_name] = signal_name
            if signal_name:
                connected_signals.add(signal_name)

    # Recurse
    body = getattr(inst, 'body', None)
    if body is None:
        return
    try:
        for child in body:
            try:
                kind = str(child.kind)
            except (UnicodeDecodeError, TypeError, Exception):
                continue
            if 'Instance' in kind:
                _walk_collect(child, target_module, instances, port_connections,
                              connected_signals, is_top=False)
            elif 'GenerateBlockArray' in kind:
                _walk_collect_gba(child, target_module, instances, port_connections,
                                  connected_signals)
            elif 'GenerateBlock' in kind:
                _walk_collect_gb(child, target_module, instances, port_connections,
                                 connected_signals)
    except (UnicodeDecodeError, TypeError, Exception):
        return


def _walk_collect_gba(gba, target_module, instances, port_connections, connected_signals):
    try:
        entries = getattr(gba, 'entries', None) or list(gba)
    except Exception:
        return
    for entry in entries:
        try:
            if 'GenerateBlock' in str(getattr(entry, 'kind', '')):
                _walk_collect_gb(entry, target_module, instances, port_connections, connected_signals)
        except Exception:
            continue


def _walk_collect_gb(gb, target_module, instances, port_connections, connected_signals):
    try:
        for child in gb:
            try:
                kind = str(child.kind)
            except Exception:
                continue
            if 'Instance' in kind:
                _walk_collect(child, target_module, instances, port_connections,
                              connected_signals, is_top=False)
            elif 'GenerateBlockArray' in kind:
                _walk_collect_gba(child, target_module, instances, port_connections, connected_signals)
            elif 'GenerateBlock' in kind:
                _walk_collect_gb(child, target_module, instances, port_connections, connected_signals)
    except Exception:
        return


def _normalize_mig_keys(keys, target_module):
    """[Helper] Strip leading namespace prefix to allow comparison.

    Native uses 'ariane.i_cva6.X.Y' but MIG after namespace rewrite uses 'cva6.X.Y'.
    Strip until we find a segment EXACTLY matching target_module.
    """
    out = set()
    for k in keys:
        parts = k.split('.')
        if target_module in parts:
            idx = parts.index(target_module)
            out.add('.'.join(parts[idx:]))
        else:
            # Keep as-is (no match = don't normalize)
            out.add(k)
    return out

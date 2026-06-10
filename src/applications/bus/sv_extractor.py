"""
applications.bus.sv_extractor - SystemVerilog 信号提取

Phase A v3: 真实 SV 集成 (Option 1)

设计要点
========

1. **从 SV 文件/filelist 编译 → 提取 port list**
2. **port list → SignalContext list** (供 ProtocolDetector 使用)
3. **支持单 module 或多 module** (多 module 时全部检测, top-1 输出)
4. **复用现有 infra**:
   - `UnifiedTracer` (filelist, include_dirs, sources)
   - `SemanticAdapter.get_port_declarations(module)`
   - `SemanticAdapter.get_port_name_and_direction(port)`
   - `SemanticAdapter.extract_port_width(port, scope=module)`

使用
====

    from applications.bus.sv_extractor import SVSignalExtractor

    extractor = SVSignalExtractor(filelist="/path/to/file.f")
    modules = extractor.extract_all_modules()
    for mod_name, sigs in modules.items():
        print(f"{mod_name}: {len(sigs)} signals")
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from .structural import SignalContext
from .normalize import SignalNormalizer, NormalizeConfig


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class ExtractedModule:
    """从 SV 提取的模块信号.

    Attributes:
        name: 模块名
        signals: 该模块的 port SignalContext 列表
        file: 来源文件
    """

    name: str
    signals: List[SignalContext] = field(default_factory=list)
    file: str = ""


# ---------------------------------------------------------------------------
# SVSignalExtractor
# ---------------------------------------------------------------------------

class SVSignalExtractor:
    """从 SV 文件提取模块的信号上下文 (SignalContext)."""

    def __init__(
        self,
        sources: Optional[Dict[str, str]] = None,
        files: Optional[List[str]] = None,
        filelist: Optional[str] = None,
        include_dirs: Optional[List[str]] = None,
        log_level: str = "WARNING",
    ):
        self._sources = sources
        self._files = files or []
        self._filelist = filelist
        self._include_dirs = include_dirs or []
        self._log_level = log_level
        self._tracer = None
        self._extracted: Dict[str, ExtractedModule] = {}

    @classmethod
    def from_file(
        cls,
        file: str,
        include_dirs: Optional[List[str]] = None,
    ) -> "SVSignalExtractor":
        """从单文件构造."""
        with open(file) as f:
            sources = {file: f.read()}
        return cls(sources=sources, include_dirs=include_dirs)

    @classmethod
    def from_filelist(
        cls,
        filelist: str,
        include_dirs: Optional[List[str]] = None,
    ) -> "SVSignalExtractor":
        """从 filelist (.f/.fl) 构造."""
        return cls(filelist=filelist, include_dirs=include_dirs)

    # ----- 提取 -----

    def extract_all_modules(self) -> Dict[str, ExtractedModule]:
        """提取所有模块的信号.

        Returns:
            {module_name: ExtractedModule}
        """
        if self._extracted:
            return self._extracted

        tracer = self._get_tracer()
        adapter = self._get_adapter(tracer)
        root = tracer._get_compiler().get_root()

        # 遍历 root, 找所有 ModuleDeclaration
        modules = self._find_modules(root, adapter)
        for mod_name, mod in modules.items():
            sigs = self._extract_module_signals(mod, adapter)
            if sigs:
                self._extracted[mod_name] = ExtractedModule(
                    name=mod_name,
                    signals=sigs,
                    file=self._module_file(mod),
                )
        return self._extracted

    def extract_module(self, module_name: str) -> Optional[ExtractedModule]:
        """提取单个模块的信号."""
        all_mods = self.extract_all_modules()
        return all_mods.get(module_name)

    def list_modules(self) -> List[str]:
        """列出所有模块名."""
        return list(self.extract_all_modules().keys())

    # ----- 内部 -----

    def _get_tracer(self):
        """获取或创建 UnifiedTracer."""
        if self._tracer is None:
            # 添加项目 src 到 sys.path, 让 import 找到 trace.*
            project_root = Path(__file__).resolve().parents[3]  # ~/my_dv_proj/sv_query
            src_path = project_root / "src"
            if str(src_path) not in sys.path:
                sys.path.insert(0, str(src_path))

            from trace.unified_tracer import UnifiedTracer

            kwargs = {
                "log_level": self._log_level,
                "include_dirs": self._include_dirs,
            }
            if self._sources is not None:
                kwargs["sources"] = self._sources
            if self._files:
                kwargs["files"] = self._files
            if self._filelist:
                kwargs["filelist"] = self._filelist
            self._tracer = UnifiedTracer(**kwargs)
        return self._tracer

    def _get_adapter(self, tracer):
        """获取 SemanticAdapter."""
        return tracer._get_adapter()

    def _find_modules(self, root, adapter) -> Dict[str, object]:
        """从 root 找所有模块定义.

        返回 {module_name: module_node}.
        走 SemanticAdapter.get_modules() (兼容好路径).
        """
        modules: Dict[str, object] = {}

        # 优先用 adapter.get_modules() (已验证走 SymbolKind.Instance 路径)
        if hasattr(adapter, "get_modules"):
            try:
                for mod in adapter.get_modules():
                    name = self._safe_get_name(mod)
                    if name:
                        modules[name] = mod
                if modules:
                    return modules
            except Exception:
                pass

        return modules

    def _extract_module_signals(self, mod, adapter) -> List[SignalContext]:
        """从 module 提取所有 port 的 SignalContext."""
        sigs: List[SignalContext] = []

        # 1. 收集 port declarations
        port_decls = self._get_port_declarations(mod, adapter)
        port_names: List[str] = []

        for port in port_decls:
            name, direction = adapter.get_port_name_and_direction(port)
            if not name or name == "unknown":
                continue
            # 用 safe get 避免 unicode 错误
            try:
                width = self._get_port_width(adapter, port, mod)
            except Exception:
                width = 1

            sigs.append(SignalContext(
                name=name,
                width=width,
                direction=direction if direction != "unknown" else "input",
                driver_kind="port",
            ))
            port_names.append(name)

        # 2. 找 paired signals (heuristic: AW/W/AR/R valid+ready pairs)
        paired = self._infer_paired_signals(sigs)

        # 更新 sigs, 设置 paired_signals
        sigs_with_paired = []
        sig_by_name = {s.name: s for s in sigs}
        for sig in sigs:
            new_sig = SignalContext(
                name=sig.name,
                width=sig.width,
                direction=sig.direction,
                driver_kind=sig.driver_kind,
                paired_signals=paired.get(sig.name, []),
            )
            sigs_with_paired.append(new_sig)
        return sigs_with_paired

    def _get_port_declarations(self, mod, adapter) -> List[object]:
        """获取 module 的所有 port 声明."""
        if hasattr(adapter, "get_port_declarations"):
            try:
                return list(adapter.get_port_declarations(mod))
            except Exception:
                pass
        return []

    def _get_port_width(self, adapter, port, mod) -> int:
        """提取 port 位宽.

        使用 port.internalSymbol.declaredType.type.bitWidth 路径.
        fallback 1 (1-bit signal 默认).
        """
        # 主路径: port.internalSymbol.declaredType.type.bitWidth
        try:
            int_sym = getattr(port, "internalSymbol", None)
            if int_sym is not None:
                dt = getattr(int_sym, "declaredType", None)
                if dt is not None:
                    inner = getattr(dt, "type", None)
                    if inner is not None and hasattr(inner, "bitWidth"):
                        bw = inner.bitWidth
                        if isinstance(bw, int) and bw > 0:
                            return bw
        except Exception:
            pass

        # 备用路径: adapter.extract_port_width
        try:
            width_info = adapter.extract_port_width(port, scope=mod)
            if isinstance(width_info, dict):
                msb = width_info.get("msb_eval", width_info.get("msb_raw"))
                lsb = width_info.get("lsb_eval", width_info.get("lsb_raw"))
                if isinstance(msb, int) and isinstance(lsb, int):
                    return max(1, msb - lsb + 1)
                return 1
            elif isinstance(width_info, tuple) and len(width_info) == 2:
                msb, lsb = width_info
                if isinstance(msb, int) and isinstance(lsb, int):
                    return max(1, msb - lsb + 1)
                return 1
        except Exception:
            pass
        return 1

    def _infer_paired_signals(
        self, sigs: List[SignalContext],
    ) -> Dict[str, List[str]]:
        """启发式找 valid+ready 配对 (双向).

        双向:
        - output-valid + input-ready (master 视角)
        - input-valid + output-ready (slave 视角)
        共享通道前缀 (标准化后).
        """
        norm = SignalNormalizer(NormalizeConfig.default())

        def _is_valid_like(n: str) -> bool:
            return any(n.endswith(s) for s in ("valid", "vld", "req"))

        def _is_ready_like(n: str) -> bool:
            return any(n.endswith(s) for s in ("ready", "rdy", "ack"))

        def _strip_role(n: str) -> str:
            for s in ("valid", "vld", "req", "ready", "rdy", "ack"):
                if n.endswith(s) and len(n) > len(s):
                    return n[: -len(s)]
            return n

        paired: Dict[str, List[str]] = {s.name: [] for s in sigs}
        sigs_norm = [(s, norm.normalize(s.name).normalized) for s in sigs]

        def _try_pair(sig1, sig1_norm, sig2, sig2_norm):
            base1 = _strip_role(sig1_norm)
            base2 = _strip_role(sig2_norm)
            if base1 and base1 == base2:
                if sig1.name not in paired[sig2.name]:
                    paired[sig2.name].append(sig1.name)
                if sig2.name not in paired[sig1.name]:
                    paired[sig1.name].append(sig2.name)

        for i, (sig1, n1) in enumerate(sigs_norm):
            if sig1.width != 1:
                continue
            for sig2, n2 in sigs_norm[i + 1:]:
                if sig2.width != 1:
                    continue
                # 双向检测
                v1, r1 = _is_valid_like(n1), _is_ready_like(n1)
                v2, r2 = _is_valid_like(n2), _is_ready_like(n2)
                # 互补对: 1个是 valid-like, 1个是 ready-like
                if not (v1 and r2) and not (v2 and r1):
                    continue
                # 方向互补: 1 个 output, 1 个 input
                d1, d2 = sig1.direction, sig2.direction
                if not ((d1 == "output" and d2 == "input") or
                        (d1 == "input" and d2 == "output")):
                    continue
                _try_pair(sig1, n1, sig2, n2)
        return paired

    def _safe_get_name(self, mod) -> Optional[str]:
        """安全获取 module 名字."""
        try:
            # 优先 header.name
            header = getattr(mod, "header", None)
            if header:
                name_attr = getattr(header, "name", None)
                if name_attr:
                    return getattr(name_attr, "value", str(name_attr))
            # Fallback
            name_attr = getattr(mod, "name", None)
            if name_attr:
                return getattr(name_attr, "value", str(name_attr))
        except Exception:
            pass
        return None

    def _module_file(self, mod) -> str:
        """获取 module 所在文件 (best effort)."""
        try:
            loc = getattr(mod, "location", None)
            if loc:
                return getattr(loc, "file", "") or ""
        except Exception:
            pass
        return ""

# ==============================================================================
# connection_extractor.py - Connection 提取器 (从 graph_builder.py 物理拆分, P1 cycle 9b)
#
# 职责: 解析 SV 模块实例化, 提取端口到内部信号的连接 (CONNECTION) 关系.
# ==============================================================================

import logging
import re  # [iter_117] get_path 父路径索引段检测 (去重 gen_block)

from .._safe import _safe_str, safe_attr
from .extractor_models import ExtractorResult
from .graph.models import EdgeKind, NodeKind, TraceEdge, TraceNode
from .semantic_adapter import SemanticAdapter

logger = logging.getLogger(__name__)


def _instance_decl_name(inst) -> str:
    """Extract the declared instance name without relying on undefined locals."""
    instances = getattr(inst, "instances", None) or []
    decl = getattr(instances[0], "decl", None) if instances else None
    name = getattr(decl, "name", None)
    if name:
        return str(name).strip()
    return str(inst).split("(")[0].strip()


class ConnectionExtractor:
    def __init__(self, adapter: SemanticAdapter, root_module_name: str | None = None):
        self.adapter = adapter
        # [Phase 3 2026-07-11] Accept target_module as initial root_module_name.
        # If None (legacy), falls back to auto-detect first top instance.
        self.root_module_name = root_module_name

    def _get_parent_module_name(self, inst) -> str:
        """Safely get parent module name from instance (handles generate blocks)."""
        node = inst
        for _ in range(5):
            if not hasattr(node, "parent") or node.parent is None:
                break
            node = node.parent
            if type(node).__name__ == "ModuleDeclarationSyntax":
                if hasattr(node, "header") and hasattr(node.header, "name"):
                    return node.header.name.rawText.strip()
                elif hasattr(node, "name"):
                    return str(safe_attr(node, "name", "")).strip()
        # Fallback: use parent_module if it's a string (actual parent module name)
        # For top-level instances (parent_module is None), return '__root__'
        if hasattr(inst, "parent_module"):
            if inst.parent_module is None:
                return "__root__"
            if isinstance(inst.parent_module, str) and inst.parent_module:
                return inst.parent_module
        # Fallback to type.value or inst_name
        if hasattr(inst, "type") and hasattr(safe_attr(inst, "type", None), "value") and safe_attr(inst, "type", None).value:
            return safe_attr(inst, "type", None).value
        return getattr(inst, "name", "unknown") or "unknown"

    def _get_generate_block_name(self, inst) -> str:
        """Get the generate block label if instance is inside a generate block."""
        # First try parent chain (works for SyntaxTree)
        node = inst
        for _ in range(5):
            if not hasattr(node, "parent") or node.parent is None:
                break
            node = node.parent
            if type(node).__name__ == "GenerateBlockSyntax":
                if hasattr(node, "beginName") and node.beginName:
                    bn = node.beginName
                    if hasattr(bn, "name") and hasattr(bn.name, "value"):
                        return bn.name.value.strip()

        # [FIX] Fallback: try to extract genblock name from hierarchicalPath
        # For SemanticAdapter instances with hierarchicalPath like 'top.gen[0].u_dut'
        if hasattr(inst, "_symbol"):
            try:
                hp = inst._symbol.hierarchicalPath
            except (UnicodeDecodeError, TypeError, Exception):
                hp = None
            if hp:
                try:
                    hp_str = str(hp)
                except (UnicodeDecodeError, TypeError):
                    hp_str = ""
                # [iter_134 fix] gen_block 必须来自实例的**直接宿主** generate,
                # 而非 hp 里任意 [N] 段。hp 格式 `...<gen>[<i>].<inst>` 时
                # gen 是直接宿主 (generate entry 内实例, e.g. aes_top.ROUND[0].
                # U_ROUND → ROUND[0] 是 U_ROUND 宿主);
                # 但 hp `...ROUND[0].U_ROUND.U_SUB` 时 U_SUB 的直接宿主是
                # Round 模块 (非 generate) — ROUND[0] 只是**祖先** generate
                # (Round 被 ROUND[0] 实例化的展开路径), 取它会让 get_path
                # 拼出假节点 U_ROUND.ROUND[0].U_SUB (aes 351 假节点根因)。
                # 判据: 实例名 = hp 最后一段; 其前一段若形如 name[i] 才是
                # 直接宿主 generate; 否则 (前段是普通实例名/模块路径) → None。
                import re as _re
                _hp_segs = hp_str.split(".")
                if len(_hp_segs) >= 2:
                    _inst_seg = _hp_segs[-1]       # e.g. U_ROUND / U_SUB
                    _prev_seg = _hp_segs[-2]       # 直接宿主候选
                    # 前段形如 name[<digits>] → generate-for entry 直接宿主
                    _m = _re.fullmatch(r"([a-zA-Z_][a-zA-Z0-9_]*)\[(\d+)\]", _prev_seg)
                    if _m and not _re.search(r"\[\d+\]$", _inst_seg):
                        # 确认 inst 不在 generate 内? (inst 名自身带 [i] 是数组
                        # 实例, 前段可能是其 generate; 保守: 仅当 inst 名无 [i])
                        return f"{_m.group(1)}[{_m.group(2)}]"
                # 旧逻辑: hp 里任意第一个 [N] 段 — 保留仅当 inst 名本身带
                # 数组索引且其父是 generate 的兼容路径由上方覆盖; 其余不再
                # 取祖先 generate (iter_134: aes 嵌套 generate 假节点根因).
                return None

    @staticmethod
    def _syntax_declares_module(tree, module_name: str) -> bool:
        found = []

        def walk(node):
            if node is None or found:
                return
            if type(node).__name__ == "ModuleDeclarationSyntax":
                header = getattr(node, "header", None)
                name = getattr(header, "name", None)
                if name is not None and str(name).strip() == module_name:
                    found.append(True)
                    return
            try:
                for child in node:
                    walk(child)
            except TypeError:
                logger.debug("module syntax walk: non-iterable node skipped")
                return

        walk(tree.root)
        return bool(found)

    def _module_source_known(self, module_name: str) -> bool:
        """True if a loaded source actually declares this module.

        Parse loaded source as a syntax tree and inspect module declarations;
        a commented-out ``module foo`` or a raw text match is not enough.
        Port extraction can still fail for a real module (same-name package
        function shadowing), which is why the warning text is neutral.
        """
        from pyslang import syntax

        compiler = getattr(self.adapter, "_compiler", None)
        sources = getattr(compiler, "sources", {}) if compiler is not None else {}
        for path, source in sources.items():
            try:
                tree = syntax.SyntaxTree.fromText(source or "", path)
            except Exception:
                continue
            if self._syntax_declares_module(tree, module_name):
                return True
        return False

    def _missing_module_warning(self, inst_module_name: str, inst_name: str):
        """输出可能缺少文件的警告信息"""
        import logging

        logger = logging.getLogger("sv_query")
        msg = (
            f"[sv_query] 可能缺少文件: 实例 '{inst_name}' 的模块 '{inst_module_name}' "
            f"没有找到端口定义。\n"
            f"  → 可能原因: 解析的文件范围不完整,缺少 '{inst_module_name}' 的定义文件\n"
            f"  → 建议: 确保传入所有相关的 Verilog 文件,或使用 glob 模式匹配整个目录\n"
            f"  → 例如: sv_query 'path/to/**/*.v' (递归) 或 sv_query 'file1.v file2.v' (多文件)"
        )
        logger.warning(msg)
        # 同时记录到 ExtractorResult.warnings 中
        if not hasattr(self, "_warnings"):
            self._warnings = []
        self._warnings.append(
            f"Unresolved module ports: {inst_module_name} (instance: {inst_name})")

    def _ensure_root_module(self) -> None:
        if self.root_module_name is not None:
            return
        trees = getattr(self.adapter.parser, "trees", {})
        if trees:
            tree_key = list(trees.keys())[0]
            actual_modules = [self.adapter.get_module_name(m) for m in self.adapter.get_modules()]
            if tree_key in actual_modules:
                self.root_module_name = tree_key
                return
            instances = self.adapter.get_module_instances()
            instantiated_modules = set()
            for inst in instances:
                typ = safe_attr(inst, "type", None)
                if hasattr(typ, "value"):
                    instantiated_modules.add(safe_attr(inst, "type", None).value.strip())
            for mod in self.adapter.get_modules():
                mod_name = self.adapter.get_module_name(mod)
                if mod_name not in instantiated_modules:
                    self.root_module_name = mod_name
                    return
            self.root_module_name = actual_modules[0] if actual_modules else tree_key
            return
        for mod in self.adapter.get_modules():
            self.root_module_name = self.adapter.get_module_name(mod)
            return

    @staticmethod
    def _width_tuple(width):
        if not isinstance(width, dict):
            return width
        msb = width.get("msb_eval", width.get("msb_raw", 0))
        lsb = width.get("lsb_eval", width.get("lsb_raw", 0))
        try:
            msb = int(msb) if msb is not None else 0
        except (ValueError, TypeError):
            msb = 0
        try:
            lsb = int(lsb) if lsb is not None else 0
        except (ValueError, TypeError):
            lsb = 0
        return (msb, lsb)

    def _interface_for_port(self, port):
        idef = getattr(port, "interfaceDef", None)
        if idef is None:
            return None
        try:
            iface_name = str(getattr(idef, "name", "")) or ""
            members = self.adapter.get_interface_members(port)
            return (iface_name, list(members)) if iface_name and members else None
        except Exception as exc:
            logger.debug("interface 端口收集失败: %s", exc)
            return None

    def _collect_one_module(self, module):
        module_name = self.adapter.get_module_name(module)
        port_dirs = {}
        port_widths = {}
        iface_ports = {}
        for port in self.adapter.get_port_declarations(module):
            name, direction = self.adapter.get_port_name_and_direction(port)
            port_dirs[name] = direction.strip()
            iface = self._interface_for_port(port)
            if iface is not None:
                iface_ports[name] = iface
            port_widths[name] = self._width_tuple(
                self.adapter.extract_port_width(port, scope=module))
        return module_name, port_dirs, port_widths, iface_ports

    def _collect_module_metadata(self):
        all_module_ports = {}
        all_module_widths = {}
        all_interface_ports = {}
        getter = getattr(self.adapter, "get_all_module_definitions",
                         self.adapter.get_modules)
        for module in getter():
            name, ports, widths, ifaces = self._collect_one_module(module)
            all_module_ports[name] = ports
            all_module_widths[name] = widths
            if ifaces:
                all_interface_ports[name] = ifaces
        return all_module_ports, all_module_widths, all_interface_ports

    def _module_name_for_instance(self, inst) -> str:
        typ = safe_attr(inst, "type", None)
        inst_type_value = typ.value.strip() if hasattr(typ, "value") and typ.value else ""
        _def_name = ""
        try:
            _def = getattr(inst, "definition", None)
            if _def is not None:
                _def_name = _safe_str(getattr(_def, "name", ""))
        except Exception as e:
            logger.debug("def_name 提取失败: %s", e)
        if _def_name:
            return _def_name
        if inst_type_value:
            return inst_type_value
        return self._get_parent_module_name(inst)

    def _collect_instances_info(self, instances) -> list[dict]:
        infos = []
        for inst in instances:
            infos.append({
                "inst_module_name": self._module_name_for_instance(inst),
                "inst_name": _instance_decl_name(inst),
                "parent_module": self._get_parent_module_name(inst),
                "gen_block": self._get_generate_block_name(inst),
            })
        return infos

    @staticmethod
    def _prefixed(prefix: str, gen_block: str | None, name: str) -> str:
        return f"{prefix}.{gen_block}.{name}" if gen_block else f"{prefix}.{name}"

    def _path_for_nonroot(self, info, instances_info, parent_mod, gen_block, depth):
        is_submodule = any(
            other["inst_module_name"] == parent_mod for other in instances_info)
        if not is_submodule:
            return self._prefixed(parent_mod, gen_block, info["inst_name"])
        for other_info in instances_info:
            if other_info is info or other_info["inst_module_name"] != parent_mod:
                continue
            parent_path = self._path_for_instance(other_info, instances_info, depth + 1)
            return self._prefixed(parent_path, gen_block, info["inst_name"])
        return self._prefixed(self.root_module_name, gen_block, info["inst_name"])

    def _path_for_instance(self, info, instances_info, depth: int = 0) -> str:
        if depth > 20:
            return f"{self.root_module_name}.{info['inst_name']}"
        parent_mod = info["parent_module"]
        gen_block = info.get("gen_block")
        if gen_block and parent_mod and re.search(r"\[\d+\]$", parent_mod):
            gen_block = None
        if parent_mod == "__root__":
            if info["inst_module_name"] == "__root__" and not gen_block:
                return info["inst_name"]
            return self._prefixed(self.root_module_name, gen_block, info["inst_name"])
        if parent_mod == "top":
            return self._prefixed(self.root_module_name, gen_block, info["inst_name"])
        return self._path_for_nonroot(info, instances_info, parent_mod, gen_block, depth)

    def _resolve_instance_paths(self, instances_info: list[dict]) -> list[str]:
        return [self._path_for_instance(info, instances_info) for info in instances_info]

    @staticmethod
    def _instance_signal_scope(inst_path: str) -> str | None:
        segs = inst_path.split(".")
        if len(segs) < 2:
            return None
        mod_segs = segs[:-1]
        while mod_segs and "[" in mod_segs[-1]:
            mod_segs.pop()
        return ".".join(mod_segs) if mod_segs else None

    @staticmethod
    def _normalise_connections(module_ports: dict, conns) -> dict:
        named = {}
        positional = []
        for port_key, signal_name in conns:
            if port_key.startswith("_pos_"):
                positional.append((int(port_key.replace("_pos_", "")), signal_name))
            else:
                named[port_key] = signal_name
        positional.sort(key=lambda item: item[0])
        port_names = list(module_ports.keys())
        for idx, signal_name in positional:
            if idx < len(port_names):
                named[port_names[idx]] = signal_name
        return named

    def _gen_local_names(self, parent_path: str) -> set[str]:
        if not parent_path:
            return set()
        index = getattr(self, "_gen_locals_index", None)
        if index is None:
            getter = getattr(self.adapter, "get_generate_locals_index", None)
            index = getter() if callable(getter) else {}
            self._gen_locals_index = index
        return index.get(parent_path, set())

    def _add_generate_node(self, result, gen_path: str, gen_block: str) -> None:
        if any(node.id == gen_path for node in result.nodes):
            return
        gen_module = ".".join(gen_path.rsplit(".", 1)[:-1]) or gen_path.rsplit(".", 1)[0]
        result.nodes.append(TraceNode(
            id=gen_path, name=gen_block, module=gen_module,
            kind=NodeKind.GENERATE_BLOCK
            if hasattr(NodeKind, "GENERATE_BLOCK") else NodeKind.INSTANTIATED_MODULE,
            width=(1, 0), is_port=False))

    def _add_instance_node(self, result, inst_path: str, inst_name: str,
                           inst_module_name: str) -> None:
        result.nodes.append(TraceNode(
            id=inst_path, name=inst_name, module=inst_module_name,
            kind=NodeKind.INSTANTIATED_MODULE, width=(1, 0), is_port=False))

    @staticmethod
    def _port_kind(direction: str):
        if "inout" in direction.lower():
            return NodeKind.PORT_INOUT
        if "output" in direction.lower():
            return NodeKind.PORT_OUT
        return NodeKind.PORT_IN

    @staticmethod
    def _port_extra(port_name: str, module_ports: dict, direction: str,
                    inst_module_name: str) -> dict:
        if port_name not in module_ports:
            logger.warning(
                "[connection_extractor] port '%s' not in module_ports for %s; "
                "falling back to PORT_IN (likely ref port or missing module def)",
                port_name, inst_module_name)
            return {"direction": "missing", "fallback": "PORT_IN"}
        if direction == "unknown":
            logger.warning(
                "[connection_extractor] port '%s' direction unknown for %s; "
                "falling back to PORT_IN (likely ref port or unparsed direction)",
                port_name, inst_module_name)
            return {"direction": "unknown", "fallback": "PORT_IN"}
        return {"direction": direction.lower()}

    @staticmethod
    def _port_width(all_module_widths: dict, inst_module_name: str,
                    port_name: str, signal_name: str, inst_path: str) -> tuple:
        width = all_module_widths.get(inst_module_name, {}).get(port_name)
        if width is None:
            logger.warning(
                "[connection_extractor] port '%s' width missing for %s; "
                "falling back to (1,0)", port_name, inst_module_name)
            width = (1, 0)
        if width == (0, 0) and signal_name:
            parent_path = inst_path.rsplit(".", 1)[0] if "." in inst_path else "top"
            parent_widths = all_module_widths.get(parent_path, {})
            if signal_name in parent_widths:
                width = parent_widths[signal_name]
        return width

    def _connect_input(self, result, inst_path: str, inst_port_id: str,
                       port_name: str, signal_name: str, parent_path: str,
                       gen_parent_path: str, gen_locals: set[str],
                       sig_scope: str | None) -> None:
        if signal_name in gen_locals and gen_parent_path:
            sig_parent = gen_parent_path
        else:
            sig_parent = sig_scope if sig_scope else parent_path
        parent_sig = f"{sig_parent}.{signal_name}"
        if parent_sig != inst_port_id:
            result.edges.append(TraceEdge(
                src=parent_sig, dst=inst_port_id,
                kind=EdgeKind.CONNECTION, assign_type="connection"))
        child_signal_id = f"{inst_path}.{port_name}"
        if child_signal_id != inst_port_id:
            result.edges.append(TraceEdge(
                src=inst_port_id, dst=child_signal_id,
                kind=EdgeKind.CONNECTION, assign_type="internal"))

    def _connect_output(self, result, inst_path: str, inst_port_id: str,
                        port_name: str, signal_name: str, parent_path: str,
                        gen_parent_path: str, gen_locals: set[str],
                        sig_scope: str | None) -> None:
        child_signal_id = f"{inst_path}.{port_name}"
        if signal_name in gen_locals and gen_parent_path:
            sig_parent = gen_parent_path
        else:
            sig_parent = sig_scope if sig_scope else parent_path
        parent_signal = f"{sig_parent}.{signal_name}"
        if child_signal_id != inst_port_id:
            result.edges.append(TraceEdge(
                src=child_signal_id, dst=inst_port_id,
                kind=EdgeKind.DRIVER, assign_type="internal"))
        if parent_signal != inst_port_id:
            result.edges.append(TraceEdge(
                src=inst_port_id, dst=parent_signal,
                kind=EdgeKind.CONNECTION, assign_type="connection"))

    def _connect_inout(self, result, inst_port_id: str, signal_name: str,
                       parent_path: str, gen_parent_path: str,
                       gen_locals: set[str], sig_scope: str | None) -> None:
        if signal_name in gen_locals and gen_parent_path:
            scope = gen_parent_path
        else:
            scope = sig_scope if sig_scope else parent_path
        parent = f"{scope}.{signal_name}"
        if parent != inst_port_id:
            result.edges.append(TraceEdge(
                src=inst_port_id, dst=parent,
                kind=EdgeKind.CONNECTION, assign_type="connection"))

    def _extract_port(self, result, inst_path: str, inst_module_name: str,
                      signal_name: str, port_name: str, direction: str,
                      module_ports: dict, all_widths: dict,
                      iface_info, parent_path: str, gen_parent_path: str,
                      gen_locals: set[str], sig_scope: str | None) -> None:
        port_name = self.adapter.clean_name(port_name)
        signal_name = self.adapter.clean_name(signal_name)
        direction = module_ports.get(port_name, "unknown").strip()
        iface = (iface_info or {}).get(port_name)
        if iface is not None:
            iface_name, iface_members = iface
            iface_scope = sig_scope if sig_scope else parent_path
            result.interface_links.append(
                (inst_path, port_name, iface_name, list(iface_members),
                 f"{iface_scope}.{signal_name}"))
        kind = self._port_kind(direction)
        extra = self._port_extra(port_name, module_ports, direction, inst_module_name)
        width = self._port_width(all_widths, inst_module_name, port_name,
                                 signal_name, inst_path)
        inst_port_id = f"{inst_path}.{port_name}"
        lower = port_name.lower()
        result.nodes.append(TraceNode(
            id=inst_port_id, name=port_name, module=inst_path, kind=kind,
            width=width, is_port=True,
            is_clock=("clk" in lower), is_reset=("rst" in lower),
            extra={**extra, "width": width}))
        if iface is not None:
            return
        direction_clean = direction.strip()
        parent_path = inst_path.rsplit(".", 1)[0] if "." in inst_path else "top"
        if direction_clean == "input":
            self._connect_input(result, inst_path, inst_port_id, port_name,
                                signal_name, parent_path, gen_parent_path,
                                gen_locals, sig_scope)
        elif direction_clean == "output":
            self._connect_output(result, inst_path, inst_port_id, port_name,
                                 signal_name, parent_path, gen_parent_path,
                                 gen_locals, sig_scope)
        elif "inout" in direction_clean:
            self._connect_inout(result, inst_port_id, signal_name, parent_path,
                                gen_parent_path, gen_locals, sig_scope)

    @staticmethod
    def _symbol_port_direction(port, fallback: str) -> str:
        raw = str(getattr(port, "direction", "") or "").lower()
        if "inout" in raw:
            return "inout"
        if "out" in raw:
            return "output"
        if "in" in raw:
            return "input"
        return fallback

    @classmethod
    def _instance_port_metadata(cls, inst, base_ports: dict, base_widths: dict):
        """Use the elaborated instance's port symbols when module metadata is weak."""
        ports = dict(base_ports)
        widths = dict(base_widths)
        symbol = getattr(inst, "_symbol", inst)
        for conn in getattr(symbol, "portConnections", ()) or ():
            port = getattr(conn, "port", None)
            name = str(getattr(port, "name", "") or "")
            if not name:
                continue
            ports[name] = cls._symbol_port_direction(
                port, ports.get(name, "unknown"))
            bw = getattr(getattr(port, "type", None), "bitWidth", None)
            if isinstance(bw, int) and bw > 0:
                widths[name] = (0, 0) if bw == 1 else (bw - 1, 0)
        return ports, widths

    def _extract_connections(self, instances, infos, paths, all_ports,
                             all_widths, all_iface, result) -> None:
        for idx, inst in enumerate(instances):
            info = infos[idx]
            inst_name = info["inst_name"]
            inst_module_name = info["inst_module_name"]
            inst_path = paths[idx]
            gen_block = info.get("gen_block")
            sig_scope = self._instance_signal_scope(inst_path)
            module_ports, instance_widths = self._instance_port_metadata(
                inst, all_ports.get(inst_module_name, {}),
                all_widths.get(inst_module_name, {}))
            all_widths = {**all_widths, inst_module_name: instance_widths}
            conns = self.adapter.get_instance_connection(inst)
            if not module_ports and conns and not self._module_source_known(inst_module_name):
                self._missing_module_warning(inst_module_name, inst_name)
            named_conns = self._normalise_connections(module_ports, conns)
            parent_path = inst_path.rsplit(".", 1)[0] if "." in inst_path else ""
            gen_parent_path = parent_path
            gen_locals = self._gen_local_names(gen_parent_path)
            if gen_block:
                self._add_generate_node(result, inst_path.rsplit(".", 1)[0], gen_block)
            self._add_instance_node(result, inst_path, inst_name, inst_module_name)
            iface_info = all_iface.get(inst_module_name, {})
            for port_name, signal_name in named_conns.items():
                self._extract_port(
                    result, inst_path, inst_module_name, signal_name, port_name,
                    module_ports.get(port_name, "unknown"), module_ports,
                    all_widths, iface_info, parent_path, gen_parent_path,
                    gen_locals, sig_scope)

    @staticmethod
    def _find_node(nodes, node_id: str):
        return next((node for node in nodes if node.id == node_id), None)

    @classmethod
    def _backfill_one_edge(cls, result, edge) -> None:
        if edge.kind != EdgeKind.CONNECTION:
            return
        src_node = cls._find_node(result.nodes, edge.src)
        dst_node = cls._find_node(result.nodes, edge.dst)
        if not src_node or not dst_node:
            return
        parts = dst_node.id.split(".")
        if len(parts) < 3 or not dst_node.kind.name.startswith("PORT_"):
            return
        if dst_node.width != (1, 0) or src_node.width == (0, 0):
            return
        result.nodes = [
            TraceNode(id=n.id, name=n.name, module=n.module, kind=n.kind,
                      width=src_node.width, is_port=n.is_port)
            if n.id == dst_node.id else n
            for n in result.nodes
        ]

    @classmethod
    def _backfill_connection_widths(cls, result) -> None:
        for edge in result.edges:
            cls._backfill_one_edge(result, edge)

    def extract(self) -> ExtractorResult:
        result = ExtractorResult()
        self._warnings = []
        self._ensure_root_module()
        instances = self.adapter.get_module_instances()
        all_ports, all_widths, all_iface = self._collect_module_metadata()
        infos = self._collect_instances_info(instances)
        paths = self._resolve_instance_paths(infos)
        self._extract_connections(instances, infos, paths, all_ports,
                                  all_widths, all_iface, result)
        self._backfill_connection_widths(result)
        if self._warnings:
            result.warnings = self._warnings
        return result

# ==============================================================================
# connection_extractor.py - Connection 提取器 (从 graph_builder.py 物理拆分, P1 cycle 9b)
#
# 职责: 解析 SV 模块实例化, 提取端口到内部信号的连接 (CONNECTION) 关系.
# ==============================================================================

import logging
import re  # [iter_117] get_path 父路径索引段检测 (去重 gen_block)

from .._safe import _safe_str
from .base import PyslangAdapter
from .extractor_models import ExtractorResult
from .graph.models import EdgeKind, NodeKind, TraceEdge, TraceNode

logger = logging.getLogger(__name__)


class ConnectionExtractor:
    def __init__(self, adapter: PyslangAdapter, root_module_name: str | None = None):
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
                    return node.name.rawText.strip()
        # Fallback: use parent_module if it's a string (actual parent module name)
        # For top-level instances (parent_module is None), return '__root__'
        if hasattr(inst, "parent_module"):
            if inst.parent_module is None:
                return "__root__"
            if isinstance(inst.parent_module, str) and inst.parent_module:
                return inst.parent_module
        # Fallback to type.value or inst_name
        if hasattr(inst, "type") and hasattr(inst.type, "value") and inst.type.value:
            return inst.type.value
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
        self._warnings.append(f"Missing module: {inst_module_name} (instance: {inst_name})")

    def extract(self) -> ExtractorResult:
        result = ExtractorResult()

        # [FIX Issue 20] 初始化 warnings 列表
        self._warnings = []

        # [FIX Issue 19] 动态获取根模块名而非硬编码 "top"
        # 优先从 trees 的键中获取根模块名(trees 包含当前处理的文件),
        # 如果没有则使用第一个模块
        if self.root_module_name is None:
            trees = getattr(self.adapter.parser, "trees", {})
            if trees:
                # trees 的键是 tree 文件的键,不一定等于实际模块名
                # 需要验证该键是否对应实际模块,否则使用实际模块名
                tree_key = list(trees.keys())[0]
                actual_modules = [self.adapter.get_module_name(m) for m in self.adapter.get_modules()]
                if tree_key in actual_modules:
                    self.root_module_name = tree_key
                else:
                    # tree key 与实际模块名不匹配,查找包含实例的模块
                    # 找到没有被其他模块实例化的模块(顶层模块)
                    instances = self.adapter.get_module_instances()
                    # [iter_120] 不再叠加 legacy get_generate_instances 族:
                    # iter_117 修了 indexed 族 get_path 的 gen_block 去重后,
                    # legacy 族 (iter_113 曾因路径加倍而保留) 已非必需 — 且 legacy
                    # 对嵌套模块取父路径丢 root ('u_m2.G2[0]' 缺 'top') → 同 key
                    # 覆盖正确 indexed 路径 → 实例连接整条消失 (iter_119 观察).
                    # 移除后 generate 实例只走 indexed 族 (hp 全路径, iter_109/117)

                    # 收集所有被实例化的模块名
                    instantiated_modules = set()
                    for inst in instances:
                        if hasattr(inst, "type") and hasattr(inst.type, "value"):
                            instantiated_modules.add(inst.type.value.strip())

                    # 找到没有被实例化的模块(顶层模块)
                    for mod in self.adapter.get_modules():
                        mod_name = self.adapter.get_module_name(mod)
                        if mod_name not in instantiated_modules:
                            self.root_module_name = mod_name
                            break

                    # 如果没找到,使用第一个实际模块
                    if self.root_module_name is None:
                        self.root_module_name = actual_modules[0] if actual_modules else tree_key
            else:
                for mod in self.adapter.get_modules():
                    self.root_module_name = self.adapter.get_module_name(mod)
                    break

        trees = getattr(self.adapter.parser, "trees", {})
        instances = self.adapter.get_module_instances()
        # [iter_120] legacy 族移除 (见上; iter_117 后非必需且嵌套时丢 root)

        # 收集所有模块的端口定义 (方向和位宽)
        all_module_ports = {}
        all_module_widths = {}
        # [iter_129] interface 类型端口: module_name → {port_name: (interface_def_name, members)}
        all_interface_ports: dict[str, dict[str, tuple[str, list[str]]]] = {}
        for module in self.adapter.get_modules():
            module_name = self.adapter.get_module_name(module)
            port_dirs = {}
            port_widths = {}
            iface_ports: dict[str, tuple[str, list[str]]] = {}
            for port in self.adapter.get_port_declarations(module):
                name, direction = self.adapter.get_port_name_and_direction(port)
                port_dirs[name] = direction.strip()
                # [iter_129] InterfacePortSymbol (kind=SymbolKind.InterfacePort,
                # 有 interfaceDef): 收集接口名 + 成员信号, 供实例层成员桥
                _idef = getattr(port, "interfaceDef", None)
                if _idef is not None:
                    try:
                        iface_name = str(getattr(_idef, "name", "")) or ""
                        members = self.adapter.get_interface_members(port)
                        if iface_name and members:
                            iface_ports[name] = (iface_name, list(members))
                    except Exception as _e:
                        logger.debug("interface 端口收集失败: %s", _e)
                # 获取位宽 (传入 module 作为 scope 以解析参数)
                width = self.adapter.extract_port_width(port, scope=module)
                # extract_port_width with scope returns dict, convert to tuple for compatibility
                if isinstance(width, dict):
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
                    width = (msb, lsb)
                port_widths[name] = width
            all_module_ports[module_name] = port_dirs
            all_module_widths[module_name] = port_widths
            if iface_ports:
                all_interface_ports[module_name] = iface_ports

        # [FIX] 第一阶段:收集所有实例信息
        instances_info = []  # [(inst_module_name, inst_name, parent_module)]

        for inst in instances:
            inst_name = (
                inst.instances[0].decl.name.value.strip()
                if hasattr(inst.instances[0], "decl")
                and hasattr(inst.instances[0].decl, "name")
                and inst.instances[0].decl.name.value
                else str(inst).split("(")[0].strip()
            )

            inst_type_value = inst.type.value.strip() if hasattr(inst.type, "value") and inst.type.value else ""
            # [PR1 2026-06-14] 优先用 inst.definition.name (真实 def_name)
            _def_name = ""
            try:
                _def = getattr(inst, "definition", None)
                if _def is not None:
                    _def_name = _safe_str(getattr(_def, "name", ""))
            except Exception as e:
                logger.debug("def_name 提取失败: %s", e)
                pass
            if _def_name:
                # [iter_113] 去掉 '!= inst_name' 守卫: 实例名 == 模块类型名是惯用法
                # (cell4 cell4(...)), def_name 权威, 直接采用
                inst_module_name = _def_name
            elif inst_type_value:
                # type token (native wrapper 存 definition.name) = 模块类型, 权威 —
                # 即使 == inst_name 也直接采用 (旧守卫在 inst==type 时错误回落
                # parent_module → inst_module_name==parent → get_path 自环递归,
                # CLA cell4 cell4 复现, 同 iter_112 原语根因型)
                inst_module_name = inst_type_value
            else:
                inst_module_name = self._get_parent_module_name(inst)
            parent_module = self._get_parent_module_name(inst)

            gen_block = self._get_generate_block_name(inst)
            instances_info.append(
                {
                    "inst_module_name": inst_module_name,
                    "inst_name": inst_name,
                    "parent_module": parent_module,
                    "gen_block": gen_block,
                }
            )

        # [FIX] 第二阶段:构建模块 -> 实例路径的映射
        module_to_path = {}  # (inst_module_name, inst_name) -> full_path

        # 递归确定路径
        def get_path(info: dict, depth: int = 0) -> str:
            """递归获取实例的完整路径"""
            if depth > 20:
                return f"{self.root_module_name}.{info['inst_name']}"
            parent_mod = info["parent_module"]
            gen_block = info.get("gen_block")

            # [iter_117] 父路径已含 generate 索引段 → gen_block 已在 parent 里,
            # 置 None 防二次拼接 (iter_116 摸底: aes U_SUB.ROM[4].ROM[4] ×84 /
            # dblclockfft ...GENSTAGES[0].GENSTAGES[0] ×63 — 实例在 generate-for
            # entry 内, 其 hp 父路径 '...GENSTAGES[0]' 已带索引, _get_generate_block_name
            # 的 hp 正则又取一次 'GENSTAGES[0]' → get_path 拼成双段假节点).
            # genfor/CLA 没炸是 legacy get_generate_instances 族同 key 覆盖掩盖;
            # 无 legacy 族 (generate 在嵌套实例内) 即暴露 — 此处去重是根因修。
            if gen_block and parent_mod and re.search(r"\[\d+\]$", parent_mod):
                gen_block = None

            # Handle '__root__' specially - instance is at top level
            if parent_mod == "__root__":
                if gen_block:
                    return f"{self.root_module_name}.{gen_block}.{info['inst_name']}"
                # Special case: if inst_module_name is also '__root__',
                # this instance IS the root module (not a sub-instance)
                if info["inst_module_name"] == "__root__":
                    return info["inst_name"]
                return f"{self.root_module_name}.{info['inst_name']}"
            elif parent_mod == "top":
                if gen_block:
                    return f"{self.root_module_name}.{gen_block}.{info['inst_name']}"
                return f"{self.root_module_name}.{info['inst_name']}"
            else:
                # parent_mod is not in instances_info
                # Determine if it's a top-level module (use parent_mod as prefix)
                # or a submodule of root (use root_module_name as prefix)
                #
                # Heuristic: if parent_mod appears as inst_module_name in instances_info,
                # then it's a submodule (instances of it exist elsewhere), use root_module_name.
                # Otherwise, it's a top-level module, use parent_mod as prefix.
                parent_is_submodule_of_root = any(
                    info["inst_module_name"] == parent_mod for info in instances_info
                )
                if not parent_is_submodule_of_root:
                    # parent_mod is a top-level module, not in instances_info
                    # Use parent_mod as the path prefix (this fixes wrong root_module_name fallback)
                    if gen_block:
                        return f"{parent_mod}.{gen_block}.{info['inst_name']}"
                    return f"{parent_mod}.{info['inst_name']}"
                # parent_mod is a submodule of root, use root_module_name fallback
                # [iter_112] 防自环: 跳过 other_info is info (自身). 根因是门级原语
                # inst_module_name 回落成 parent_module → parent 匹配到它自己 →
                # 无限递归被 depth>20 截断成 `top.and0.and0...` ×21 假节点.
                # 原语现在在 adapter 层被过滤 (非模块实例), 此 guard 兜底同类
                # "实例的模块名 == 其父路径" 的自匹配, 保证任何输入不递归自环。
                for other_info in instances_info:
                    if other_info is info:
                        continue
                    if other_info["inst_module_name"] == parent_mod:
                        parent_path = get_path(other_info, depth + 1)
                        if gen_block:
                            return f"{parent_path}.{gen_block}.{info['inst_name']}"
                        return f"{parent_path}.{info['inst_name']}"
                # Fallback (should not reach here if parent_is_submodule_of_root check works)
                if gen_block:
                    return f"{self.root_module_name}.{gen_block}.{info['inst_name']}"
                return f"{self.root_module_name}.{info['inst_name']}"

        for info in instances_info:
            path = get_path(info)
            gen_block = info.get("gen_block")
            if gen_block:
                key = (info["inst_module_name"], info["inst_name"], gen_block)
            else:
                key = (info["inst_module_name"], info["inst_name"])
            module_to_path[key] = path
        # [iter_120] path_by_info: 与 instances_info 对齐的逐实例路径 —
        # module_to_path 的 key (module, name, gen) 不含**父实例路径**, 同一模块
        # 多实例 (如 G1[0]/G1[1] 各含 m2, m2 内同名 G2 entry) 会 key 碰撞 →
        # 后写覆盖 → 部分实例的连接丢失/错挂 (iter_119 观察 G2[0] 归属).
        # 第三阶段用同序索引直接取逐实例路径, 不再查碰撞 key.
        paths_by_info = [get_path(info) for info in instances_info]

        # [FIX] 第三阶段:使用正确路径创建节点和边
        for _idx, inst in enumerate(instances):
            inst_name = (
                inst.instances[0].decl.name.value.strip()
                if hasattr(inst.instances[0], "decl")
                and hasattr(inst.instances[0].decl, "name")
                and inst.instances[0].decl.name.value
                else str(inst).split("(")[0].strip()
            )

            inst_type_value = inst.type.value.strip() if hasattr(inst.type, "value") and inst.type.value else ""
            # [PR1 2026-06-14] 优先用 inst.definition.name (真实 def_name)
            _def_name = ""
            try:
                _def = getattr(inst, "definition", None)
                if _def is not None:
                    _def_name = _safe_str(getattr(_def, "name", ""))
            except Exception as e:
                logger.debug("def_name 提取失败: %s", e)
                pass
            if _def_name:
                # [iter_113] def_name 权威, 直接采用 (实例名==类型名是惯用法)
                inst_module_name = _def_name
            elif inst_type_value:
                # [iter_113] type token (native wrapper 存 definition.name) = 模块类型,
                # 权威 — 即使 == inst_name 也采用; 旧守卫 inst==type 时回落 parent →
                # inst_module_name==parent → get_path 自环递归 (CLA cell4 cell4)
                inst_module_name = inst_type_value
            else:
                inst_module_name = self._get_parent_module_name(inst)

            gen_block = self._get_generate_block_name(inst)
            if gen_block:
                key = (inst_module_name, inst_name, gen_block)
                inst_path = module_to_path.get(key, f"{self.root_module_name}.{gen_block}.{inst_name}")
            else:
                key = (inst_module_name, inst_name)
                inst_path = module_to_path.get(key, f"{self.root_module_name}.{inst_name}")

            # [iter_120] 逐实例路径优先 (paths_by_info 与 instances 同序, 无 key 碰撞)
            if _idx < len(paths_by_info):
                inst_path = paths_by_info[_idx]

            # [iter_109/110] 连接信号作用域 = 实例的宿主模块路径:
            # inst_path 去掉末尾实例名 + 所有尾部 "[N]" generate 段.
            # top.g[2].U → top (信号 top.arr[2]); 嵌套 cordic.g[0].U.g[0].x_shifter
            # → cordic.g[0].U (rotator 宿主模块, 信号取 rotator 作用域).
            # (原 iter_109 只剥第一个 generate 段 → 嵌套实例错落到根模块作用域,
            #  rotator 的 x_i 误连到顶层 x_i)
            _sig_scope = None
            _segs = inst_path.split(".")
            if len(_segs) >= 2:
                _mod_segs = _segs[:-1]           # 去掉实例名
                while _mod_segs and "[" in _mod_segs[-1]:
                    _mod_segs.pop()               # 去掉尾部 generate 段 ([N])
                if _mod_segs:
                    _sig_scope = ".".join(_mod_segs)

            module_ports = all_module_ports.get(inst_module_name, {})
            conns = self.adapter.get_instance_connection(inst)

            # [FIX Issue 20] 检测可能缺少文件的情况
            if not module_ports and conns:
                # 实例有连接但模块没有端口定义,可能是缺少了实例模块的文件
                self._missing_module_warning(inst_module_name, inst_name)

            named_conns = {}
            positional_conns = []

            for port_key, signal_name in conns:
                if port_key.startswith("_pos_"):
                    idx = int(port_key.replace("_pos_", ""))
                    positional_conns.append((idx, signal_name))
                else:
                    named_conns[port_key] = signal_name

            positional_conns.sort(key=lambda x: x[0])
            port_names = list(module_ports.keys())

            for idx, signal_name in positional_conns:
                if idx < len(port_names):
                    port_name = port_names[idx]
                    named_conns[port_name] = signal_name

            # 如果在 generate block 中,创建 generate block 容器节点
            if gen_block:
                gen_path = inst_path.rsplit(".", 1)[0]  # e.g., top.GEN from top.GEN.g
                gen_module = (
                    ".".join(gen_path.rsplit(".", 1)[:-1]) or gen_path.rsplit(".", 1)[0]
                )  # e.g., top from top.GEN
                # 检查是否已经存在
                if not any(n.id == gen_path for n in result.nodes):
                    result.nodes.append(
                        TraceNode(
                            id=gen_path,
                            name=gen_block,
                            module=gen_module,
                            kind=NodeKind.GENERATE_BLOCK
                            if hasattr(NodeKind, "GENERATE_BLOCK")
                            else NodeKind.INSTANTIATED_MODULE,
                            width=(1, 0),
                            is_port=False,
                        )
                    )

            # 创建实例父节点
            result.nodes.append(
                TraceNode(
                    id=inst_path,
                    name=inst_name,
                    module=inst_module_name,  # [PR1 2026-06-14] fix: was inst_path.rsplit — use actual def_name
                    kind=NodeKind.INSTANTIATED_MODULE,
                    width=(1, 0),
                    is_port=False,
                )
            )

            # 为每个端口创建节点和边
            for port_name, signal_name in named_conns.items():
                port_name = self.adapter.clean_name(port_name)
                signal_name = self.adapter.clean_name(signal_name)

                direction = module_ports.get(port_name, "unknown").strip()
                # [iter_129] interface 类型端口 (模块端口声明 bus_if b):
                # 收集成员级连接信息 (inst_path, port_name, iface, members,
                # parent 前缀), 供 graph_builder 后处理建成员桥。节点仍创建
                # (PORT_IN kind, 兼容既有查询), 但跳过普通 input/output/inout
                # 方向边 — interface 是共享总线, 方向由实例内部是否驱动成员
                # 决定 (后处理检测 incoming DRIVER)。
                _iface_info = (all_interface_ports.get(inst_module_name, {})
                               .get(port_name))
                if _iface_info is not None:
                    _iface_name, _iface_members = _iface_info
                    _iface_parent_scope = _sig_scope if _sig_scope else parent_path
                    result.interface_links.append(
                        (inst_path, port_name, _iface_name,
                         list(_iface_members),
                         f"{_iface_parent_scope}.{signal_name}")
                    )

                inst_port_id = f"{inst_path}.{port_name}"
                # [FIX 2026-08-27 18:56] Bug #2: 端口方向未识别不再静默 fallback
                # 区分两种情况: (a) 端口在 module_ports 缺失 (ref port / 拼写错 / 模块定义不全)
                #             (b) direction 是 'unknown' 字符串 (get_port_name_and_direction 返默认值)
                # 之前两者都静默落 PORT_IN, 违反 AGENTS.md §2 禁止 silent fallback.
                # 现在: 未识别时 logger.warning + extra 记实际 direction, 行为仍取 PORT_IN (兼容).
                if port_name not in module_ports:
                    logger.warning(
                        "[connection_extractor] port '%s' not in module_ports for %s; "
                        "falling back to PORT_IN (likely ref port or missing module def)",
                        port_name, inst_module_name,
                    )
                    port_extra = {"direction": "missing", "fallback": "PORT_IN"}
                elif direction == "unknown":
                    logger.warning(
                        "[connection_extractor] port '%s' direction unknown for %s; "
                        "falling back to PORT_IN (likely ref port or unparsed direction)",
                        port_name, inst_module_name,
                    )
                    port_extra = {"direction": "unknown", "fallback": "PORT_IN"}
                else:
                    port_extra = {"direction": direction.lower()}

                if "inout" in direction.lower():
                    kind = NodeKind.PORT_INOUT
                elif "output" in direction.lower():
                    kind = NodeKind.PORT_OUT
                else:
                    kind = NodeKind.PORT_IN
                # 获取端口位宽
                port_widths = all_module_widths.get(inst_module_name, {})
                width = port_widths.get(port_name, (1, 0))

                # [NEW] 如果位宽为 (0,0),尝试从父模块的信号宽度推断
                if width == (0, 0) and signal_name:
                    parent_path = inst_path.rsplit(".", 1)[0] if "." in inst_path else "top"
                    parent_widths = all_module_widths.get(parent_path, {})
                    if signal_name in parent_widths:
                        width = parent_widths[signal_name]

                # [FIX 2026-08-27 18:56] Bug #3: 位宽 (0,0) 静默兜底为 (1,0) 加 warning
                # 之前 line 407 静默 fallback if width == (0,0) -> (1,0),
                # 违反 AGENTS.md §2. 现在: 兜底仍保留 (兼容), 但 logger.warning + extra 记实际 width.
                if width == (0, 0):
                    logger.warning(
                        "[connection_extractor] port '%s' width (0,0) for %s; "
                        "falling back to (1,0) (likely parameterized port or missing width)",
                        port_name, inst_module_name,
                    )
                    width_extra = {"width": (0, 0), "fallback": (1, 0)}
                    final_width = (1, 0)
                else:
                    width_extra = {"width": width}
                    final_width = width
                # 合并 port_extra + width_extra 到 TraceNode.extra
                merged_extra = {**port_extra, **width_extra}

                result.nodes.append(
                    TraceNode(
                        id=inst_port_id,
                        name=port_name,
                        module=inst_path,
                        kind=kind,
                        width=final_width,
                        is_port=True,
                        extra=merged_extra,
                    )
                )

                direction_clean = direction.strip()
                parent_path = inst_path.rsplit(".", 1)[0] if "." in inst_path else "top"

                # [iter_129] interface 端口跳过普通方向建模 (节点已建, link 已收集)
                if _iface_info is not None:
                    continue

                if direction_clean == "input":
                    # [iter_109] generate 内实例: 信号作用域取模块路径 (去掉 generate 段)
                    _sig_parent = _sig_scope if _sig_scope else parent_path
                    parent_sig = f"{_sig_parent}.{signal_name}"
                    # [FIX 2026-08-13] 跳过 SELFLOOP (SELFLOOP 边不画)。
                    # 当 parent_sig 路径与 inst_path 路径冲突时 (e.g. case26 中
                    # level2_scale u_scale (.din(data_in)) — parent_sig = "golden_hier_top.u_scale.din"
                    # 而 inst_path = "golden_hier_top.u_scale" + 拼 ".din" 之后两个 ID 完全一样)
                    # 会出现 self-loop: src == dst.
                    # 决策: D2 (只给 CROSS_TOP 画红线 + SELFLOOP 删)
                    if parent_sig != inst_port_id:
                        result.edges.append(
                            TraceEdge(
                                src=parent_sig,
                                dst=inst_port_id,
                                kind=EdgeKind.CONNECTION,
                                assign_type="connection",
                            )
                        )
                    # [FIX 2026-07-08] 用 inst_path (完整 hierarchy) 替代 inst_module_name (短名)
                    # 之前: bitreverse.i_clk (flatten, 多 instance 合并, 冲突)
                    # 现在: openofdm_tx.dot11_tx.ifft64.revstage.i_clk (hierarchy 完整)
                    # 这样多 instance 区分, graph 不再 merge.
                    child_signal_id = f"{inst_path}.{port_name}"
                    # [FIX 2026-08-13] 同样跳过 SELFLOOP (inst_port_id == child_signal_id)
                    if child_signal_id != inst_port_id:
                        result.edges.append(
                            TraceEdge(
                                src=inst_port_id, dst=child_signal_id, kind=EdgeKind.CONNECTION, assign_type="internal"
                            )
                        )
                    # 同步构建 port_to_internal 映射 (full path)
                    result.port_to_internal[inst_port_id] = child_signal_id
                    # [FIX 2026-07-08] 同时保留 port_to_module_type 映射 (semantic short name)
                    # 让 trace 跨 module boundary 仍能找 leaf module 内部 signal
                    result.port_to_module_type[inst_port_id] = f"{inst_module_name}.{port_name}"
                elif direction_clean == "output":
                    # 输出端口: 子模块输出端口驱动实例端口
                    # 连接关系: child.data (child output) -> top.u_driver.data (instance port) -> top.data (parent wire)
                    # 边1: child output -> instance port (DRIVER)
                    # 边2: instance port -> parent wire (CONNECTION)
                    # [FIX 2026-07-08] 同上, child_signal_id 用 inst_path
                    child_signal_id = f"{inst_path}.{port_name}"
                    # [iter_109] generate 内实例: 信号作用域取模块路径 (去掉 generate 段)
                    _sig_parent2 = _sig_scope if _sig_scope else parent_path
                    parent_signal = f"{_sig_parent2}.{signal_name}"
                    # 边1: child output -> instance port (DRIVER)
                    # [FIX 2026-07-08] child_signal_id 用 inst_path — 自环作为"模块内部
                    # 驱动实例输出"的标记 (test_cross_module_tracking 依赖), 保持原行为.
                    result.edges.append(
                        TraceEdge(src=child_signal_id, dst=inst_port_id, kind=EdgeKind.DRIVER, assign_type="internal")
                    )
                    # 边2: instance port -> parent wire (CONNECTION)
                    # [FIX 2026-08-13] 跳过 SELFLOOP (同样防御 case26 中 parent_signal == inst_port_id)
                    if parent_signal != inst_port_id:
                        result.edges.append(
                            TraceEdge(
                                src=inst_port_id, dst=parent_signal, kind=EdgeKind.CONNECTION, assign_type="connection"
                            )
                        )
                    # 同步构建 port_to_internal (full path) + port_to_module_type (short)
                    result.port_to_internal[inst_port_id] = child_signal_id
                    result.port_to_module_type[inst_port_id] = f"{inst_module_name}.{port_name}"
                elif "inout" in direction_clean:
                    # [iter_129 候选1] inout 双向端口: 父信号与实例端口是**同一根线**
                    # (物理连接, 无方向归属 — 谁驱动取决于上下文: 外部拉 or 实例
                    # 内部三态驱动)。此前完全无 inout 分支 → 无任何边 → 跨模块
                    # fanin 空答 (top.sda ← u_io.sda 断)。
                    # 建模: 建 output 式 CONNECTION inst_port → parent_signal,
                    # fanin(父线) 沿它穿透到实例端口, 再追实例内部驱动链
                    # (三态 assign 的 DRIVER/BRANCH 边)。不建 input 式
                    # (parent → inst_port), 避免双向边让 fanin 把"外部线"当
                    # 实例端口驱动源 (i2c 开漏多驱动归属 = 更深语义, 待专项)。
                    _inout_parent = f"{_sig_scope if _sig_scope else parent_path}.{signal_name}"
                    if _inout_parent != inst_port_id:
                        result.edges.append(
                            TraceEdge(
                                src=inst_port_id,
                                dst=_inout_parent,
                                kind=EdgeKind.CONNECTION,
                                assign_type="connection",
                            )
                        )
                    # port_to_internal 同 output 语义: 实例端口 → 内部 (self 同路径)
                    result.port_to_internal[inst_port_id] = f"{inst_path}.{port_name}"
                    result.port_to_module_type[inst_port_id] = f"{inst_module_name}.{port_name}"

        # [FIX] 后处理:修复实例端口的位宽
        # 如果实例端口位宽为默认值(1,0),尝试从连接推断实际位宽
        for edge in result.edges:
            if edge.kind != EdgeKind.CONNECTION:
                continue

            # 找 src 是外部信号,dst 是实例端口的情况
            src_node = None
            dst_node = None
            for node in result.nodes:
                if node.id == edge.src:
                    src_node = node
                if node.id == edge.dst:
                    dst_node = node

            if src_node and dst_node:
                # dst 是实例端口吗?
                # 实例端口格式: path.inst.port
                parts = dst_node.id.split(".")
                if len(parts) >= 3 and dst_node.kind.name.startswith("PORT_"):
                    # 如果 dst 的位宽是默认值(1,0)且 src 有有效位宽,使用 src 的位宽
                    if dst_node.width == (1, 0) and src_node.width != (0, 0):
                        # 找到 dst_node 并更新
                        for i, n in enumerate(result.nodes):
                            if n.id == dst_node.id:
                                # 创建新的 TraceNode with correct width
                                result.nodes[i] = TraceNode(
                                    id=n.id,
                                    name=n.name,
                                    module=n.module,
                                    kind=n.kind,
                                    width=src_node.width,
                                    is_port=n.is_port,
                                )
                                break

        # [FIX Issue 20] 将警告信息添加到 result
        if hasattr(self, "_warnings") and self._warnings:
            result.warnings = self._warnings

        return result



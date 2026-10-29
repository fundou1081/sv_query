# ruff: noqa: E402
# ==============================================================================
# unified_tracer.py - Query Layer
# 使用 Semantic AST (Compilation + getRoot())
# ==============================================================================

import logging
import os
import re
from dataclasses import dataclass


def reclaim_memory_for_pyslang() -> None:
    """[DEPRECATED 2026-07-09] Was: Force inactive page reclamation before pyslang.

    [User 2026-07-09 反馈] 不能使用 swap 来规避内存 oom 问题.
    The 4GB bytearray trick pushes inactive pages to SWAP — that's a hack
    that hides pyslang's silent OOM bugs. Real fixes are smaller filelists
    or explicit OOM errors.

    This function is kept as a no-op for backward compatibility. New code
    should not call it. See test_no_swap_reclaim.py for the discipline test.
    """
    # No-op: do not push pages to SWAP. Use proper memory management instead.
    return


def reclaim_memory_if_needed() -> None:
    """[DEPRECATED 2026-07-09] Was: Conditional reclaim based on SWAP usage.

    [User 2026-07-09 反馈] 不能使用 swap 来规避内存 oom 问题.
    This function no longer auto-reclaims. It only logs a warning if SWAP
    usage is high. The user must close other apps or analyze in smaller chunks.
    """
    try:
        import subprocess
        out = subprocess.run(['sysctl', '-n', 'vm.swapusage'],
                            capture_output=True, text=True, timeout=2).stdout
        import re
        m = re.search(r'used\s*=\s*([\d.]+)M', out)
        if m:
            used_mb = float(m.group(1))
            if used_mb > 2048:
                # Just log — do not reclaim. User must manage memory explicitly.
                import sys
                print(
                    f"[sv_query] ⚠️  SWAP 使用量 {used_mb:.0f}MB — pyslang elaboration may "
                    f"silently fail. 建议: (1) 关闭其他应用释放内存. "
                    f"(2) 用更小 filelist 按模块逐个分析.",
                    file=sys.stderr,
                )
    except Exception as e:
        logger.debug("%s: 忽略 Exception: %s", __name__, e)


# [C-Flaky-3b 2026-06-27] 向后兼容旧名
_reclaim_memory_for_pyslang = reclaim_memory_for_pyslang

from .core.bit_select_handler import BitSelectHandler
from .core.class_graph_builder import ClassGraphBuilder
from .core.compiler import SVCompiler
from .core.graph import SignalGraph
from .core.graph_builder import GraphBuilder
from .core.module_instance_graph import ModuleInstanceGraph, PathResolver
from .core.query import (
    ClockDomainTrace,
    ClockDomainTracer,
    LoadChain,
    LoadTracer,
    ModuleConnections,
    ModuleTracer,
    SignalChain,
    SignalTracer,
)
from .core.query.signal import DriverChain
from .core.semantic_adapter import SemanticAdapter


# ==============================================================================
# 状态机分析器
# ==============================================================================
from trace.core.fsm_analyzer import (  # noqa: E402
    StateMachineAnalyzer, StateMachineInfo, StateTransition,
)


# ==============================================================================
# 日志级别配置
# ==============================================================================
# 支持的日志级别: DEBUG, INFO, WARNING, ERROR
# 默认使用环境变量 SV_QUERY_LOG_LEVEL，默认为 WARNING
_log_level_from_env = os.environ.get("SV_QUERY_LOG_LEVEL", "WARNING").upper()
_log_level_map = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}
_default_log_level = _log_level_map.get(_log_level_from_env, logging.WARNING)

# 配置根 logger
_root_logger = logging.getLogger("trace")
_root_logger.setLevel(_default_log_level)

# 配置 __main__ logger (用于 build_graph 等操作)
_main_logger = logging.getLogger("trace.core")
_main_logger.setLevel(_default_log_level)


# ==============================================================================
# 数据类
# ==============================================================================
@dataclass
class InstanceInfo:
    """模块实例信息 - 封装实例提取结果

    Attributes:
        name: 实例名称 (不含父路径), 如 "u_dut"
        module_type: 模块类型, 如 "dut"
        full_path: 完整路径, 如 "top.u_dut"
        parent: 父实例路径, 如 "top" 或 None (顶层)
    """

    name: str
    module_type: str
    full_path: str
    parent: str | None = None


# ==============================================================================
# UnifiedTracer
# ==============================================================================
class UnifiedTracer:
    """统一追踪入口"""

    def __init__(
        self,
        sources: dict[str, str] = None,
        files: list[str] = None,
        filelist: str = None,
        log_level: str = None,
        include_dirs: list[str] = None,
        preprocess_macros: bool = True,
        top_modules: list[str] = None,
    ):
        """初始化 UnifiedTracer

        Args:
            sources: 源文件字典 {"filename.sv": "source code"}
            files: SV 源文件路径列表
            filelist: SV 文件列表 (.fl/.f/.filelist) 路径
            log_level: 日志级别 (DEBUG/INFO/WARNING/ERROR)
                      默认为环境变量 SV_QUERY_LOG_LEVEL 的值
            include_dirs: include 搜索路径列表
            preprocess_macros: True (默认) 时跑 sv_preprocessor.preprocess_macros
                              跨文件展开 `MACRO 引用. False 则跳过 (信任 pyslang 内置).
            top_modules: [iter_145] 指定 top module 列表 → SVCompiler.top_modules
                    (只 elaborate 这些 top, free-floating 忽略 — 库 filelist +
                    显式 top 场景如 axi_xbar benchmark / CVA6)
        """
        if sources is None:
            sources = {}
        self._sources = sources
        self._log_level = log_level or os.environ.get("SV_QUERY_LOG_LEVEL", "WARNING")
        self._compiler: SVCompiler | None = None
        self._files = files or []
        self._filelist = filelist
        self._adapter = None
        self._graph: SignalGraph | None = None
        self._covergroup_cgs = None  # [G3 iter_165] 惰性 covergroup 定义
        self._signal_tracer: SignalTracer | None = None
        self._module_tracer: ModuleTracer | None = None
        self._clock_tracer: ClockDomainTracer | None = None
        self._load_tracer: LoadTracer | None = None
        self._include_dirs = include_dirs or []
        self._preprocess_macros = preprocess_macros  # [Req-20 2026-06-12] 默认跨文件宏展开
        self._preprocessed = False  # 标记是否已 preprocess
        self._top_modules = list(top_modules) if top_modules else None  # [iter_145]

        # 日志级别控制
        if log_level is not None:
            self.set_log_level(log_level)

    @staticmethod
    def _bit_bridge_mode() -> str:
        """[iter_302 / PLAN P13.1] 当前生效的位桥模式（非法值按 one，与 GraphBuilder 一致）。"""
        import os as _os

        mode = (_os.environ.get("SVQ_BIT_BRIDGE") or "one").strip().lower()
        return mode if mode in ("one", "full") else "one"

    def _graph_cache_key(self, target_module: str | None) -> str | None:
        """[iter_270] 图缓存 key: 内容 hash + **图模式**。

        旧 key 只有 sources hash → 模块级/实例级共用同一个 key, 先建哪个就命中哪个
        (实测: 先模块级再请求实例级, 直接返回旧图, 静默错误)。现在把
        target_module 编进 key (v2: 图模式只有实例级, 用固定版本段区分旧缓存)。

        filelist 模式: 用 filelist + 所有引用文件的内容 hash (iter_270 新增),
        以前 `_sources` 为空直接跳过缓存 → 真实工程永远不命中。
        """
        from trace.core.cache import get_cache

        cache = get_cache()
        try:
            if self._sources:
                base = cache.compute_sources_hash(self._sources)
            elif self._filelist:
                base = cache.compute_filelist_hash(self._filelist, self._include_dirs)
            else:
                return None
        except (OSError, FileNotFoundError) as e:
            _main_logger.debug("缓存 key 计算失败, 跳过缓存: %s", e)
            return None
        # [iter_302 / PLAN P13.1] 位桥模式影响图内容；不编进 key 会串模式（静默错误）
        # [iter_313] 图缓存 schema/语义版本：节点 metadata（dynamic/function_call）
        # 随版本变化，旧图缺标记会静默复用 → v3 显式失效一次。
        return (f"{base}-v7-t{target_module or 'all'}"
                f"-bb{self._bit_bridge_mode()}")

    def _graph_project_key(self) -> str | None:
        """[iter_287 / PLAN P3.2] 工程身份（只看路径）—— 供缓存按工程过期。"""
        from trace.core.cache import get_cache

        try:
            return get_cache().compute_project_key(
                sources=self._sources or None,
                filelist=self._filelist,
                include_dirs=self._include_dirs,
            )
        except (OSError, FileNotFoundError) as e:
            _main_logger.debug("工程 key 计算失败, 缓存不分组: %s", e)
            return None

    def set_log_level(self, level: str) -> None:
        """动态设置日志级别

        Args:
            level: DEBUG, INFO, WARNING, ERROR
        """
        level = level.upper()
        log_level_val = _log_level_map.get(level, logging.WARNING)
        _root_logger.setLevel(log_level_val)
        _main_logger.setLevel(log_level_val)

    def get_log_level(self) -> str:
        """获取当前日志级别名称"""
        return logging.getLevelName(_root_logger.level)

    def _ensure_preprocessed(self):
        """[Req-20 2026-06-12] 跨文件宏展开 (默认开启)

        在第一次 _get_compiler() 之前调用, 把 `MACRO 引用在源文件里替换成字面值
        这样 pyslang 不再报 TooFewArguments (因为 `MACRO 已被展开成具体数字)

        解决 NaplesPU 12 个 TooFewArguments:
          - coherence:49 $clog2(`DCACHE_WAY)  →  $clog2(4)
          - coherence:103 $clog2(`L2_CACHE_WAY)  →  $clog2(8)
          - npu_defines:100 typedef enum 展开成 64
        """
        if self._preprocessed or not self._preprocess_macros or not self._sources:
            return
        from .core.sv_preprocessor import preprocess_all
        _main_logger.info(
            f"[preprocess] 跨文件宏展开 + auto-inject imports: {len(self._sources)} files"
        )
        self._sources = preprocess_all(self._sources)
        self._preprocessed = True

    def _get_compiler(self) -> SVCompiler:
        """获取 SVCompiler (Semantic AST 编译入口)"""
        if self._compiler is None:
            self._ensure_preprocessed()  # [Req-20 2026-06-12] 宏展开在 compiler 前
            self._compiler = SVCompiler(self._sources, log_level=self._log_level,
                                        top_modules=self._top_modules)  # [iter_145]
            for d in self._include_dirs:
                self._compiler.add_include_dir(d)
            if self._files:
                self._compiler.add_files(self._files)
            if self._filelist:
                self._compiler.add_filelist(self._filelist)
        return self._compiler

    def _get_adapter(self):
        """获取 SemanticAdapter wrapping Semantic AST root (RootSymbol)"""
        if self._adapter is None:
            self._adapter = SemanticAdapter(self._get_compiler().get_root())
        return self._adapter

    @property
    def sources(self) -> dict[str, str]:
        """获取源文件字典"""
        return self._sources.copy()

    @property
    def compilation(self) -> object:
        """获取 Compilation 对象"""
        return self._get_compiler().get_compilation()

    def build_graph(self, force: bool = False, use_cache: bool = False,
                    target_module: str | None = None,
                    auto_target_single_top: bool = False) -> SignalGraph:
        """构建信号流图

        Args:
            force: 强制重新构建（忽略缓存）
            use_cache: 使用缓存加速（基于内容 hash）
            target_module: [Phase 3 2026-07-11] User-specified target. If set,
                           SignalGraph nodes use this as root namespace (instead
                           of auto-detected first top instance). This ensures
                           pipeline/timing/dataflow show signals in user namespace.
        """
        # [C-Flaky-3b 2026-06-27] reclaim moved to CLI main + conftest (process start).
        # build_graph() 不再调用, 避免 pytest test 内部多次调用累积 OOM.
        if self._graph is None or force:
            # 尝试从缓存加载
            cache_key = self._graph_cache_key(target_module) if use_cache else None
            project_key = self._graph_project_key() if use_cache else None
            if use_cache and cache_key:
                from trace.core.cache import get_cache

                cache = get_cache()
                cached = cache.get_by_key(cache_key, force=force, project_key=project_key)
                # [iter_270] ASTCache 把 payload 包在 "data" 里 (put_by_key 的契约,
                # 测试锁定 get_by_key(...)["data"][...])。旧代码直接查 "graph_data"
                # → **永远不命中**, 图缓存自诞生起就是死代码 (静默 miss, 无 warning)。
                payload = (cached or {}).get("data") or {}
                if payload.get("graph_data"):
                    _main_logger.info(f"Loading graph from cache (key={cache_key[:8]}...)")
                    self._graph = SignalGraph.from_dict(payload["graph_data"])
                    self._init_tracers()
                    return self._graph

            # [ARCHITECTURE_TODOLIST #5] 显式 DAG 管线 —— step 实现见下方
            # `_step_*` 方法 (P3.1 从 153 行内联闭包拆出)。
            from .core.pipeline import Pipeline, PipelineStep

            pipeline = Pipeline([
                PipelineStep("compile", self._step_compile, outputs=("root",)),
                PipelineStep("adapter", self._step_adapter, inputs=("root",), outputs=("adapter",)),
                PipelineStep("graph", self._step_graph, inputs=("adapter",), outputs=("graph",)),
                PipelineStep("class", self._step_class, inputs=("adapter", "graph")),
                PipelineStep("class_member", self._step_class_member, inputs=("adapter", "graph")),
                PipelineStep("bit_select", self._step_bit_select, inputs=("adapter", "graph")),
                PipelineStep("module_graph", self._step_module_graph,
                             inputs=("adapter", "graph"), outputs=("module_graph",)),
                PipelineStep("path_resolver", self._step_path_resolver,
                             inputs=("graph", "module_graph"), outputs=("path_resolver",)),
                PipelineStep("tracers", self._step_tracers, inputs=("graph", "module_graph")),
                PipelineStep("cond_ops", self._step_cond_ops, inputs=("graph",)),
                PipelineStep("backfill", self._step_backfill, inputs=("adapter", "graph")),
            ])
            pipeline.run({
                "compiler": self._get_compiler(),
                "target": target_module,
                "auto_target_single_top": auto_target_single_top,
            })

            # 保存到缓存
            if use_cache and cache_key:
                from trace.core.cache import get_cache

                cache = get_cache()
                cache_data = {
                    "graph_data": self._graph.to_dict(),
                }
                cache.put_by_key(cache_key, cache_data, project_key=project_key)
        return self._graph

    # ------------------------------------------------------------------
    # build_graph 的 DAG step 实现（P3.1 从内联闭包拆出）
    # ------------------------------------------------------------------
    def _step_compile(self, ctx):
        """编译并解析顶层；单 top 且未指定 target 时可自动取该 top。"""
        root = self._get_compiler().get_root()
        if (ctx.get("auto_target_single_top") and ctx.get("target") is None
                and root is not None):
            try:
                tops = list(root.topInstances)
                if len(tops) == 1:
                    ctx["target"] = str(tops[0].name)
            except Exception as e:
                _main_logger.warning("自动 target 检测失败: %s", e)
        return root

    def _step_adapter(self, ctx):
        from .core.semantic_adapter import SemanticAdapter

        compiler = ctx["compiler"]
        adapter = SemanticAdapter(
            ctx["root"], compiler,
            target_module=ctx.get("target"),
        )
        self._adapter = adapter
        return adapter

    def _step_graph(self, ctx):
        adapter = ctx["adapter"]
        builder = GraphBuilder(adapter,
                               target_module=ctx.get("target"))
        graph = builder.build()
        # [V2.A.2 cycle 17c] coverage_generator 需要 adapter 上的 AST 访问
        graph._adapter = adapter
        self._graph = graph
        return graph

    def _step_class(self, ctx):
        # [iter_154 C4-B / D5] class 类型级节点在 filter 之后加入（显式保留）
        ClassGraphBuilder(ctx["adapter"]).build(ctx["graph"])
        return None

    def _step_class_member(self, ctx):
        self._resolve_class_member_access(ctx["adapter"], ctx["graph"])
        return None

    def _step_bit_select(self, ctx):
        BitSelectHandler(ctx["adapter"], ctx["graph"]).process()
        return None

    def _step_module_graph(self, ctx):
        module_graph = ModuleInstanceGraph(ctx["adapter"])
        module_graph.build(ctx["adapter"])
        self._module_graph = module_graph
        return module_graph

    def _step_path_resolver(self, ctx):
        path_resolver = PathResolver(ctx["graph"], ctx["module_graph"])
        self._path_resolver = path_resolver
        return path_resolver

    def _step_tracers(self, ctx):
        self._init_tracers()
        return None

    def _step_cond_ops(self, ctx):
        self._emit_conditional_op_nodes()
        return None

    def _step_backfill(self, ctx):
        self._backfill_source_locations(ctx["adapter"])
        return None

    def load_graph(self, graph: SignalGraph) -> None:
        self._graph = graph
        self._init_tracers()

    def get_graph(self) -> SignalGraph | None:
        return self._graph

    def get_path_resolver(self):
        """[iter_237] 公开访问 PathResolver (跨模块路径查询)。

        返回 None 表示尚未构建 (需先 build_graph)。
        """
        return getattr(self, "_path_resolver", None)

    def get_module_graph(self):
        """[iter_236 1a] 公开访问 ModuleInstanceGraph (实例层级 + 端口映射)。

        CLI 的 instances/instance/connections/hierarchy 需要它; 之前只有私有
        `self._module_graph`, 让 CLI 直接摸私有属性不是契约。返回 None 表示尚未构建。
        """
        return getattr(self, "_module_graph", None)

    def get_elaboration_errors(self) -> list[dict]:
        """[FIX 2026-06-11 Issue 17] 公开 API: 返回 elaboration 错误列表

        需先调用 build_graph() (即使内部报错也安全, 内部已 try/except).

        Returns:
            list of dict: [{"file", "line", "column", "code", "message"}, ...]
            空 list 表示没有 elaboration 错误.
        """
        if self._compiler is None:
            # 触发编译
            try:
                self._get_compiler()
            except Exception as e:
                logger.debug("%s: 忽略 Exception: %s", __name__, e)
        if self._compiler is None:
            return []
        return self._compiler.get_elaboration_errors()

    def _resolve_class_member_access(self, adapter, graph):
        """为 class 实例成员访问建 MEMBER_SELECT 边（P0~P3 四步，实现在下方）。"""
        from trace.core.graph.models import NodeKind

        class_names = self._collect_class_names(adapter)
        if not class_names:
            return

        instance_to_class = self._find_class_instances(adapter)
        self._upgrade_class_instances(graph, NodeKind, instance_to_class)
        self._link_member_access(graph, NodeKind, class_names)

    def _collect_class_names(self, adapter) -> set[str]:
        """所有 class 名（pyslang 二进制垃圾名跳过）。"""
        names: set[str] = set()
        for cls in adapter.get_classes():
            try:
                name = getattr(cls, "name", None)
                if name:
                    names.add(str(name).strip())
            except (UnicodeDecodeError, TypeError):
                continue
        return names

    def _find_class_instances(self, adapter) -> dict[str, str]:
        """模块级 class 实例 (p = new()) → {实例路径: class 名}。"""
        found: dict[str, str] = {}
        for module in adapter.get_modules():
            module_name = adapter.get_module_name(module)
            for decl in adapter.get_data_declarations(module):
                type_node = getattr(decl, "type", None)
                if type_node is None:
                    continue
                if "ClassType" not in str(getattr(type_node, "kind", "")):
                    continue
                cls_name = getattr(type_node, "name", None)
                if cls_name is None:
                    continue
                sig_name = adapter.get_signal_name(decl)
                found[f"{module_name}.{sig_name}"] = str(cls_name).strip()
        return found

    def _upgrade_class_instances(self, graph, NodeKind, instance_to_class: dict[str, str]) -> None:
        """P1: 实例节点 → CLASS_INSTANCE + IS_INSTANCE_OF；P2: 组合成员同升级。"""
        from trace.core.graph.models import EdgeKind, TraceEdge

        for inst_path, cls_name in instance_to_class.items():
            inst_node = graph.get_node(inst_path)
            if inst_node is None:
                continue
            inst_node.kind = NodeKind.CLASS_INSTANCE
            if graph.get_edge(inst_path, cls_name) is None:
                graph.add_trace_edge(TraceEdge(
                    src=inst_path, dst=cls_name, kind=EdgeKind.IS_INSTANCE_OF))

        for node_id in list(graph.nodes()):
            node = graph.get_node(node_id)
            if node is None or node.kind != NodeKind.CLASS_PROPERTY:
                continue
            for src, dst in graph.edges():
                if src != node_id:
                    continue
                edge = graph.get_edge(src, dst)
                if edge.kind == EdgeKind.IS_INSTANCE_OF:
                    node.kind = NodeKind.CLASS_INSTANCE
                    instance_to_class[node_id] = dst
                    break

    def _link_member_access(self, graph, NodeKind, class_names: set[str]) -> None:
        """P0/P3: 实例成员 (p.addr / range.min_addr) → MEMBER_SELECT 两条边。"""
        import re

        from trace.core.graph.models import EdgeKind, TraceEdge

        for node_id in list(graph.nodes()):
            match = re.match(r"^(.+)\.([^.]+)$", node_id)
            if not match:
                continue
            base_path, member_name = match.group(1), match.group(2)
            base_node = graph.get_node(base_path)
            node = graph.get_node(node_id)
            if base_node is None or node is None or node.kind != NodeKind.SIGNAL:
                continue
            # 只有 base 是 class 实例才升级（排除 struct 等）
            if base_node.kind != NodeKind.CLASS_INSTANCE:
                continue
            class_prop_id = next(
                (f"{c}.{member_name}" for c in class_names
                 if graph.get_node(f"{c}.{member_name}") is not None),
                None,
            )
            if class_prop_id is None:
                continue

            node.kind = NodeKind.CLASS_INSTANCE_PROPERTY
            for dst in (base_path, class_prop_id):
                if graph.get_edge(node_id, dst) is None:
                    graph.add_trace_edge(TraceEdge(
                        src=node_id, dst=dst, kind=EdgeKind.MEMBER_SELECT))

    # =========================================================================
    # [FIX 2026-08-21 Plan B Step 1] OP_TERNARY / OP_CASE 节点 emit
    # =========================================================================
    _OP_TERNARY = ("Ternary", "ConditionalOp", "ConditionalExpression")
    _OP_CASE = ("Case", "CaseStatement", "CaseExpression")

    def _emit_conditional_op_nodes(self) -> None:
        """从 `_expr_trees` 提取 OP_TERNARY / OP_CASE 节点（P3.1 拆分后的编排）。

        之前 ?: / case 是 ELK-only 合成节点，内部 graph 看不到；现在按表达式树
        建 OP_* 节点 + BRANCH_*/CASE_* 边，让 `graph nodes` / trace 都能看到条件分支。
        """
        if self._graph is None:
            return
        expr_trees = getattr(self._graph, "_expr_trees", {}) or {}
        for tree_key, tree in expr_trees.items():
            if not isinstance(tree, dict):
                continue
            parts = tree_key.rsplit(".", 1)
            if len(parts) != 2:
                continue
            parent_module, lhs_short = parts
            seen: set[str] = set()
            for node in self._iter_op_nodes(tree):
                op = node.get("op")
                if op in self._OP_TERNARY:
                    self._emit_ternary_op(parent_module, lhs_short, node, seen)
                elif op in self._OP_CASE:
                    self._emit_case_op(parent_module, lhs_short, node, seen)

    def _iter_op_nodes(self, node):
        """先序遍历表达式树，产出 Ternary/Case 节点。"""
        if not isinstance(node, dict):
            return
        if node.get("op") in self._OP_TERNARY or node.get("op") in self._OP_CASE:
            yield node
        for child in node.get("children", []) or []:
            yield from self._iter_op_nodes(child)

    @staticmethod
    def _signal_refs(node) -> list[str]:
        """子树里的 SignalRef label（去重保序）。"""
        out: list[str] = []

        def walk(n):
            if isinstance(n, dict):
                if n.get("op") == "SignalRef":
                    label = n.get("label", "")
                    if label and label not in out:
                        out.append(label)
                for child in n.get("children", []) or []:
                    walk(child)

        walk(node)
        return out

    def _add_op_node(self, op_id: str, label: str, module: str, kind, extra: dict) -> bool:
        """建 OP_* 节点；失败只 debug（不中断 build）。"""
        from trace.core.graph.models import TraceNode

        try:
            self._graph.add_trace_node(TraceNode(
                id=op_id, name=label, module=module, kind=kind, width=(0, 0), extra=extra))
            return True
        except Exception as e:  # [FIX 2026-08-21] 不让错误中断 build_graph
            logger.debug("%s: 忽略 Exception: %s", __name__, e)
            return False

    def _link_op_edge(self, src: str, dst: str, kind) -> None:
        from trace.core.graph.models import TraceEdge

        if src in self._graph and dst in self._graph:
            self._graph.add_trace_edge(TraceEdge(src=src, dst=dst, kind=kind))

    def _emit_ternary_op(self, parent_module, lhs_short, node, seen: set[str]) -> None:
        """OP_TERNARY + BRANCH_CONDITION/TRUE/FALSE/RESULT 边。"""
        from trace.core.graph.models import EdgeKind, NodeKind

        children = node.get("children", []) or []
        cond_sigs = self._signal_refs(children[0]) if children else []
        sel_label = ", ".join(sorted(cond_sigs)) if cond_sigs else "?"
        op_id = f"{parent_module}.{lhs_short}.ternary_{sel_label.replace(',', '_').replace(' ', '')}"
        if op_id in seen or op_id in self._graph:
            return
        seen.add(op_id)
        if not self._add_op_node(op_id, f"?: ({sel_label})", parent_module,
                                 NodeKind.OP_TERNARY, {"op": "Ternary", "sel_label": sel_label}):
            return
        for cond in cond_sigs:
            self._link_op_edge(f"{parent_module}.{cond}", op_id, EdgeKind.BRANCH_CONDITION)
        for ci, edge_kind in ((1, EdgeKind.BRANCH_TRUE), (2, EdgeKind.BRANCH_FALSE)):
            branch = children[ci] if ci < len(children) else None
            if isinstance(branch, dict) and branch.get("op") == "SignalRef":
                label = branch.get("label", "")
                if label:
                    self._link_op_edge(f"{parent_module}.{label}", op_id, edge_kind)
        self._link_op_edge(op_id, f"{parent_module}.{lhs_short}", EdgeKind.BRANCH_RESULT)

    def _emit_case_op(self, parent_module, lhs_short, node, seen: set[str]) -> None:
        """OP_CASE + CASE_SELECT/ITEM/RESULT 边。"""
        from trace.core.graph.models import EdgeKind, NodeKind

        children = node.get("children", []) or []
        cond_sigs = self._signal_refs(children[0]) if children else []
        sel_label = ", ".join(sorted(cond_sigs)) if cond_sigs else "?"
        op_id = f"{parent_module}.{lhs_short}.case_{sel_label.replace(',', '_').replace(' ', '')}"
        if op_id in seen or op_id in self._graph:
            return
        seen.add(op_id)
        if not self._add_op_node(op_id, f"case ({sel_label})", parent_module,
                                 NodeKind.OP_CASE, {"op": "Case", "sel_label": sel_label}):
            return
        for cond in cond_sigs:
            self._link_op_edge(f"{parent_module}.{cond}", op_id, EdgeKind.CASE_SELECT)
        for item in children[1:]:
            if isinstance(item, dict) and item.get("op") == "SignalRef":
                label = item.get("label", "")
                if label:
                    self._link_op_edge(f"{parent_module}.{label}", op_id, EdgeKind.CASE_ITEM)
        self._link_op_edge(op_id, f"{parent_module}.{lhs_short}", EdgeKind.CASE_RESULT)

    # =========================================================================
    # 实例提取 API (Req-1: API 简化)
    # =========================================================================
    def get_instances(self, module: str = None) -> list[InstanceInfo]:
        """获取模块实例列表

        简化实例提取 API，自动合并 Module 和 Generate 中的实例，
        并返回结构化的 InstanceInfo 对象。

        Args:
            module: 可选，限定实例必须在指定模块内 (如 "top")
                   不指定则返回所有实例

        Returns:
            List[InstanceInfo]: 实例信息列表，按 full_path 去重

        Example:
            tracer = UnifiedTracer(parser, trees)
            tracer.build_graph()

            # 获取所有实例
            all_instances = tracer.get_instances()

            # 获取 top 模块内的实例
            top_instances = tracer.get_instances(module='top')

            for inst in top_instances:
                print(f"{inst.full_path} ({inst.module_type})")
        """
        # [iter_236 1a] 修两个 pre-existing bug (该 API 此前**无任何 CLI 调用方**, 所以没人发现):
        #   ① 旧写法 `SemanticAdapter(adapter)` —— 把 SemanticAdapter 又包一层,
        #      新 adapter 的 _root 是 SemanticAdapter 而非 pyslang root
        #      → native 实例枚举访问 `self._root.topInstances` 直接 AttributeError;
        #   ② `_parse_instance_node` 期望**原始** InstanceSymbol (`hasattr(node,'kind')`),
        #      而 native/生产路径返回的是 `SemanticInstanceWrapper` → 永远解析不出东西。
        adapter = self._get_adapter()  # SemanticAdapter (已 wrap pyslang root)
        seen: set[str] = set()
        result: list[InstanceInfo] = []
        for wrapper in adapter.get_module_instances():
            info = self._instance_info_from_wrapper(wrapper)
            if info is None or info.full_path in seen:
                continue
            seen.add(info.full_path)
            # 模块过滤: 父**实例路径** == module, 或自身就是 module
            if module is None or info.parent == module or info.full_path == module:
                result.append(info)
        return result

    @staticmethod
    def _instance_info_from_wrapper(wrapper) -> InstanceInfo | None:
        """`SemanticInstanceWrapper` → `InstanceInfo` (按实测字段形状解析)。

        实测形状 (iter_236 探针): `.name` / `.parent_module`(父**模块名**) /
        `.type.value`(模块类型) / `._symbol.hierarchicalPath`(完整路径, 如 "top.u_dut")。
        full_path 取 `hierarchicalPath` (唯一可靠来源); parent 由 full_path 去掉最后一段得到
        (比 `parent_module` 更准: 后者是模块名, 数组/generate 场景会与实例路径不一致)。
        """
        sym = getattr(wrapper, "_symbol", None)
        full = getattr(sym, "hierarchicalPath", None)
        name = getattr(wrapper, "name", None) or getattr(sym, "name", None)
        if not full:
            pm = getattr(wrapper, "parent_module", None)
            full = f"{pm}.{name}" if (pm and name) else name
        if not full:
            return None
        full = str(full)
        name = str(name) if name else full.rsplit(".", 1)[-1]
        mtype = ""
        tp = getattr(wrapper, "type", None)
        if tp is not None:
            mtype = str(getattr(tp, "value", "") or "")
        parent = full.rsplit(".", 1)[0] if "." in full else None
        return InstanceInfo(name=name, module_type=mtype, full_path=full, parent=parent)

    def trace_signal(self, signal: str, module: str = None) -> SignalChain:
        self.build_graph()
        return self._signal_tracer.trace(signal, module)

    def trace_loads(self, signal: str, module: str = None, depth: int | None = None) -> LoadChain:
        """Trace signal fanout (loads).

        [iter_241] 与 `trace_fanout` 现在**同源** (LoadTracer 是薄适配层),
        因此两者的结果逐节点相同。

        Args:
            signal: 信号名; 不给 module 时按**完整 id** 解析 (例 `'top.u.d'`)
            module: 模块名。给定 = 限定查询 (不跨模块); None = 全局查询 (跨模块)
            depth: 1=只看直接后继, N=递归 N 层, None=递归到底
        """
        self.build_graph()
        return self._load_tracer.trace(signal, module, depth=depth)

    def trace_fanout(
        self,
        signal: str,
        module: str = None,
        depth: int | None = None,
        include_clock: bool = False,
        include_reset: bool = False,
        include_control: bool = False,
        include_conditional: bool = False,
    ) -> list:
        """[FIX 2026-08-21 Plan B Step 2] trace fanout 支持 include_conditional.

        当 include_conditional=True 时, trace 会穿过 OP_TERNARY/OP_CASE 节点,
        看到条件表达式 (?: / case) 的两个分支.
        """
        self.build_graph()
        return self._signal_tracer.trace_fanout(
            signal, module, depth,
            include_clock=include_clock,
            include_reset=include_reset,
            include_control=include_control,
            include_conditional=include_conditional,
        )

    def trace_fanin(self, signal: str, module: str = None, depth: int | None = None) -> list:
        self.build_graph()
        return self._signal_tracer.trace_fanin(signal, module, depth)

    def trace_detailed(self, signal: str, module: str = None) -> DriverChain:
        """[方案C] Trace signal with detailed driver information

        返回包含 condition, clock_domain 等详细信息的驱动链

        Args:
            signal: signal name
            module: module name (optional)

        Returns:
            DriverChain - 包含 DriverInfo 列表
        """
        self.build_graph()
        return self._signal_tracer.trace_detailed(signal, module)

    def trace_fanin_detailed(self, signal: str, module: str = None, depth: int | None = None) -> list:
        """[方案C] Trace signal fanin with detailed driver information

        Args:
            signal: signal name
            module: module name (optional)
            depth: 1=direct drivers only, N=recursive N levels, None=recursive all

        Returns:
            List[DriverInfo] - 驱动信息列表
        """
        self.build_graph()
        return self._signal_tracer.trace_fanin_detailed(signal, module, depth)

    # =========================================================================
    # 模块追踪 API
    # =========================================================================
    def trace_module(self, module: str) -> ModuleConnections:
        self.build_graph()
        return self._module_tracer.trace(module)

    def trace_port(self, module: str, port_name: str) -> list:
        self.build_graph()
        return self._module_tracer.trace_port(module, port_name)

    def find_connected_modules(self, module: str) -> list:
        self.build_graph()
        return self._module_tracer.find_connected_modules(module)

    # =========================================================================
    # Class 关系查询 API (iter_152 C2 — 架构决策 D3: 类型级=结构参考)
    # =========================================================================
    def trace_class_members(self, class_name: str) -> list:
        """[iter_152 C2] class 类型级成员 (结构参考, D3).

        返回 CLASS_PROPERTY / CONSTRAINT_BLOCK / 方法等**结构节点** —
        类型级定义不是数据端点 (数据端点 = 实例属性); 查询成员关系用此 API,
        查"谁驱动属性"用实例路径 (top.p.data) 走 fanin。
        """
        self.build_graph()
        g = self._graph
        out = []
        for node_id in g.nodes():
            if not node_id.startswith(f"{class_name}."):
                continue
            nd = g.get_node(node_id)
            if nd and nd.id not in [x.id for x in out]:
                out.append(nd)
        return out

    def trace_class_instances(self, class_name: str) -> list:
        """[iter_152 C2] 类型 → 实例: 所有 IS_INSTANCE_OF 该 class 的实例节点.

        反向遍历 (IS_INSTANCE_OF: 实例 → 类型), 图不变 (不建反向边)。
        """
        self.build_graph()
        g = self._graph
        from .core.graph.models import EdgeKind as _EK
        out = []
        for s, d in g.edges():
            if d != class_name:
                continue
            for e in g.get_edges(s, d):
                if e.kind == _EK.IS_INSTANCE_OF:
                    nd = g.get_node(s)
                    if nd and nd.id not in [x.id for x in out]:
                        out.append(nd)
        return out

    def list_classes(self) -> list:
        """[iter_167] 编译域 class 名列表 (查询层槽展开判定用).

        class 成员槽 id ('tb_env.p') 首段 = owner class 名 — 判定是否需要
        展开到容器实例 (CovergroupTracer._class_instances)。
        """
        self.build_graph()
        try:
            adapter = self._get_adapter()
            names = []
            for cls in adapter.get_classes():
                try:
                    n = cls.name
                except Exception:
                    continue
                if n:
                    names.append(str(n))
            return names
        except Exception as e:
            _main_logger.warning("class 名枚举失败: %s", e)
            return []

    def trace_member_instances(self, type_prop_id: str) -> list:
        """[iter_152 C2] 类型属性 (packet.data) → 已建的实例属性节点.

        packet.data → (IS_INSTANCE_OF 实例 p1/p2) → p1.data / p2.data
        (仅返回图内**已存在**的实例成员节点 — 数据端点按需创建, 未使用
        的实例成员不臆造, 见 C2 实证)。
        """
        self.build_graph()
        g = self._graph
        if "." not in type_prop_id:
            return []
        class_name, member = type_prop_id.rsplit(".", 1)
        insts = self.trace_class_instances(class_name)
        out = []
        for inst in insts:
            prop_id = f"{inst.id}.{member}"
            nd = g.get_node(prop_id)
            if nd:
                out.append(nd)
        return out

    def trace_constraints(self, prop_id: str) -> list:
        """[iter_153 C3] 属性受哪些约束 (ConstraintTracer, 架构决策 D4).

        约束 = 声明式关系 (CONSTRAINS/HAS_* 边), 独立 tracer — 不走数据
        fanin。prop_id 支持类型级 (packet.addr) 与实例 (top.p.addr,
        自动解析类型级 — 约束定义在类型作用于所有实例)。
        """
        self.build_graph()
        from .core.query.constraint import ConstraintTracer
        return ConstraintTracer(self._graph).trace(prop_id)

    # =========================================================================
    # Covergroup 联系查询 (G3 iter_165, 方案 B / D4 范式)
    #
    # covergroup = 观察域, 定义独立 (CovergroupExtractor, 惰性提取一次,
    # 复用本 tracer compiler — 不双编译); 查询桥委托: Q1 fanin /
    # Q3 约束 (数据 fanin 单一实现)。
    # =========================================================================

    def _get_covergroup_cgs(self) -> list:
        """惰性 covergroup 定义 (与主图同一编译器 root — 语义一致)."""
        if self._covergroup_cgs is None:
            from .core.covergroup_extractor import CovergroupExtractor
            try:
                self._covergroup_cgs = CovergroupExtractor(
                    sources=self._sources,
                    compiler=self._get_compiler(),  # [G3] 复用编译, 不双编
                ).extract()
            except Exception as e:
                _main_logger.warning("covergroup 定义提取失败: %s", e)
                self._covergroup_cgs = []
        return self._covergroup_cgs

    def trace_covergroup_sampling(self, cg_name: str, cp_name: str | None = None,
                                  instance: str | None = None) -> list:
        """[iter_165 G3 Q1] cg 的 cp 采样什么信号 → 谁驱动 (fanin).

        cg_name: covergroup 定义名; instance: class cg 的实例路径 (top.p,
        D3 数据端点 — 缺省单实例自动取, 多实例须显式); module cg 免。
        返回 list[query.covergroup.SamplingInfo]。
        """
        self.build_graph()
        from .core.query.covergroup import CovergroupTracer
        return CovergroupTracer(self._get_covergroup_cgs(), self).trace_sampling_chain(
            cg_name, cp_name, instance)

    def trace_coverpoints(self, signal_id: str) -> list:
        """[iter_165 G3 Q2] 信号 X 被哪些 covergroup/coverpoint 采样.

        signal_id 域: module 顶层 (top.din) / class 类型级 (packet.addr) /
        实例级 (top.p.addr)。返回 list[query.covergroup.CoverpointRef]。
        """
        self.build_graph()
        from .core.query.covergroup import CovergroupTracer
        return CovergroupTracer(self._get_covergroup_cgs(), self).trace_coverpoints(
            signal_id)

    def trace_covergroup_rand_linkage(self, cg_name: str,
                                      cp_name: str | None = None,
                                      instance: str | None = None) -> list:
        """[iter_165 G3 Q3] class cg 采样 (rand) 属性 → 受哪些约束.

        prop_id: instance 给出 → 实例 (top.p.addr, 自动解析类型级);
        否则类型级 (packet.addr)。返回 list[query.covergroup.RandLinkage]
        (constraints = query.constraint.ConstraintInfo)。
        """
        self.build_graph()
        from .core.query.covergroup import CovergroupTracer
        return CovergroupTracer(self._get_covergroup_cgs(), self).trace_rand_linkage(
            cg_name, cp_name, instance)

    # =========================================================================
    # 时钟域追踪 API
    # =========================================================================
    def trace_clock_domain(self, clock: str) -> ClockDomainTrace:
        self.build_graph()
        return self._clock_tracer.trace(clock)

    def trace_all_domains(self) -> list:
        self.build_graph()
        return self._clock_tracer.trace_all_domains()

    def find_synchronizers(self, clock: str) -> list:
        self.build_graph()
        return self._clock_tracer.find_synchronizers(clock)

    def check_cdc_violations(self) -> list:
        self.build_graph()
        return self._clock_tracer.check_cdc_violations()

    # =========================================================================
    # 分析 API
    # =========================================================================
    def find_path(self, src: str, dst: str) -> list:
        self.build_graph()
        return self._graph.find_path(src, dst)

    def detect_cycles(self) -> list:
        self.build_graph()
        return self._graph.detect_cycles()

    def stats(self) -> dict:
        if self._graph:
            return self._graph.stats()
        return {}

    def _init_tracers(self):
        # [PR3 2026-06-15] 传 mig 给 SignalTracer, 启用跨模块 port 映射 fallback.
        # mig 在 build_graph() 里已经创建 (unified_tracer.py:434).
        self._signal_tracer = SignalTracer(self._graph, mig=getattr(self, "_module_graph", None))
        self._module_tracer = ModuleTracer(self._graph)
        self._clock_tracer = ClockDomainTracer(self._graph)
        # [iter_241] LoadTracer 现在是 SignalTracer 的薄适配层, 同样需要 mig
        # (此前不给 mig → API `trace_loads` 的跨模块结果恒空)
        self._load_tracer = LoadTracer(self._graph, mig=getattr(self, "_module_graph", None))

    def _backfill_source_locations(self, semantic_adapter) -> int:
        """[V6.2.1 2026-07-20] Backfill file/line on nodes that lack it.

        Drivers and extractors in driver_extractor.py / clock_domain_extractor.py /
        load_extractor.py sometimes create TraceNode() directly without populating
        the file/line fields. We do a final pass after build_graph() that walks
        the semantic body directly (PortSymbol / NetSymbol / VariableSymbol),
        uses semantic_adapter.get_source_location() to resolve real file/line
        (which works through the symbol's .syntax + SourceManager), then maps
        (module_name, signal_name) → (file, line) for graph nodes missing loc.

        Returns: number of nodes updated
        """
        try:
            decl_index: dict[tuple[str, str], tuple[str, int]] = {}

            def _safe_name(sym) -> str:
                try:
                    n = sym.name
                    if isinstance(n, bytes):
                        try:
                            return n.decode("utf-8", errors="replace")
                        except Exception:
                            return ""
                    return str(n)
                except Exception:
                    return ""

            # Iterate every module's semantic body. PortSymbol / NetSymbol /
            # VariableSymbol all have .name and .syntax (so
            # semantic_adapter.get_source_location() returns real file/line).
            for module in semantic_adapter.get_modules():
                module_name = semantic_adapter.get_module_name(module)
                body = getattr(module, "body", None)
                if body is None:
                    continue
                for member in body:
                    sym_kind = str(getattr(member, "kind", ""))
                    if not (sym_kind.endswith("Port") or sym_kind.endswith("Net")
                            or sym_kind.endswith("Variable")):
                        continue
                    nm = _safe_name(member)
                    if not nm:
                        continue
                    f, line, _, _ = semantic_adapter.get_source_location(member)
                    if f and line > 0:
                        decl_index[(module_name, nm)] = (f, line)

            # Apply to graph nodes missing location
            updated = 0
            for nid in list(self._graph.nodes()):
                node = self._graph.get_node(nid)
                if not node or (node.file and node.line > 0):
                    continue
                mod_split = nid.split('.', 1)
                if len(mod_split) != 2:
                    continue
                mod, rest = mod_split
                # Try several sig variants: full, last segment, last w/ [n] stripped
                candidates = [rest]
                last = rest.split('.')[-1]
                candidates.append(last)
                if '[' in last:
                    candidates.append(last.split('[')[0])
                for cand in candidates:
                    key = (mod, cand)
                    if key in decl_index:
                        node.file, node.line = decl_index[key]
                        updated += 1
                        break
            return updated
        except Exception:
            return 0

    # =========================================================================
    # 状态机分析 API
    # =========================================================================
    def analyze_fsm(self, state_signal: str, module: str = None) -> StateMachineInfo:
        """分析状态机,生成状态转换图

        从控制流分析结果中提取状态机转换信息,生成 DOT/Mermaid 格式图.

        Args:
            state_signal: 状态寄存器信号名 (如 "state", "fsm_state")
            module: 所在模块 (可选, 用于限定搜索范围)

        Returns:
            StateMachineInfo - 包含状态、转换、输出格式等信息

        Example:
            >>> tracer = UnifiedTracer({'top.sv': src})
            >>> fsm = tracer.analyze_fsm('state', 'fsm3')
            >>> print(fsm.to_dot())  # DOT 格式
            >>> print(fsm.to_mermaid())  # Mermaid 格式
        """
        self.build_graph()
        analyzer = StateMachineAnalyzer(self)
        return analyzer.analyze(state_signal, module)

# covergroup_extractor.py - Covergroup 结构化提取器
#
# 使用 Semantic AST (SVCompiler) 提取 covergroup 信息。
#
# [铁律1] 必须使用编译后 Semantic AST
# [铁律3] 不可信则不输出

import logging

from .compiler import SVCompiler
from .graph.covergroup_models import (
    BinsInfo,
    CoverCrossInfo,
    CovergroupInfo,
    CoverpointInfo,
    SampledSignal,
)

logger = logging.getLogger(__name__)


class CovergroupExtractor:
    """Covergroup 结构化提取器

    使用 Semantic AST 提取 covergroup/coverpoint/bins/cross 信息。
    [铁律1] 通过 SVCompiler 获取编译后 AST，不使用 SyntaxTree.fromText。
    """

    def __init__(self, sources: dict[str, str], strict: bool = True,
                 compiler: 'SVCompiler | None' = None):
        # [FIX 2026-06-12 Req-15] strict 参数跟 caller 一致 (默认 True, CLI 可传 False)
        # [G3 iter_165] compiler 可选注入: 复用调用方已编译的 SVCompiler
        # (UnifiedTracer 查询桥 — 避免同源双编译; get_root 缓存, 不重编)
        self._sources = sources
        self._strict = strict
        self._compiler = compiler

    def extract(self) -> list[CovergroupInfo]:
        """提取所有 covergroup"""
        results = []
        try:
            compiler = self._compiler or SVCompiler(sources=self._sources,
                                                    strict=self._strict)
            root = compiler.get_root()
            self._find_covergroups(root, results)
            self._attach_instance_rules(root, results)
        except Exception as e:
            logger.warning(f"编译失败: {e}")
        return results

    # =========================================================================
    # 遍历
    # =========================================================================

    def _find_covergroups(self, node, results: list[CovergroupInfo], scope_class: str = "",
                          scope_path: str = ""):
        """递归查找 CovergroupType.

        scope_class: 当前所在的 class 定义名 (G1 iter_162 — 归属 CovergroupInfo.
        in_class; 语义树 CovergroupType 嵌在 ClassType 下, 旧遍历不记录父 class
        → in_class 恒空, coverage.py --class 过滤/randomize 显示静默失效).
        scope_path: [G3 iter_165] 当前 instance 路径 (top / top.u_sub) — module
        顶层 cg 的宿主锚点 (CovergroupInfo.host_module, Q1 采样信号 → 图 id
        需要模块前缀; 非 class 时记录)。
        """
        kind = str(getattr(node, "kind", ""))

        if "CovergroupType" in kind:
            host_module = scope_path if not scope_class else ""
            cg = self._parse_covergroup(node, scope_class, host_module)
            if cg:
                results.append(cg)
            # 继续遍历 body (可能有嵌套)

        # [G1 iter_162] class 定义 → 其成员归属该 class (嵌套 class 覆盖外层)
        new_scope = scope_class
        if "ClassType" in kind:
            cls_name = self._sym_name(node)
            if cls_name:
                new_scope = cls_name

        # [G3 iter_165] Instance → 宿主路径下钻 (嵌套实例 top.u_sub)
        new_path = scope_path
        if "Instance" in kind:
            inst_name = self._sym_name(node)
            if inst_name:
                new_path = f"{scope_path}.{inst_name}" if scope_path else inst_name

        # 遍历 Instance body 或 CompilationUnit
        if hasattr(node, "body"):
            try:
                for child in node.body:
                    self._find_covergroups(child, results, new_scope, new_path)
            except TypeError as _e:  # pyslang Token 对象不可迭代，跳过
                logger.debug("Token 遍历跳过: %s", _e)

        # 遍历 root 的子节点
        try:
            for child in node:
                self._find_covergroups(child, results, new_scope, new_path)
        except TypeError as _e:  # pyslang Token 对象不可迭代，跳过
            logger.debug("Token 遍历跳过: %s", _e)

    @staticmethod
    def _sym_name(node) -> str:
        """symbol 名安全读取 (iter_141 教训: 非 utf8 identifier str() 抛
        UnicodeDecodeError — 归属失败不崩整图)."""
        try:
            return str(getattr(node, "name", "")).strip()
        except Exception as _e:  # UnicodeDecodeError 等
            return ""

    # =========================================================================
    # [G2 iter_163] 实例化规则 (CovergroupInfo.instance_rule)
    # =========================================================================

    def _attach_instance_rules(self, root, results: list[CovergroupInfo]):
        """后处理: 给每个 cg 定 instance_rule.

        - module 顶层 cg → 'module_scope' (采样 = module 作用域信号, 实例无关)
        - class 内 cg → 'ctor_new' / 'uninstantiated': class 内 covergroup 的
          实例 = embedded covergroup 变量, 只能在新方法 (构造函数) 里赋值
          (LRM; slang 语义也证实: 成员 = 同名 ClassProperty, ctor 语句只在
          syntax 层) — ctor syntax 含 `cg = new()` → 每个类实例携带该实例。
        """
        ctor_new = self._collect_ctor_new_targets(root)
        for cg in results:
            if cg.in_class:
                names = ctor_new.get(cg.in_class, set())
                cg.instance_rule = "ctor_new" if cg.name in names else "uninstantiated"
            else:
                cg.instance_rule = "module_scope"

    def _collect_ctor_new_targets(self, root) -> dict[str, set[str]]:
        """class 名 → ctor 中 `X = new()` 的赋值目标名集合 (G2)."""
        out: dict[str, set[str]] = {}

        def walk(node, cur_class: str = ""):
            kind = str(getattr(node, "kind", ""))
            if "ClassType" in kind:
                cls = self._sym_name(node)
                if cls:
                    cur_class = cls
            if "Subroutine" in kind and cur_class and self._sym_name(node) == "new":
                syn = getattr(node, "syntax", None)
                if syn is not None:
                    targets: set[str] = set()
                    self._collect_new_assign_targets(syn, targets)
                    out.setdefault(cur_class, set()).update(targets)
            # 语义树遍历 (body 优先 + 自身迭代, 同 _find_covergroups)
            body = getattr(node, "body", None)
            if body is not None:
                try:
                    for child in body:
                        walk(child, cur_class)
                except TypeError:
                    pass
            try:
                for child in node:
                    walk(child, cur_class)
            except TypeError:
                pass

        walk(root, "")
        return out

    def _collect_new_assign_targets(self, syn, out: set[str]):
        """syntax 递归: 找 `X = new()` 赋值的 X (NewClassExpression RHS).

        条件化 (if (en) cg = new()) 的赋值在嵌套语句里 — 递归仍可达;
        分支语义 = 运行时边界 → 存在即记 'ctor_new' (models 文档标记).
        """
        cls = type(syn).__name__
        if cls == "Token":
            return
        if cls == "BinaryExpressionSyntax":
            kids = list(syn)
            if any(type(c).__name__ == "NewClassExpressionSyntax" for c in kids):
                lhs = kids[0] if kids else None
                tgt = self._last_identifier_name(lhs)
                if tgt:
                    out.add(tgt)
        try:
            for ch in syn:
                self._collect_new_assign_targets(ch, out)
        except TypeError:
            pass

    @staticmethod
    def _last_identifier_name(syn) -> str:
        """syntax 节点子树里最后一个标识符文本 ('cg' / 'this.cg' → 'cg')."""
        found = ""
        if syn is None:
            return ""
        cls = type(syn).__name__
        if cls == "IdentifierNameSyntax":
            try:
                return str(syn).strip()
            except Exception:
                return ""
        try:
            for ch in syn:
                n = CovergroupExtractor._last_identifier_name(ch)
                if n:
                    found = n
        except TypeError:
            pass
        return found

    # =========================================================================
    # Covergroup 解析
    # =========================================================================

    def _parse_covergroup(self, node, scope_class: str = "",
                          host_module: str = "") -> CovergroupInfo | None:
        """解析 CovergroupType"""
        name = str(getattr(node, "name", "")).strip()
        # class 内的 covergroup name 可能为空，从 syntax 获取
        if not name:
            syntax = getattr(node, "syntax", None)
            if syntax:
                syntax_name = getattr(syntax, "name", None)
                if syntax_name:
                    name = str(syntax_name).strip()

        # 提取采样时钟
        clock = ""
        syntax = getattr(node, "syntax", None)
        if syntax:
            # CovergroupDeclarationSyntax 有 event 属性
            event = getattr(syntax, "event", None)
            if event:
                clock = str(event).strip()
        if not clock:
            coverage_event = getattr(node, "coverageEvent", None)
            if coverage_event:
                clock = str(coverage_event).strip()

        # 获取 body
        body = getattr(node, "body", None)
        if body is None:
            return CovergroupInfo(name=name, clock=clock)

        coverpoints = []
        crosses = []

        for child in body:
            ck = str(getattr(child, "kind", ""))
            if "Token" in ck:
                continue
            if "Coverpoint" in ck and "Cross" not in ck:
                cp = self._parse_coverpoint(child, scope_class)
                if cp:
                    coverpoints.append(cp)
            elif "CoverCross" in ck:
                cross = self._parse_cover_cross(child)
                if cross:
                    crosses.append(cross)

        return CovergroupInfo(
            name=name,
            clock=clock,
            coverpoints=coverpoints,
            crosses=crosses,
            in_class=scope_class,  # [G1 iter_162] 归属所在 class (无 = "")
            host_module=host_module,  # [G3 iter_165] module cg 宿主实例路径
        )

    # =========================================================================
    # Coverpoint 解析
    # =========================================================================

    def _parse_coverpoint(self, node, scope_class: str = "") -> CoverpointInfo | None:
        """解析 CoverpointSymbol"""
        name = str(getattr(node, "name", "")).strip()

        # 提取采样信号（从 syntax 获取）
        signal = name  # 默认用 coverpoint 名作为信号名
        syntax = getattr(node, "syntax", None)
        if syntax:
            expr = getattr(syntax, "expr", None)
            if expr:
                signal = str(expr).strip()

        # [G1 iter_162] 采样信号结构化解析: signal 原文保留 (8 消费方),
        # sampled 为结构化引用 (表达式拆到每个信号, 决策点 2)
        sampled = []
        if syntax:
            expr = getattr(syntax, "expr", None)
            if expr is not None:
                seen = set()
                for path, sel, raw in self._collect_signal_refs(expr):
                    key = (path, sel)
                    if key in seen:
                        continue
                    seen.add(key)
                    sampled.append(SampledSignal(
                        name=path,
                        kind="class_prop" if scope_class else "module",
                        host=scope_class,  # class_prop → 所在 class (类型级, D3)
                        select=sel,
                        raw=raw,
                    ))

        bins_list = []
        for child in node:
            ck = str(getattr(child, "kind", ""))
            if "Token" in ck:
                continue
            if "CoverageBin" in ck or "Bins" in ck:
                b = self._parse_bins(child)
                if b:
                    bins_list.append(b)

        # [iter_062] 提取 iff 条件 (coverpoint data iff (enable))
        iff = ""
        if syntax:
            iff_syn = getattr(syntax, "iff", None)
            if iff_syn is not None:
                iff = str(iff_syn).strip()
                if iff.startswith("iff"):
                    iff = iff[3:].strip().strip("()").strip()

        return CoverpointInfo(
            name=name,
            signal=signal,
            bins=bins_list,
            iff=iff,
            sampled=sampled,
        )

    # -------------------------------------------------------------------------
    # [G1 iter_162] 采样信号引用走查 (syntax 表达式树 → (path, select, raw))
    #
    # 铁律: 非 string fallback — 走 coverpoint syntax.expr 的 AST 子树
    # (extractor 现取 signal/iff 同源)。实证形态 (2026-09-06):
    #   IdentifierNameSyntax        'din'
    #   IdentifierSelectNameSyntax  'din[3:0]'   (base Token + ElementSelectSyntax)
    #   ScopedNameSyntax            's.x'        (标识符段 + '.' Token 平铺)
    #   Concatenation/Binary/Conditional → 组合: 逐子递归, 每个名字类子节点
    #   独立成引用 (多信号观察)。
    # 边界: 函数调用 callee 跳过 (procedural 域), 实参引用保留; 中段 select
    # 链 (a[0].b) 内嵌到 path (近似, 罕见形态 — models 注释已标)。
    # -------------------------------------------------------------------------

    _NAME_LIKE = ("IdentifierNameSyntax", "IdentifierSelectNameSyntax", "ScopedNameSyntax")

    def _collect_signal_refs(self, syn) -> list[tuple[str, str, str]]:
        """表达式 → [(path, select, raw)]; 调用方负责去重."""
        out: list[tuple[str, str, str]] = []
        self._expr_walk(syn, out)
        return out

    def _expr_walk(self, syn, out: list):
        if syn is None:
            return
        cls = type(syn).__name__
        if cls == "Token":
            return
        merged = self._merge_ref(syn)
        if merged is not None:
            out.append(merged)
            return
        try:
            kids = list(syn)
        except TypeError:
            return
        # 函数/方法调用 (CallExpressionSyntax / InvocationExpressionSyntax):
        # callee = 首个子节点 (非信号, procedural 域), 实参引用保留
        if ("Call" in cls or "Invocation" in cls) and kids:
            kids = kids[1:]
        for ch in kids:
            self._expr_walk(ch, out)

    def _merge_ref(self, syn) -> tuple[str, str, str] | None:
        """名字类节点 → 单个 (path, select, raw); 非名字类 → None.

        path = 去 select 的标识符点路径; select = 末尾切片/位选原文
        (多段拼 '[...][...]'); 中段 select (a[0].b) 内嵌进 path.
        """
        cls = type(syn).__name__
        if cls == "IdentifierNameSyntax":
            t = str(syn).strip()
            return (t, "", t) if t else None
        if cls == "IdentifierSelectNameSyntax":
            base = ""
            sel = ""
            for ch in syn:
                ccls = type(ch).__name__
                if ccls == "Token" and not base:
                    base = str(ch).strip()
                elif ccls == "ElementSelectSyntax":
                    sel += str(ch).strip()
            if not base:
                return None
            return (base, sel, str(syn).strip())
        if cls == "ScopedNameSyntax":
            frags: list[tuple[str, str]] = []  # ('n', path段) / ('s', select原文)
            for ch in syn:
                ccls = type(ch).__name__
                if ccls == "Token":
                    continue
                if ccls in self._NAME_LIKE:
                    sub = self._merge_ref(ch)
                    if sub:
                        path, sel, _raw = sub
                        if path:
                            frags.append(("n", path))
                        if sel:
                            frags.append(("s", sel))
            path, tail_sel = self._fold_scoped(frags)
            raw = str(syn).strip()
            return (path, tail_sel, raw) if path else None
        return None

    @staticmethod
    def _fold_scoped(frags: list[tuple[str, str]]) -> tuple[str, str]:
        """折叠 ScopedName 片段: select 后还有 name → 内嵌 (a[0].b);
        否则收尾 (s.x[1] → path 's.x', sel '[1]')."""
        out: list[str] = []
        tail_sel = ""
        i = 0
        n = len(frags)
        while i < n:
            kind, text = frags[i]
            if kind == "s":
                tail_sel += text  # 悬空 select (前无 name) → 收尾
                i += 1
                continue
            out.append(text)
            i += 1
            while i < n and frags[i][0] == "s":
                has_more_name = any(f[0] == "n" for f in frags[i + 1:])
                if has_more_name:
                    out[-1] += frags[i][1]
                else:
                    tail_sel += frags[i][1]
                i += 1
        return ".".join(out), tail_sel

    # =========================================================================
    # Bins 解析
    # =========================================================================

    def _parse_bins(self, node) -> BinsInfo | None:
        """解析 CoverageBin"""
        name = str(getattr(node, "name", "")).strip()

        # 判断 bins 类型（从 syntax 获取 keyword）
        kind = "bins"
        syntax = getattr(node, "syntax", None)
        if syntax:
            keyword = getattr(syntax, "keyword", None)
            if keyword:
                keyword_str = str(keyword).strip()
                if "illegal" in keyword_str:
                    kind = "illegal_bins"
                elif "ignore" in keyword_str:
                    kind = "ignore_bins"

        # [iter_062] bin_type: wildcard / transition 识别
        bin_type = ""
        if syntax:
            # wildcard 是 keyword 前的独立修饰 token (keyword 本身不含),
            # 用 syntax 完整文本判断 "wildcard" 位于 bins 关键字之前
            syntax_str = str(syntax)
            keyword_str = str(getattr(syntax, "keyword", "")).strip()
            kw_pos = syntax_str.find(keyword_str)
            if kw_pos > 0 and "wildcard" in syntax_str[:kw_pos]:
                bin_type = "wildcard"

        # 提取值
        values = ""
        if syntax:
            initializer = getattr(syntax, "initializer", None)
            if initializer:
                values = str(initializer).strip()
                # [iter_062] transition bins: (0 => 1 => 2) 形态
                if "=>" in values:
                    bin_type = "transition"
            else:
                for child in syntax:
                    ck = str(getattr(child, "kind", ""))
                    if "Initializer" in ck or "Range" in ck:
                        values = str(child).strip()
                        break

        if not values:
            values = str(node).strip()

        return BinsInfo(
            name=name,
            kind=kind,
            values=values,
            bin_type=bin_type,
        )

    # =========================================================================
    # Cross 解析
    # =========================================================================

    def _parse_cover_cross(self, node) -> CoverCrossInfo | None:
        """解析 CoverCross

        [iter_122] 匿名 cross (cross cp_a, cp_b {...} 无 label 合法) 的
        semantic name 恒空 — 合成可读名 'cross_<item1>_<item2>...' (对抗发现
        name 空串). 具名 cross 若 semantic 仍空也走合成兜底.
        """
        name = str(getattr(node, "name", "")).strip()

        items = []
        targets = getattr(node, "targets", None)
        if targets:
            for t in targets:
                t_name = str(getattr(t, "name", "")).strip()
                if t_name:
                    items.append(t_name)

        # [iter_122] 匿名 cross → 合成名 (有 label 时不覆盖)
        if not name and items:
            name = "cross_" + "_".join(items)

        # [iter_062] cross 的 iff 条件 (cross addr, mode iff (reset == 0))
        iff = ""
        syntax = getattr(node, "syntax", None)
        if syntax:
            iff_syn = getattr(syntax, "iff", None)
            if iff_syn is not None:
                iff = str(iff_syn).strip()
                if iff.startswith("iff"):
                    iff = iff[3:].strip().strip("()").strip()

        return CoverCrossInfo(
            name=name,
            items=items,
            iff=iff,
        )

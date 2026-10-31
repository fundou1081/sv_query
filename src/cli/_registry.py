"""
cli/_registry.py — CLI 分层注册表 (单一真相源)

[iter_230 P0 2026-09-09] 背景: CLI 长到 21 组 / 64 叶子命令平铺在一个命名空间里,
agent (主消费者) 无法从命令名判断该用哪个, 也不知道哪些是稳定契约、哪些只是试验。

本模块只做一件事: **把"每个命令属于哪一层、什么承诺等级"变成代码里的数据**,
供三处消费:
  1. `svq capabilities --json`  — agent 的工具面真相源
  2. `tools/gen_cli_surface.py` — 生成 docs/CLI_SURFACE.md (可重生成, 不手写)
  3. `tools/check_cli_layers.py` — 机械校验分层/只读/反向依赖

设计原则 (与 AGENTS 纪律一致):
  - **目录体现承诺等级与消费者; 属性体现副作用/成本/输出形态。**
    不为每个属性建目录 (会组合爆炸), 而是用 LayerSpec + CommandSpec 声明。
  - 注册表是**声明式**的: 某个命令没被登记 → `check_cli_layers.py` 报错, 不允许"忘了分层"。
  - P0 阶段**不改命令行为**: 本表只描述现状 + 记录已定的改名计划 (planned_name)。

层级 (2026-09-09 方豆拍板):
  core  : agent 一等公民 —— 只读 + JSON + 稳定 schema
  view  : 人眼面 —— 图与叙述, 默认含于 capabilities, 后续重点开发
  exp   : 降级区 —— 无 schema 承诺, 只修 bug 不加功能 (总线域 + 验证域 + 待定算法)
  dev   : 开发者内部调试, 不进用户文档
  out   : 移出 CLI (会写文件) → 交给 tools/
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# 1. 层规范 (承诺等级 + 消费者)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LayerSpec:
    """一层的契约。改这里 = 改对外的承诺。"""
    name: str
    consumer: str            # agent / human / dev / none
    stability: str           # stable / unstable / none
    readonly: bool           # 是否禁止任何文件写入
    json_required: bool      # 是否要求所有命令支持 --json
    in_capabilities: bool    # 是否出现在 capabilities 默认输出
    schema_version: str | None = None   # 非 None = 输出 schema 有版本承诺
    note: str = ""


LAYERS: dict[str, LayerSpec] = {
    "core": LayerSpec(
        name="core", consumer="agent", stability="stable", readonly=True,
        json_required=True, in_capabilities=True, schema_version="1",
        note="agent 一等公民: 只读 + JSON + 稳定 schema",
    ),
    "view": LayerSpec(
        name="view", consumer="human", stability="stable", readonly=True,
        json_required=False, in_capabilities=True, schema_version=None,
        note="人眼面 (图/叙述); 默认含于 capabilities, 后续重点开发",
    ),
    "exp": LayerSpec(
        name="exp", consumer="none", stability="unstable", readonly=True,
        json_required=False, in_capabilities=False, schema_version=None,
        note="降级区: 规范入口 svq exp <组> <子> (老路径为别名); 无 schema 承诺, 只修 bug; --include-exp 才列出",
    ),
    "dev": LayerSpec(
        name="dev", consumer="dev", stability="none", readonly=True,
        json_required=False, in_capabilities=False, schema_version=None,
        note="开发者内部调试 (当前无命令; expression 已于 iter_252 归档)",
    ),
    "out": LayerSpec(
        name="out", consumer="none", stability="none", readonly=True,
        json_required=False, in_capabilities=False, schema_version=None,
        note="移出 CLI (会写 RTL/项目文件) → tools/; 不算产品命令",
    ),
}

# core 内部三段: 语义 (agent 主力) / 定位原语 / 状态 / 诊断
CORE_GROUPS = {
    "semantic": "语义事实: 关系查询 (drivers/loads/conditions/path) —— agent 推理链主力",
    "locate": "定位原语: 枚举与统计 (search/stats/graph) —— 低层但 agent 需要",
    "state": "状态: graph 快照与比较 (写自有状态, 不碰项目文件)",
    "diagnose": "只读诊断: diagnose <check> (imports/report/timescale/widths), 不改文件",
}


# ---------------------------------------------------------------------------
# 2. 命令规格 + 分类表 (现状 = 真相; planned_name = 已定的改名)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CommandSpec:
    key: str                 # 现状命令路径 ("trace fanin" / "stats")
    layer: str               # core / view / exp / dev / out
    group: str               # 层内分组 (core: semantic/locate/state/diagnose)
    kind: str                # fact / primitive / presentation / diagnosis / state / debug
    cost: str                # cheap / medium / expensive
    json: bool               # 是否已有 --json
    stateful: bool = False
    recommended: bool = False   # agent 默认优先使用 (capabilities --recommended)
    planned_name: str | None = None   # 已定的改名 (P1 执行, 老名保留 alias)
    note: str = ""


def _c(key, group, kind="fact", cost="medium", json=True, *, stateful=False,
       recommended=False, planned=None, note="") -> CommandSpec:
    return CommandSpec(key=key, layer="core", group=group, kind=kind, cost=cost,
                       json=json, stateful=stateful, recommended=recommended,
                       planned_name=planned, note=note)


def _v(key, kind="presentation", cost="expensive", json=False, note="") -> CommandSpec:
    return CommandSpec(key=key, layer="view", group="render", kind=kind,
                       cost=cost, json=json, note=note)


def _e(key, group, cost="medium", note="") -> CommandSpec:
    return CommandSpec(key=key, layer="exp", group=group, kind="experimental",
                       cost=cost, json=False, note=note)


def _d(key) -> CommandSpec:
    return CommandSpec(key=key, layer="dev", group="internal", kind="debug",
                       cost="cheap", json=True)


def _o(key, note="") -> CommandSpec:
    return CommandSpec(key=key, layer="out", group="mutating", kind="mutating",
                       cost="cheap", json=False, note=note)


COMMANDS: list[CommandSpec] = [
    # ---- core / semantic (agent 主力) ----
    _c("drivers", "semantic", recommended=True, cost="medium",
       note="[规范入口] 谁驱动这个信号 (上游; DRIVER 边反向遍历); 兼容别名 trace fanin"),
    _c("loads", "semantic", recommended=True, cost="medium",
       note="[规范入口] 这个信号被谁使用 (下游; DRIVER 边正向遍历); 兼容别名 trace fanout"),
    _c("trace impact", "semantic", recommended=True, cost="expensive",
       note="传递影响 + 启发式风险分 (未标定, 仅用于同一图内相对排序; 见 KNOWN_LIMITATIONS §3.4)"),
    _c("trace evidence", "semantic", recommended=True, note="源码证据 (always/if 块原文)"),
    _c("controlflow analyze", "semantic", cost="medium", recommended=True,
       note="信号的驱动条件分析; --conditions-only 只要扁平条件列表 (原 controlflow conditions)"),
    _c("controlflow list-conditioned", "semantic", cost="expensive",
       note="列出所有带条件驱动的信号 (枚举, 用于找入口)"),
    _c("dataflow analyze", "semantic", recommended=True,
       note="源→目标路径 (有向, 跨模块; 实例级 id; 与 paths --directed 结论一致)"),
    # [iter_236 1a] 实例/层级查询 (补 agent 理解架构的第一步; 复用 get_instances/MIG)
    _c("instances", "semantic", cost="cheap", recommended=True,
       note="列出实例; 给实例路径 → 详情 (类型/父/子/端口); 支持 --filelist"),
    _c("connections", "semantic", cost="medium", recommended=True,
       note="[规范入口] 连接: 实例→端口↔内部信号 / 模块→四类边+置信度 (输出带 resolved_as)"),
    _c("hierarchy", "semantic", cost="medium", recommended=True,
       note="[规范入口] 实例层级树 (机器可读版 arch show)"),
    # [iter_237] 语义查询补全 (参数 override / 端口总览 / 跨模块路径 / class)
    _c("params", "semantic", cost="cheap", recommended=True,
       note="[规范入口] 实例的**生效**参数值 (含 is_overridden: 区分 override 与默认)"),
    _c("ports", "semantic", cost="cheap", recommended=True,
       note="[规范入口] 模块端口总览 (方向/位宽/入边数/出边数)"),
    _c("paths", "semantic", cost="medium", recommended=True,
       note="[规范入口] 图上路径 (实例级 id; --all 枚举; "
            "--directed 只沿数据流方向, 与 dataflow analyze 结论一致)"),
    _c("class", "semantic", cost="medium",
       note="不给 name → 列出所有 class; 给了 → 成员(类型级)+实例(实例级); --member 查某成员实例"),
    _c("audit", "semantic", cost="medium", recommended=True,
       note="[规范入口] 设计审计 (只读): 协议识别/握手配对/反压环候选/断言覆盖/覆盖缺口/"
            "验证缺口/改动风险/约束覆盖/CDC 候选/组合链长度; 每条带 confidence"),

    # ---- core / locate (枚举与统计) ----
    _c("stats", "locate", kind="primitive", cost="cheap", recommended=True),
    _c("search", "locate", kind="primitive", cost="cheap",
       note="文本/正则搜索; [iter_231] 已补 --json"),
    _c("graph nodes", "locate", kind="primitive", cost="cheap",
       note="列图节点 (kind/module/--match 过滤; --detail 给表达式等富字段); 支持 --file / --filelist"),
    _c("graph edges", "locate", kind="primitive", cost="cheap",
       note="列出图边; 支持 --file / --filelist (iter_236 补)"),
    _c("diagnose", "diagnose", kind="diagnosis", cost="cheap", recommended=True,
       note="只读诊断: <检查项> = imports|report|timescale|widths; 不改文件 (写文件用 tools/fix_*.py)"),
    _c("capabilities", "locate", kind="primitive", cost="cheap", recommended=True,
       note="本清单自身 (agent 应先读它再决定调什么)"),

    # ---- core / state (你已定: graph 比较算 core) ----
    _c("snapshot save", "state", kind="state", cost="medium", stateful=True,
       note="[iter_239 1b] 默认写缓存目录 (~/.svq/cache/snapshots; 可用 SVQ_SNAPSHOT_DIR 覆盖)"),
    _c("snapshot list", "state", kind="state", cost="cheap", stateful=True,
       note="列出快照; 给 tag → 该快照详情 (原 snapshot show)"),
    _c("snapshot compare", "state", kind="state", cost="medium", recommended=True,
       note="比较两个快照, 或两个 SV 文件 (文件模式 = 原 diff compare; --signal 看可达性差异)"),
    _c("snapshot delete", "state", kind="state", cost="cheap", stateful=True,
       note="[iter_231] 已补 --json"),

    # ---- core / diagnose (原 fix 只读部分) ----

    # ---- view (人眼面, 默认含于 capabilities) ----
    _v("visualize graph", cost="expensive"),
    _v("visualize dataflow"),
    _v("visualize pipeline", cost="medium"),
    _v("visualize chain"),
    _v("visualize module"),
    _v("visualize teach"),
    _v("visualize datapath", note="定点计算架构图; 0 个测试文件 (只有 fixture 名引用, 覆盖缺口)"),
    _v("arch show", note="项目架构总览 (L1 模块 + L2 端口)"),
    _v("design show", cost="expensive", note="IP 级设计理解; 仅 1 个测试文件 (覆盖缺口)"),
    _v("trace overview", kind="presentation", cost="expensive",
       note="两个信号之间的综合叙述 (dataflow + controlflow + evidence)"),
    # ---- dev (内部调试) ----


    # ---- out: CLI 内已无会写文件的命令 (2026-09-09 方豆: sv_query 不改 RTL) ----
    # 写入能力现在只在 tools/: fix_timescale.py --apply (改 .sv) / fix_imports.py --write (写 filelist)
    # 若将来再加会写文件的命令 → 归入本层, 并由 R3 检查器拦截。
]

COMMANDS_BY_KEY: dict[str, CommandSpec] = {c.key: c for c in COMMANDS}

# ---------------------------------------------------------------------------
# 兼容别名 (老命令名 → 规范名)
#   [iter_231 P1] 方豆决定方案 (a): 语义 core 的规范入口是**顶层关系名**
#   (`svq drivers` / `svq loads`), 老名在 `trace` 组内保留为兼容别名。
#   别名与规范名是**同一个函数对象** (无第二份实现/签名) → 输出必然一致。
# ---------------------------------------------------------------------------
ALIASES: dict[str, str] = {
    "trace fanin": "drivers",
    "trace fanout": "loads",
    # [iter_248 T2] fix <x> 别名已删除: 诊断统一为 `diagnose <check>`, 只读
    # [iter_235 P3] exp 降级区收进 `svq exp ...` 前缀; 老路径保留为兼容别名
}


def canonical(key: str) -> str:
    """别名 → 规范名; 规范名原样返回。"""
    return ALIASES.get(key, key)


def aliases_of(canonical_key: str) -> list[str]:
    return sorted(a for a, c in ALIASES.items() if c == canonical_key)

# 计划新增 (P1+, 语义 core 缺口): instance 查询
NEW_PLANNED: list[dict] = [
    # [iter_236 1a] instances / instance / connections / hierarchy 已落地 (core/semantic)。
    # 候选 (未拍板): 参数/端口 override 查询; class 实例成员 (trace_member_instances 仍未暴露)。
]


# ---------------------------------------------------------------------------
# 3. 查询辅助 (供 capabilities / 生成器 / 检查器共用)
# ---------------------------------------------------------------------------
def spec_for(key: str) -> CommandSpec | None:
    return COMMANDS_BY_KEY.get(key)


def layer_of(key: str) -> str | None:
    s = spec_for(key)
    return s.layer if s else None


def counts() -> dict:
    """按层/组统计 (生成器与检查器共用, 避免两处各算一遍)。"""
    by_layer: dict[str, int] = {}
    by_group: dict[str, int] = {}
    for c in COMMANDS:
        by_layer[c.layer] = by_layer.get(c.layer, 0) + 1
        if c.layer == "core":
            by_group[c.group] = by_group.get(c.group, 0) + 1
    return {"total": len(COMMANDS), "by_layer": by_layer, "core_by_group": by_group}


# ---------------------------------------------------------------------------
# 位精确性契约 (agent 可发现性; 与 docs/architecture/trace_capability_review 同步)
# 只描述"静态可判定"部分, 运行期相关形态明确列为 coarse。
# ---------------------------------------------------------------------------
JSON_CONTRACT = {
    "schema_version": "1",
    "policy": (
        "v1 allows additive optional fields; removing/renaming a field, changing a "
        "field type, or adding a required field requires a schema_version bump. "
        "Nullable values use JSON null (not omission)."
    ),
    "scope": (
        "Top-level envelope + trace fanin/fanout signal/node fields. Other core "
        "commands share the top-level envelope; command-specific fields are added "
        "incrementally with the same policy."
    ),
    "top_level": {
        "ok": {"type": "boolean", "desc": "false if any per-signal error was recorded"},
        "command": {"type": "string", "desc": "command name, e.g. trace_fanin"},
        "params": {"type": "object", "desc": "echo of resolved request parameters"},
        "result": {"type": "object", "desc": "command-specific result payload"},
        "errors": {"type": "array", "desc": "per-signal errors; empty when ok=true"},
    },
    "trace_signal": {
        "signal": {"type": "string", "desc": "queried signal id (as requested)"},
        "index": {"type": "integer", "desc": "position in the batch/signals request"},
        "precision": {
            "type": "string", "enum": ["bit", "bus", "unknown"],
            "desc": "answer granularity; unknown means runtime/opaque dependency",
        },
        "coarse_fallback": {
            "type": "boolean",
            "desc": "bit query mixed with bus/constant fallback; downgrade to bus",
        },
        "dynamic_index": {
            "type": "boolean",
            "desc": "runtime index (mem[i]) affects this query -> precision=unknown",
        },
        "function_call": {
            "type": "boolean",
            "desc": "function call result/condition affects this query (not inlined) -> unknown",
        },
        "runtime_system_call": {
            "type": "boolean",
            "desc": "runtime system call ($random/$urandom/...) affects this query -> unknown",
        },
        "conditions": {
            "type": "array<string>",
            "desc": "per-path condition expressions (direct edge or multi-path OR components)",
        },
        "condition_truncated": {
            "type": "boolean",
            "desc": "condition path enumeration hit caps; conditions may be incomplete",
        },
        "truncated_by_depth": {
            "type": "boolean",
            "desc": "a node at the depth boundary still has unexpanded edges",
        },
        "cycles_detected": {
            "type": "boolean|null",
            "desc": "reachable cycle in traversal direction; null = analysis cap reached",
        },
        "count": {"type": "integer", "desc": "returned item count after filters"},
        "pre_filter_count": {"type": "integer", "desc": "item count before filters"},
        "truncated": {"type": "boolean", "desc": "max_results cap applied (independent of depth)"},
    },
    "trace_node": {
        "id": {"type": "string", "desc": "graph node id"},
        "module": {"type": "string", "desc": "instance/module path"},
        "kind": {"type": "string", "desc": "NodeKind name (SIGNAL/PORT_IN/...)"},
        "width": {"type": "integer", "desc": "bit width (0 if unknown)"},
        "width_msb": {"type": "integer|null", "desc": "declared MSB"},
        "width_lsb": {"type": "integer|null", "desc": "declared LSB"},
        "distance": {"type": "integer", "desc": "hops from query signal; 1 = direct"},
        "precision": {
            "type": "string", "enum": ["bit", "bus", "constant", "unknown"],
            "desc": "node granularity",
        },
        "is_signed": {"type": "boolean|null", "desc": "declared signedness, null if unknown"},
        "parent": {"type": "string|null", "desc": "parent bus/member node id"},
        "bit_range": {"type": "array|null", "desc": "[hi, lo] for slice/bit nodes"},
        "dynamic_index": {"type": "boolean", "desc": "runtime index affects node"},
        "function_call": {"type": "boolean", "desc": "function call result/condition node"},
        "runtime_system_call": {"type": "boolean", "desc": "runtime system call node"},
        "condition": {
            "type": "string",
            "desc": "direct-edge OR or multi-path OR for this node; empty = unconditional",
        },
        "conditions": {
            "type": "array<string>",
            "desc": "preserved per-edge/per-path conditions (not flattened)",
        },
        "condition_path": {
            "type": "array<string>",
            "desc": "first path's raw conditions (compat with P23)",
        },
        "condition_paths": {
            "type": "array<object>",
            "item": {"condition": "string", "path": "array<string>"},
            "desc": "each path: combined condition + raw condition sequence",
        },
        "condition_unconditional": {
            "type": "boolean",
            "desc": "at least one path has no condition -> condition is empty",
        },
        "condition_truncated": {
            "type": "boolean",
            "desc": "path enumeration hit caps for this node",
        },
    },
    "commands": {
        "trace fanin": {
            "result_fields": ["drivers"],
            "signal_fields": ["driver_count", "multi_driver", "conditional_drivers"],
            "node_array": "drivers",
        },
        "trace fanout": {
            "result_fields": ["loads"],
            "signal_fields": [],
            "node_array": "loads",
        },
    },
    "precision_values": ["bit", "bus", "unknown"],
    "notes": (
        "null != false: cycles_detected=null means the analysis cap was hit. "
        "condition fields are display strings, not a normalized boolean AST. "
        "unknown/coarse_fallback are intentional downgrades, not failures."
    ),
}


BIT_PRECISION = {
    "schema_version": "1",
    "modes": {
        "one": "默认: 只为'一侧已有位节点'的连接补位桥；纯总线保持总线粒度",
        "full": "SVQ_BIT_BRIDGE=full: 纯总线连接也按同索引合成位节点（图更大）",
    },
    "precise_forms": [
        "explicit bit select/assignment (y[3], y[3]=a[7])",
        "slice (y[7:4]=a, y=a[7:4], offsets, slice-to-slice)",
        "register bit / always_ff bit assignment",
        "generate per-entry bit",
        "bus<->bus connection (one: one side already has bits; full: pure bus)",
        "direct copy assign y=a (source bit nodes exist)",
        "expressions: bitwise (& | ^ ~), add/sub/mul, constant shift, slice",
        "concatenation {a,b} (signal operands and literal segments)",
        "constants (sized N'b/o/d/h, unsized, concat literal; unsigned extension)",
        "signed literal/signal extension (sign bit vs zero extend)",
        "integer/int/byte/shortint/longint/time widths",
        "packed struct/union aggregate + member layout + member bit bridge",
        "static-indexed memory element bits (mem[1][3])",
    ],
    "coarse_forms": [
        "comparison / logical / reduction (all bits may participate)",
        "variable shift / dynamic part-select / dynamic memory index",
        "function/task return values",
        "deep packed members (o.inner.a) not materialized",
        "non-packed struct",
        "source bit node absent -> falls back to bus",
    ],
    "markers": {
        "node.precision": "bit | bus | constant",
        "signal.precision": "bit | bus | unknown",
        "signal.coarse_fallback": "true when a bit query mixes bit with bus/constant results",
        "signal.dynamic_index": "true when runtime index (mem[i]) affects the query; propagated through data, conditions, clock/reset, dynamic writes -> precision=unknown",
        "signal.function_call": "true when the query passes through a function call (result or condition/clock; not inlined) -> precision=unknown",
        "signal.conditions": "edge/path conditions on the queried signal; deeper nodes get multi-path OR with per-path condition_paths",
        "signal.condition_truncated": "true when condition path enumeration hit caps (max 8 paths/depth 20/5000 expansions)",
        "signal.runtime_system_call": "true when the query passes through a runtime system call ($random/$urandom/...) -> precision=unknown",
    },
    "notes": "precision markers describe granularity, not a proof of bit-exact dependency; "
             "coarse_fallback=true means the answer should be downgraded to bus level.",
}


def to_json(*, include_exp: bool = False, recommended_only: bool = False) -> dict:
    """capabilities / 生成器共用的结构 (agent 的工具面真相源)。"""
    cmds = []
    for c in COMMANDS:
        lay = LAYERS[c.layer]
        if not lay.in_capabilities and not include_exp:
            continue
        if recommended_only and not c.recommended:
            continue
        cmds.append({
            "name": c.key,
            "planned_name": c.planned_name,
            "aliases": aliases_of(c.key),
            "layer": c.layer,
            "group": c.group,
            "kind": c.kind,
            "cost": c.cost,
            "json": c.json,
            "stateful": c.stateful,
            "readonly": lay.readonly,
            "stability": lay.stability,
            "schema_version": lay.schema_version,
            "recommended": c.recommended,
            "note": c.note,
        })
    return {
        "schema_version": "1",
        "layers": {
            n: {"consumer": l.consumer, "stability": l.stability,
                "readonly": l.readonly, "json_required": l.json_required,
                "schema_version": l.schema_version, "note": l.note}
            for n, l in LAYERS.items()
        },
        "core_groups": CORE_GROUPS,
        "counts": counts(),
        "planned_new": NEW_PLANNED,
        "bit_precision": BIT_PRECISION,
        "json_contract": JSON_CONTRACT,
        "commands": cmds,
    }


def walk_app(app) -> list[str]:
    """遍历 typer app, 返回所有叶子命令的现状路径 (如 "trace fanin")。"""
    import typer

    root = app if hasattr(app, "commands") else typer.main.get_command(app)
    out: list[str] = []

    def _walk(cmd, prefix: str) -> None:
        import click
        if isinstance(cmd, click.Group):
            for name, sub in cmd.commands.items():
                _walk(sub, f"{prefix}{name} ")
        else:
            out.append(prefix.strip())

    _walk(root, "")
    return sorted(out)

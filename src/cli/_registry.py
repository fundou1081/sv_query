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
        note="降级区: 无 schema 承诺, 只修 bug 不加功能; --include-exp 才列出",
    ),
    "dev": LayerSpec(
        name="dev", consumer="dev", stability="none", readonly=True,
        json_required=False, in_capabilities=False, schema_version=None,
        note="开发者内部调试, 不进用户文档",
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
    "diagnose": "只读诊断: 编译/依赖问题报告 (原 fix report/widths)",
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
    _c("trace fanin", "semantic", planned="drivers", recommended=True, cost="medium",
       note="谁驱动这个信号 (上游; DRIVER 边反向遍历)"),
    _c("trace fanout", "semantic", planned="loads", recommended=True, cost="medium",
       note="这个信号被谁使用 (下游; DRIVER 边正向遍历)"),
    _c("trace impact", "semantic", recommended=True, cost="expensive",
       note="传递影响 + 风险分级"),
    _c("trace evidence", "semantic", recommended=True, note="源码证据 (always/if 块原文)"),
    _c("controlflow analyze", "semantic", recommended=True, note="信号的驱动条件分析"),
    _c("controlflow conditions", "semantic", recommended=True, note="信号的全部驱动条件"),
    _c("controlflow list-conditioned", "semantic", cost="expensive",
       note="列出所有带条件驱动的信号 (枚举, 用于找入口)"),
    _c("dataflow analyze", "semantic", recommended=True, note="源→目标路径"),

    # ---- core / locate (枚举与统计) ----
    _c("stats", "locate", kind="primitive", cost="cheap", recommended=True),
    _c("search", "locate", kind="primitive", cost="cheap", json=False,
       note="[缺口] 无 --json; 文本 grep"),
    _c("graph nodes", "locate", kind="primitive", cost="cheap",
       note="[缺口] 只支持 --file 单文件, 真实项目(filelist)不可用"),
    _c("graph edges", "locate", kind="primitive", cost="cheap",
       note="[缺口] 只支持 --file 单文件"),
    _c("graph find", "locate", kind="primitive", cost="cheap",
       note="[缺口] 只支持 --file 单文件"),
    _c("graph dump", "locate", kind="primitive", cost="cheap",
       note="[缺口] 只支持 --file 单文件"),
    _c("capabilities", "locate", kind="primitive", cost="cheap", recommended=True,
       note="本清单自身 (agent 应先读它再决定调什么)"),

    # ---- core / state (你已定: graph 比较算 core) ----
    _c("snapshot save", "state", kind="state", cost="medium", json=False, stateful=True,
       note="[缺口] 无 --json; 默认写 .svq/ (应迁 $SVQ_CACHE_DIR)"),
    _c("snapshot list", "state", kind="state", cost="cheap", stateful=True),
    _c("snapshot show", "state", kind="state", cost="cheap", stateful=True),
    _c("snapshot compare", "state", kind="state", cost="medium", stateful=True,
       recommended=True, note="graph 差异 (diff compare 计划并入这里)"),
    _c("snapshot delete", "state", kind="state", cost="cheap", json=False, stateful=True),
    _c("diff compare", "state", kind="state", cost="medium", stateful=True,
       note="[计划] 并入 snapshot compare"),

    # ---- core / diagnose (原 fix 只读部分) ----
    _c("fix report", "diagnose", kind="diagnosis", cost="cheap", recommended=True,
       note="[计划] 改名 diagnose report (去 fix 暗示)"),
    _c("fix widths", "diagnose", kind="diagnosis", cost="cheap",
       note="[计划] 改名 diagnose widths"),

    # ---- view (人眼面, 默认含于 capabilities) ----
    _v("visualize graph", cost="expensive"),
    _v("visualize dataflow"),
    _v("visualize pipeline", cost="medium"),
    _v("visualize chain"),
    _v("visualize module"),
    _v("visualize teach"),
    _v("visualize datapath", note="[缺口] 0 测试"),
    _v("visualize compute", note="[缺口] 仅 1 测试文件"),
    _v("visualize timed", note="[缺口] 仅 1 测试文件"),
    _v("visualize gap", cost="medium"),
    _v("arch show", note="[计划] 迁 VizData 统一渲染"),
    _v("design show", cost="expensive", note="[缺口] 仅 3 测试文件"),
    _v("trace overview", kind="presentation", cost="expensive",
       note="[计划] 归入 view/overview"),

    # ---- exp / bus (总线结构域: 方豆定 —— 也降级) ----
    _e("protocol detect", "bus"), _e("protocol show", "bus"),
    _e("protocol list", "bus", cost="cheap"), _e("protocol semantics", "bus"),
    _e("handshake scan", "bus"), _e("handshake analyze", "bus"),
    _e("handshake pair", "bus"),
    _e("backpressure analyze", "bus"), _e("backpressure deadlock", "bus"),

    # ---- exp / verif (验证域: 统一降级) ----
    _e("sva extract", "verif"), _e("sva coverage", "verif"), _e("sva timing", "verif"),
    _e("coverage suggest", "verif"), _e("coverage gap", "verif"),
    _e("coverage generate", "verif"), _e("coverage analyze", "verif"),
    _e("verify gap", "verif"), _e("risk analyze", "verif"),
    _e("randomize list", "verif"), _e("randomize extract", "verif"),
    _e("randomize trace", "verif"), _e("randomize reachability", "verif"),

    # ---- exp / struct (cdc/timing: 算法待定, 附晋升门槛) ----
    _e("cdc analyze", "struct", note="算法可靠性待验证; 见 docs/EXP_NAMESPACE.md 晋升门槛"),
    _e("timing analyze", "struct", note="算法可靠性待验证; 见 docs/EXP_NAMESPACE.md 晋升门槛"),

    # ---- dev (内部调试) ----
    _d("expression build"), _d("expression func"), _d("expression cond"),

    # ---- out (会写文件 → tools/) ----
    _o("fix timescale", note="--apply 会改 RTL (.sv) + .bak 备份 → tools/fix_timescale.py"),
    _o("fix imports", note="--write 会写 filelist → tools/"),
]

COMMANDS_BY_KEY: dict[str, CommandSpec] = {c.key: c for c in COMMANDS}

# 计划新增 (P1+, 语义 core 缺口): instance 查询
NEW_PLANNED: list[dict] = [
    {"name": "instances", "layer": "core", "group": "semantic",
     "reuse": "UnifiedTracer.get_instances()",
     "output": "[{full_path,name,module_type,parent}]",
     "note": "实例列表/过滤 —— 目前 CLI 零暴露"},
    {"name": "instance", "layer": "core", "group": "semantic",
     "reuse": "get_instances() + 端口/参数",
     "output": "{full_path,module_type,ports[],param_overrides[],src_file,src_line}"},
    {"name": "connections", "layer": "core", "group": "semantic",
     "reuse": "trace_module / trace_port",
     "output": "{inputs[],outputs[],internals[],cross_module[],confidence,caveats}"},
    {"name": "hierarchy", "layer": "core", "group": "semantic",
     "reuse": "module_instance_graph (MIG)",
     "output": "{path,module_type,children[]}  ← arch show 的机器面"},
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

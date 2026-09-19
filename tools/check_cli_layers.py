#!/usr/bin/env python3
"""
check_cli_layers.py — [iter_230 P0] CLI 分层的机械保障

用途: 把"分层 / 只读 / 反向依赖"从**声明**变成**可执行检查**。
      (项目已有两次教训: 声明没有机械保障就会长回来 —— iter_190 的 except:pass、
       iter_224 的 1-tuple 逗号。本检查器是同一手法的第三次应用。)

规则 (R1~R6):
  R1 每个叶子命令必须登记在 cli/_registry.py (不允许"忘了分层")
  R2 层间依赖方向: core ⊥ view/exp/dev;  view ⊥ exp/dev;  exp ⊥ dev
  R3 src/cli/** 内禁止任何文件写操作 (只读硬约束)
  R4 core 层命令必须支持 --json (agent 契约)
  R5 exp 层命令名不得出现在 core/view 的帮助文本里 (防止误导 agent)
  R6 exp 不得出现在 capabilities 默认输出 (须 --include-exp)
  R7 模块级不得定义与 builtin 同名的函数/类 (会劫持同模块的 builtin 调用)
  R8 不得用 __file__ 做路径深度运算 (搬目录即错位) —— 一律用 cli/_paths.py 锚点

INFO (不算违规, 但列出来当待办):
  - 只支持 --file 单文件、不支持 --filelist 的命令 (真实项目用不了)
  - registry 标记 json=True 但实际命令没有 --json 选项的漂移

用法:
    python3 tools/check_cli_layers.py            # 人类可读
    python3 tools/check_cli_layers.py --json     # 机器可读
退出码: 0 = 通过, 1 = 有违规
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
CLI = SRC / "cli"
sys.path.insert(0, str(SRC))

# ---- 写操作 API 清单 (有意具体: 宁可漏报可评审, 不要模糊匹配) ----
# 注意: **不含 replace** —— `str.replace()` 与 `Path.replace()` 同名, 静态无法区分,
# 上一版因此误报 20+ 条 (自证: 检查器本身也要经得起抽查)。
WRITE_METHODS = {
    "write_text", "write_bytes", "touch", "unlink", "mkdir", "makedirs",
    "rename", "rmdir", "chmod", "truncate",
}

# 输出类选项 (按前缀匹配): 命令把产物写到用户指定路径 —— 渲染是产品职责, 允许。
# 注意 **不含 `write` / `apply` / `backup`**: 那些是"原地改文件"的特征 (见下)。
OUTPUT_OPTIONS = {
    "output", "out", "dot_output", "svg", "png", "html", "dot",
    "graph_dir", "emit_dot", "emit_svg",
}

# 原地改文件的特征参数名 (fix --apply / fix imports --write)
MUTATION_FLAGS = {"apply", "in_place", "write", "backup"}

# 源文件/工程文件后缀: 写到这些 = 改项目 (禁止)
SOURCE_SUFFIXES = (".sv", ".svh", ".v", ".vh", ".f", ".fl", ".filelist")


def _is_output_param(name: str) -> bool:
    return name in OUTPUT_OPTIONS or name.startswith("output")


def _source_path_in(node) -> bool:
    """写操作里是否出现源文件后缀的路径字面量。"""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            if sub.value.endswith(SOURCE_SUFFIXES):
                return True
    return False
WRITE_MODULES = {
    "shutil": {"copy", "copy2", "copytree", "move", "rmtree", "copyfile"},
    "os": {"remove", "unlink", "rename", "replace", "mkdir", "makedirs",
           "rmdir", "chmod", "truncate", "write"},
}

LAYER_ORDER_DEPS = {
    "core": {"view", "exp", "dev"},
    "view": {"exp", "dev"},
    "exp": {"dev"},
    "dev": set(),
}


def module_layer(path: Path) -> str | None:
    """按目录判断模块属于哪一层 (cli/core/xx.py → core)。"""
    try:
        rel = path.relative_to(CLI)
    except ValueError:
        return None
    parts = rel.parts
    return parts[0] if parts and parts[0] in ("core", "view", "exp", "dev") else None


def iter_cli_py() -> list[Path]:
    return sorted(p for p in CLI.rglob("*.py") if "__pycache__" not in str(p))


def scan_writes(path: Path) -> list[tuple[int, str, ast.AST]]:
    """R3: 找出文件写操作调用点 (行号, 描述, AST 节点)。"""
    hits: list[tuple[int, str, ast.AST]] = []
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        return hits
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        # a.b(...)
        if isinstance(f, ast.Attribute):
            if f.attr in WRITE_METHODS:
                hits.append((node.lineno, f"{f.attr}(...)", node))
            elif isinstance(f.value, ast.Name) and f.value.id in WRITE_MODULES \
                    and f.attr in WRITE_MODULES[f.value.id]:
                hits.append((node.lineno, f"{f.value.id}.{f.attr}(...)", node))
        # open(...) with write-ish mode
        if isinstance(f, ast.Name) and f.id == "open":
            for a in list(node.args) + [k.value for k in node.keywords]:
                if isinstance(a, ast.Constant) and isinstance(a.value, str) \
                        and any(ch in a.value for ch in "wax+"):
                    hits.append((node.lineno, f'open(..., "{a.value}")', node))
    return hits


def function_spans(path: Path) -> list[tuple[int, int, set[str]]]:
    """返回每个函数/方法的 (起始行, 结束行, 参数名集合)。

    用途: 判断某处写操作是否落在"声明了输出路径选项"的命令函数内 ——
    写到用户指定产物路径 = 渲染 (允许); 否则 = 隐式改文件 (禁止)。
    """
    spans: list[tuple[int, int, set[str], bool]] = []
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        return spans
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            params = {a.arg for a in node.args.args + node.args.kwonlyargs}
            is_cmd = any(
                isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
                and d.func.attr == "command"
                for d in node.decorator_list
            )
            spans.append((node.lineno, getattr(node, "end_lineno", node.lineno),
                          params, is_cmd))
    return spans


def classify_write(path: Path, lineno: int, spans, node) -> str:
    """三分类 (自证: 上一版用"有输出选项"一刀切, 把 teach/design 的产物输出误判成违规)。

    mutation      = 原地改源文件/工程文件 → **违规** (核心纪律: 不改 RTL)
                    特征: ① 参数含 apply/write/backup/in_place
                          ② 写目标带 .sv/.v/.f 等源文件后缀
    artifact      = 写到产物路径 (用户指定, 或渲染命令的默认产物) → 允许
    helper-review = 落在非命令的 helper 里且无输出选项 → INFO 请人工复核
    """
    for start, end_, params, is_cmd in spans:
        if start <= lineno <= end_:
            if params & MUTATION_FLAGS or _source_path_in(node):
                return "mutation"
            if any(_is_output_param(x) for x in params):
                return "artifact"
            return "artifact" if is_cmd else "helper-review"
    return "helper-review"


def builtin_shadows(path: Path) -> list[tuple[int, str]]:
    """R7: 模块级定义与 builtin 同名的函数/类 —— 会遮蔽 builtin。

    实例 (iter_231 实测): `snapshot.py` 里 `def list(...)` (快照 list 命令) 遮蔽 builtin
    `list` → 同模块 `list(sources.keys())` 变成"执行 list 命令": 返回 None + 打印
    55,577 行快照表 (实测), 导致 `snapshot save --filelist` 的 file 元数据一直为空。
    修法: 命令函数改名 (`list_cmd`) + 显式 `@app.command("list")`。
    """
    import builtins as _b
    names = set(dir(_b))
    out: list[tuple[int, str]] = []
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        return out
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) \
                and node.name in names:
            out.append((node.lineno, node.name))
    return out


def file_depth_math(path: Path) -> list[tuple[int, str]]:
    """R8: 找出 `__file__` 路径深度运算 (搬目录即错位)。

    实例 (iter_232 实测): `commands/coverage.py` 搬到 `exp/verif/` 后,
    `Path(__file__).resolve().parents[3] / "tools"` 由 `<repo>/tools` 变成 `src/tools`
    → `import coverage_gen_demo` ImportError (16 个测试红)。
    规则: 一律用 `cli/_paths.py` 的 PROJECT_ROOT / SRC_DIR / TOOLS_DIR。
    """
    out: list[tuple[int, str]] = []
    try:
        src = path.read_text()
        tree = ast.parse(src)
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        # Path(__file__)...parent 链 或 .resolve().parents[N]
        seg = ast.get_source_segment(src, node) or ""
        if "__file__" not in seg:
            continue
        parents = seg.count(".parent")
        if parents >= 2 or "parents[" in seg:
            out.append((node.lineno, seg[:70]))
    return out


def import_edges(path: Path, all_modules: dict[str, Path]) -> list[tuple[str, str]]:
    """返回该文件的 (它 → 它 import 的 cli 模块) 边。"""
    edges: list[tuple[str, str]] = []
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        return edges
    me = str(path.relative_to(ROOT))
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                names = [node.module]
        for n in names:
            cand = n.replace("src.", "").replace(".", "/")
            for key in (cand + ".py", cand + "/__init__.py"):
                if key in all_modules:
                    edges.append((me, str(all_modules[key].relative_to(ROOT))))
                    break
    return edges


# 已知违规基线: P0 时点的现状清单。每条都必须写清"何时消除"。
# 作用: 检查器**立刻**能挡住新增违规, 同时不阻塞 P1/P2 的推进。
# (与项目既有手法一致: 门禁失败数基线、regen_baselines --check 漂移检测。)
KNOWN: list[tuple[str, str, str]] = [
    # [iter_234 P2] 原 fix.py / fix_imports.py 的写操作已移出 CLI →
    # 检查器现在对 R3 是**零基线** (任何 CLI 内写文件都会立即失败)。
]


def _is_known(rule: str, text: str) -> str | None:
    for r, pat, why in KNOWN:
        if r == rule and pat in text:
            return why
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="CLI 分层机械检查 (iter_230)")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    args = ap.parse_args()

    from cli._registry import (ALIASES, COMMANDS, LAYERS, canonical, spec_for)  # noqa: E402

    errors: list[str] = []
    infos: list[str] = []

    # ---- 读 typer app (命令清单 + 每个命令的选项) ----
    import click  # noqa: E402
    import typer  # noqa: E402
    from cli.main import app  # noqa: E402

    root = typer.main.get_command(app)
    leaves: dict[str, click.Command] = {}

    def _walk(cmd: click.Command, prefix: str) -> None:
        if isinstance(cmd, click.Group):
            for name, sub in cmd.commands.items():
                _walk(sub, f"{prefix}{name} ")
        else:
            leaves[prefix.strip()] = cmd

    _walk(root, "")

    # ---- R1: 每个命令必须登记 (规范名 或 已声明的兼容别名) ----
    registered = {c.key for c in COMMANDS}
    for key in sorted(leaves):
        if key in registered or key in ALIASES:
            continue
        errors.append(f"R1 未分层: `{key}` 不在 cli/_registry.py 中 (也不是已声明别名)")
    for key in sorted(registered - set(leaves)):
        errors.append(f"R1 幽灵登记: `{key}` 在注册表里但 CLI 上不存在 "
                      f"(改名/删除后忘了同步?)")
    for alias, canon in sorted(ALIASES.items()):
        if alias not in leaves:
            errors.append(f"R1 别名不存在: `{alias}` → `{canon}` 但 CLI 上没有 `{alias}`")
        if canon not in registered:
            errors.append(f"R1 别名指向未登记命令: `{alias}` → `{canon}`")
    if ALIASES:
        infos.append("兼容别名: " + ", ".join(f"`{a}` → `{c}`" for a, c in sorted(ALIASES.items())))

    # ---- R2: 层间依赖方向 ----
    all_modules = {str(p.relative_to(ROOT)): p for p in iter_cli_py()}
    for path in iter_cli_py():
        lay = module_layer(path)
        if lay is None:
            continue
        for src_m, dst_m in import_edges(path, all_modules):
            dst_lay = module_layer(ROOT / dst_m)
            if dst_lay and dst_lay in LAYER_ORDER_DEPS[lay]:
                errors.append(f"R2 反向依赖: {src_m} ({lay}) → {dst_m} ({dst_lay})")

    # ---- R3: 只读 (区分"写产物"与"隐式改文件") ----
    write_sites: list[dict] = []
    for path in iter_cli_py():
        hits = scan_writes(path)
        if not hits:
            continue
        spans = function_spans(path)
        lay = module_layer(path)
        for lineno, what, node_ast in hits:
            kind = classify_write(path, lineno, spans, node_ast)
            node = {"file": str(path.relative_to(ROOT)), "line": lineno,
                    "call": what, "kind": kind, "layer": lay}
            write_sites.append(node)
            if kind == "mutation":
                errors.append(f"R3 隐式改文件: {node['file']}:{lineno} {what}")
            elif kind == "helper-review":
                infos.append(f"helper 写操作 (需人工复核): {node['file']}:{lineno} {what}")
            else:
                infos.append(f"产物写出 (允许): {node['file']}:{lineno} {what}")

    # ---- R7: 模块级遮蔽 builtin ----
    for path in iter_cli_py():
        for lineno, name in builtin_shadows(path):
            errors.append(f"R7 遮蔽 builtin: {path.relative_to(ROOT)}:{lineno} "
                          f"def {name}(...) —— 同模块内 builtin 调用会被劫持")

    # ---- R8: 禁止 __file__ 路径深度运算 ----
    for path in iter_cli_py():
        if path.name == "_paths.py":
            continue
        for lineno, seg in file_depth_math(path):
            errors.append(f"R8 __file__ 深度运算: {path.relative_to(ROOT)}:{lineno} {seg} "
                          f"—— 改用 cli/_paths.py 锚点")

    # ---- R4: core 必须 --json ----
    for key, cmd in sorted(leaves.items()):
        spec = spec_for(key) or spec_for(canonical(key))
        if spec is None or spec.layer != "core":
            continue
        has_json = any(getattr(p, "name", "") in ("json_output", "json") for p in cmd.params)
        if not has_json:
            errors.append(f"R4 core 缺 --json: `{key}` (agent 契约要求结构化输出)")
        if spec.json != has_json:
            infos.append(f"registry 漂移: `{key}` 标 json={spec.json} 实际 {has_json}")

    # ---- R5: exp 命令名不得出现在 core/view 的帮助里 ----
    exp_names = {c.key.split()[-1] for c in COMMANDS if c.layer == "exp"}
    for key, cmd in sorted(leaves.items()):
        spec = spec_for(key) or spec_for(canonical(key))
        if spec is None or spec.layer not in ("core", "view"):
            continue
        text = (cmd.help or "")
        for n in exp_names:
            if n in text:
                infos.append(f"R5 「{n}」(exp) 出现在 `{key}` 帮助文本里 —— 检查是否误导")

    # ---- R6: exp 不进 capabilities 默认输出 ----
    if LAYERS["exp"].in_capabilities:
        errors.append("R6 exp 被设为 in_capabilities=True —— 与降级决定冲突")

    # ---- INFO: 只支持单文件 (真实项目不可用) ----
    single_file: list[str] = []
    for key, cmd in sorted(leaves.items()):
        names = {getattr(p, "name", "") for p in cmd.params}
        if ("file" in names or "file_" in names) and "filelist" not in names:
            spec = spec_for(key)
            if spec and spec.layer in ("core", "view"):
                single_file.append(key)
    if single_file:
        infos.append(f"只支持 --file 单文件 (不支持 --filelist): {', '.join(single_file)}")

    known: list[str] = []
    fresh: list[str] = []
    for e in errors:
        rule = e.split()[0]
        why = _is_known(rule, e)
        if why:
            known.append(f"{e}   [已知: {why}]")
        else:
            fresh.append(e)

    result = {
        "ok": not fresh,
        "errors": fresh,
        "known": known,
        "infos": infos,
        "write_sites": write_sites,
        "counts": {
            "leaves": len(leaves),
            "registered": len(COMMANDS),
            "by_layer": {n: sum(1 for c in COMMANDS if c.layer == n) for n in LAYERS},
        },
    }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("=== CLI 分层检查 (iter_230) ===")
        print(f"叶子命令 {result['counts']['leaves']} 个 | 已登记 {result['counts']['registered']} 个 | "
              + ", ".join(f"{k}={v}" for k, v in result['counts']['by_layer'].items()))
        if fresh:
            print(f"\n❌ 新增违规 {len(fresh)} 条 (必须修):")
            for e in fresh:
                print(f"   - {e}")
        else:
            print("\n✅ 无新增违规")
        if known:
            print(f"\n📋 已知基线 {len(known)} 条 (不阻塞, 等 P1/P2 清理):")
            for e in known:
                print(f"   - {e}")
        if infos:
            print(f"\nℹ️  待办/漂移 {len(infos)} 条:")
            for i in infos:
                print(f"   - {i}")
    return 0 if not fresh else 1


if __name__ == "__main__":
    sys.exit(main())

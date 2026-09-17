#!/usr/bin/env python3
"""
gen_cli_surface.py — [iter_230 P0] 从代码生成 CLI 能力清单 (docs/CLI_SURFACE.md)

为什么: 手写的命令清单一定会烂 —— 本仓库的 `docs/ARCHITECTURE.md` 就烂过
(写"23 commands"实际 21 组 64 命令; 写 driver_extractor 3987 行实际 1445 行)。
本脚本让"命令清单"成为**生成物**: 数据来自 `cli/_registry.py`(分层声明) +
typer/click introspection(实际选项), 两者不一致时 `--check` 报错。

用法:
    python3 tools/gen_cli_surface.py            # 写入 docs/CLI_SURFACE.md
    python3 tools/gen_cli_surface.py --check    # 只校验是否漂移 (CI / 提交前)
    python3 tools/gen_cli_surface.py --json     # stdout JSON (供 agent/脚本消费)
退出码: 0 = 已同步/已写入; 1 = --check 发现漂移
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
OUT = ROOT / "docs" / "CLI_SURFACE.md"
sys.path.insert(0, str(SRC))

# 输出类选项 (判断"能不能写产物")
OUTPUT_OPTIONS = {"output", "out", "dot_output", "svg", "png", "html", "dot",
                  "graph_dir", "emit_dot", "emit_svg"}


def collect() -> dict:
    import click
    import typer
    from cli.main import app
    from cli._registry import (ALIASES, COMMANDS, LAYERS, NEW_PLANNED,
                               aliases_of, counts)

    root = typer.main.get_command(app)
    leaves: dict[str, click.Command] = {}

    def _walk(cmd: click.Command, prefix: str) -> None:
        if isinstance(cmd, click.Group):
            for name, sub in cmd.commands.items():
                _walk(sub, f"{prefix}{name} ")
        else:
            leaves[prefix.strip()] = cmd

    _walk(root, "")

    def opts_of(cmd: click.Command) -> list[str]:
        return [p.name for p in cmd.params if isinstance(p, click.Option)]

    rows = []
    for spec in COMMANDS:
        cmd = leaves.get(spec.key)
        opts = opts_of(cmd) if cmd else []
        rows.append({
            "name": spec.key,
            "planned_name": spec.planned_name,
            "aliases": aliases_of(spec.key),
            "layer": spec.layer,
            "group": spec.group,
            "kind": spec.kind,
            "cost": spec.cost,
            "json": "json_output" in opts or "json" in opts,
            "stateful": spec.stateful,
            "recommended": spec.recommended,
            "filelist": "filelist" in opts,
            "options": len(opts),
            "outputs": [o for o in opts if o in OUTPUT_OPTIONS],
            "note": spec.note,
            "exists": cmd is not None,
        })

    return {
        "generated_at": date.today().isoformat(),
        "counts": counts(),
        "layers": {n: {"consumer": l.consumer, "stability": l.stability,
                       "readonly": l.readonly, "json_required": l.json_required,
                       "schema_version": l.schema_version, "note": l.note}
                   for n, l in LAYERS.items()},
        "planned_new": NEW_PLANNED,
        "aliases": dict(ALIASES),
        "rows": rows,
    }


def render(data: dict) -> str:
    L = []
    c = data["counts"]
    L.append("# CLI 能力清单 (生成物 — 请勿手改)")
    L.append("")
    L.append(f"> **生成方式**: `python3 tools/gen_cli_surface.py`  "
             f"(数据源: `src/cli/_registry.py` + typer introspection)")
    L.append(f"> **生成日期**: {data['generated_at']}  |  "
             f"**漂移校验**: `python3 tools/gen_cli_surface.py --check`")
    L.append("> **分层检查**: `python3 tools/check_cli_layers.py` (R1~R6)")
    L.append("")
    L.append("## 总览")
    L.append("")
    L.append(f"- 叶子命令总数: **{c['total']}**")
    L.append("- 按层: " + ", ".join(f"`{k}`={v}" for k, v in sorted(c["by_layer"].items())))
    L.append("- core 内分组: " + ", ".join(f"`{k}`={v}" for k, v in c["core_by_group"].items()))
    L.append("")
    L.append("| 层 | 消费者 | 稳定性 | 只读 | 必须 JSON | schema | 说明 |")
    L.append("|---|---|---|---|---|---|---|")
    for n, l in data["layers"].items():
        L.append(f"| `{n}` | {l['consumer']} | {l['stability']} | "
                 f"{'✅' if l['readonly'] else '—'} | "
                 f"{'✅' if l['json_required'] else '—'} | "
                 f"{l['schema_version'] or '—'} | {l['note']} |")
    L.append("")

    for layer in ("core", "view", "exp", "dev", "out"):
        rows = [r for r in data["rows"] if r["layer"] == layer]
        if not rows:
            continue
        L.append(f"## `{layer}` ({len(rows)} 个)")
        L.append("")
        L.append("| 命令 | 兼容别名 | 计划改名 | 组 | 类型 | 成本 | JSON | filelist | 状态 | 说明 |")
        L.append("|---|---|---|---|---|---|---|---|---|---|")
        for r in sorted(rows, key=lambda x: (x["group"], x["name"])):
            state = "✅" if r["exists"] else "❌ 不存在"
            if not r["json"] and layer == "core":
                state += " ⚠️缺JSON"
            alias_txt = ", ".join(f"`{a}`" for a in r["aliases"]) or "—"
            L.append(f"| `{r['name']}` | {alias_txt} | {r['planned_name'] or '—'} | "
                     f"{r['group']} | {r['kind']} | {r['cost']} | "
                     f"{'✅' if r['json'] else '—'} | "
                     f"{'✅' if r['filelist'] else '—'} | {state} | {r['note']} |")
        L.append("")

    if data.get("aliases"):
        L.append("## 兼容别名 (老名保留, 同一实现)")
        L.append("")
        L.append("| 别名 | 规范名 |")
        L.append("|---|---|")
        for a, c in sorted(data["aliases"].items()):
            L.append(f"| `{a}` | `{c}` |")
        L.append("")

    L.append("## 计划新增 (语义 core 缺口: instance 查询)")
    L.append("")
    L.append("| 新命令 | 复用现有 API | 输出 |")
    L.append("|---|---|---|")
    for n in data["planned_new"]:
        L.append(f"| `{n['name']}` | {n['reuse']} | {n['output']} |")
    L.append("")
    return "\n".join(L) + "\n"


def _strip_volatile(text: str) -> str:
    """比对时忽略**易变字段** (生成日期)。

    [iter_232 自证] 第一版 `--check` 直接比全文 → 跨天后必然误报
    ("命令/分层/选项有变", 实则只差日期)。漂移检查必须只比稳定内容。
    """
    return re.sub(r"^> \*\*生成日期\*\*: .*$", "> **生成日期**: <date>",
                  text, flags=re.MULTILINE)


def main() -> int:
    ap = argparse.ArgumentParser(description="生成 CLI 能力清单 (iter_230)")
    ap.add_argument("--check", action="store_true", help="只校验漂移, 不写文件")
    ap.add_argument("--json", action="store_true", help="stdout JSON")
    ap.add_argument("--fingerprint", action="store_true",
                    help="打印**稳定指纹** (只含命令面, 不含日期) —— 搬目录时用它证明纯搬迁")
    args = ap.parse_args()

    data = collect()
    if args.fingerprint:
        # [iter_233] 搬目录的"纯搬迁"证明: 只对命令面取指纹, 排除易变字段 (日期)。
        import hashlib
        stable = {
            "counts": data["counts"],
            "aliases": data["aliases"],
            "layers": data["layers"],
            "rows": data["rows"],
        }
        payload = json.dumps(stable, sort_keys=True, ensure_ascii=False)
        print(hashlib.sha256(payload.encode()).hexdigest())
        return 0
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    text = render(data)
    if args.check:
        if not OUT.exists():
            print(f"❌ {OUT.relative_to(ROOT)} 不存在 — 跑 `python3 tools/gen_cli_surface.py`")
            return 1
        if _strip_volatile(OUT.read_text()) != _strip_volatile(text):
            print(f"❌ {OUT.relative_to(ROOT)} 与代码不一致 (命令/分层/选项有变) — 重新生成")
            return 1
        print(f"✅ {OUT.relative_to(ROOT)} 与代码一致")
        return 0

    OUT.write_text(text)
    print(f"✅ 已写入 {OUT.relative_to(ROOT)}  ({data['counts']['total']} 个命令)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

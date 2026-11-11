"""[P91 / A] `sv_query filelist prune` — top-aware conservative filelist pruning."""
from __future__ import annotations

import json
from pathlib import Path

import typer

from cli._common import _read_filelist_full
from trace.core.top_prune import prune_sources

filelist_app = typer.Typer(help="Filelist 操作 (只读/显式输出)")


def _write_output(output: Path, selected: list[str], write_enabled: bool, force: bool) -> dict:
    """Validate and optionally write a pruned filelist (default dry-run)."""
    out = Path(output)
    suffix = out.suffix.lower()
    if suffix not in {".f", ".fl"}:
        return {"error": f"refusing non-filelist output suffix: {suffix or '<none>'}",
                "kind": "unsafe_output_suffix"}
    if out.exists() and not force:
        return {"error": f"output already exists: {out} (use --force to backup+overwrite)",
                "kind": "output_exists"}
    patch = {"output": str(out), "written": False, "dry_run": not write_enabled}
    if not write_enabled:
        patch["requires_apply"] = True
        return patch
    backup = None
    if out.exists():
        backup = out.with_suffix(out.suffix + ".bak")
        i = 1
        while backup.exists():
            backup = out.with_suffix(out.suffix + f".bak{i}")
            i += 1
        backup.write_bytes(out.read_bytes())
    out.write_text("\n".join(selected) + "\n", encoding="utf-8")
    patch.update({"written": True, "backup": str(backup) if backup else None})
    return patch


@filelist_app.command("prune")
def prune_cmd(
    filelist: str = typer.Option(..., "--filelist", help="完整 filelist (.f/.fl)"),
    top: str = typer.Option(..., "--top", help="目标 top module"),
    output: Path = typer.Option(None, "--output", "-o",
                                help="目标 filelist 路径 (.f/.fl)；默认 dry-run"),
    apply: bool = typer.Option(False, "--apply",
                               help="真正写入 --output (默认只预览)"),
    force: bool = typer.Option(False, "--force",
                               help="允许覆盖已有 filelist；先写 .bak 备份"),
    json_output: bool = typer.Option(False, "--json", "-j"),
    pretty: bool = typer.Option(False, "--pretty", "-p"),
) -> None:
    """从完整 filelist 中裁出 top 可达的保守子集。

    这是候选裁剪，不是语义证明：package/interface/无声明文件/读失败文件都会保留；
    top 找不到时返回完整 filelist 并标 reason=top_not_found。
    """
    fl = Path(filelist)
    if not fl.exists():
        raise typer.BadParameter(f"filelist not found: {fl}")
    sources, _incdirs = _read_filelist_full(str(fl), base_dir=fl.parent.resolve())
    result = prune_sources(sources, top)
    data = {
        "ok": True,
        "command": "filelist_prune",
        "params": {"filelist": str(fl), "top": top},
        "result": result.as_dict(),
    }
    if output is not None:
        patch = _write_output(output, result.selected, apply, force)
        if patch.get("kind"):
            data = {"ok": False, "command": "filelist_prune",
                    "error": patch["error"],
                    "errors": [{"kind": patch["kind"], "output": str(output)}]}
            if json_output:
                print(json.dumps(data, indent=2 if pretty else None, ensure_ascii=False))
            else:
                print(patch["error"], file=__import__("sys").stderr)
            raise typer.Exit(code=1)
        data["result"].update(patch)
    if json_output:
        print(json.dumps(data, indent=2 if pretty else None, ensure_ascii=False))
        return
    r = data["result"]
    print(f"filelist: {r['total_files']} files")
    print(f"top:      {top}")
    print(f"selected: {r['selected_count']} / {r['total_files']} ({r['reason']})")
    for p in result.selected:
        print(f"  {p}")
    if output is not None:
        print(f"wrote: {output}")

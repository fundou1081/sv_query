"""[P91 / A] `sv_query filelist prune` — top-aware conservative filelist pruning."""
from __future__ import annotations

import json
from pathlib import Path

import typer

from cli._common import _read_filelist_full
from trace.core.top_prune import prune_sources

filelist_app = typer.Typer(help="Filelist 操作 (只读/显式输出)")


@filelist_app.command("prune")
def prune_cmd(
    filelist: str = typer.Option(..., "--filelist", help="完整 filelist (.f/.fl)"),
    top: str = typer.Option(..., "--top", help="目标 top module"),
    output: Path = typer.Option(None, "--output", "-o",
                                help="把 selected files 写成新 filelist (显式路径)"),
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
        output.write_text("\n".join(result.selected) + "\n", encoding="utf-8")
        data["result"]["output"] = str(output)
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

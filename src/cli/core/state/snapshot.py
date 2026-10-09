"""
snapshot save/compare/list/show/delete 子命令
"""

import json
import logging
import sys
from pathlib import Path

import typer

from cli._paths import ensure_on_path, PROJECT_ROOT  # noqa: E402
ensure_on_path(PROJECT_ROOT)


from trace.core.snapshot_manager import SnapshotManager
from trace.unified_tracer import UnifiedTracer

snapshot_app = typer.Typer(help="Snapshot management for graph diff")

logger = logging.getLogger(__name__)


def _get_tracer_from_file(file_path, ):
    """从文件构建 UnifiedTracer"""
    import os
    # 收集所有 .sv 文件
    sv_files = []
    if file_path.is_dir():
        for root, _walk_dirs, walk_files in os.walk(file_path):
            # 跳过隐藏目录和 build 目录
            _walk_dirs[:] = [d for d in _walk_dirs if not d.startswith(".") and d not in ("build", "sim", "__pycache__")]
            for f in walk_files:
                if f.endswith(".sv") or f.endswith(".svh"):
                    sv_files.append(Path(root) / f)
    elif file_path.suffix in (".sv", ".svh"):
        sv_files = [file_path]
    else:
        raise ValueError(f"Unsupported file type: {file_path}")

    if not sv_files:
        raise ValueError(f"No .sv files found in {file_path}")

    # 构建 sources 字典
    sources_dict = {}
    for f in sv_files:
        try:
            with open(f) as fp:
                sources_dict[str(f)] = fp.read()
        except Exception as e:
            logger.warning(f"Failed to read {f}: {e}")
            continue

    tracer = UnifiedTracer(sources=sources_dict)
    tracer.build_graph()
    return tracer, [str(f) for f in sv_files]


def _get_tracer_from_filelist(filelist, preprocess_macros=True):
    """[Req-20 2026-06-12] 从 filelist 构建 UnifiedTracer (snapshot filelist 模式)

    [FIX 2026-07-04 B4] Use `UnifiedTracer(filelist=...)` instead of pre-reading
    sources via _read_filelist (which had base_dir bug causing 0 sources).
    """
    tracer = UnifiedTracer(filelist=filelist, preprocess_macros=preprocess_macros)
    tracer.build_graph()
    # [B4] Get file paths from the tracer for the snapshot metadata
    file_paths_list = list(tracer._compiler._sources.keys()) if hasattr(tracer, '_compiler') and tracer._compiler else []
    return tracer, file_paths_list


@snapshot_app.command()
def save(
    path: Path = typer.Argument(..., help="File or directory to snapshot"),
    tag: str = typer.Option("", "--tag", "-t", help="Snapshot tag (e.g., v1.2.3)"),
    git: bool = typer.Option(False, "--git", "-g", help="Auto-capture git commit hash"),
    filelist: str = typer.Option(None, "--filelist", help="[Req-20 2026-06-12] Path to filelist (.f/.fl) for multi-file projects"),
    preprocess_macros: bool = typer.Option(True, "--preprocess/--no-preprocess", help="[Req-20] 跨文件 `MACRO 展开"),
    json_output: bool = typer.Option(False, "--json", "-j", help="[iter_231] Output JSON (core 契约)"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="[JSON] Pretty-print"),
):
    """Save current code state as a snapshot

    [iter_224] 恒定严格: elaboration error 会 raise; 已解析到的 elaboration 错误
    仍随图存下 (供 fix/snapshot compare 用)。
    [ADD 2026-06-12 Req-20] 支持 --filelist 跑多文件项目
    """
    try:
        # 获取 git commit
        git_commit = ""
        if git:
            import subprocess
            try:
                git_commit = (
                    subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
                    .decode().strip()[:8]
                )
            except Exception as e:
                logger.warning("%s: 忽略 Exception: %s", __name__, e)

        # 构建 tracer
        if filelist:
            tracer, files = _get_tracer_from_filelist(filelist, preprocess_macros=preprocess_macros)
        else:
            tracer, files = _get_tracer_from_file(path)
        graph = tracer.get_graph()

        # 获取 elaboration 错误
        elaboration_errors = tracer.get_elaboration_errors()
        # 过滤 None 跟非字符串 file
        failed_files = sorted({e["file"] for e in elaboration_errors if e.get("file") and isinstance(e.get("file"), str)})

        # 获取 tag
        if not tag:
            if git_commit:
                tag = git_commit
            else:
                from datetime import datetime
                tag = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 保存快照
        manager = SnapshotManager()
        graph_data = graph.to_dict()
        graph_data["elaboration_errors"] = elaboration_errors
        graph_data["failed_files"] = failed_files
        graph_data["strict_mode"] = True  # [iter_224] strict 已彻底移除, 语义恒为 True
        if files is None:
            files = []
        saved_path = manager.save(tag, graph_data, git_commit=git_commit, files=files)

        if json_output:
            print(json.dumps({
                "ok": True, "tag": tag, "path": str(saved_path),
                "files": len(files),
                "node_count": graph_data["node_count"],
                "edge_count": graph_data["edge_count"],
                "elaboration_errors": len(elaboration_errors),
                "failed_files": [str(f) for f in (failed_files or [])],
            }, indent=2 if pretty else None, ensure_ascii=False))
            return

        print(f"✅ Snapshot saved: {tag}")
        print(f"   Path: {saved_path}")
        print(f"   Files: {len(files)}")
        print(f"   Nodes: {graph_data['node_count']}")
        print(f"   Edges: {graph_data['edge_count']}")
        if elaboration_errors:
            n_errors = len(elaboration_errors)
            n_files = len(failed_files)
            print(f"   ⚠️  Elaboration: {n_errors} error(s) in {n_files} file(s)")
            from collections import Counter
            code_counts = Counter(e["code"] for e in elaboration_errors)
            for code, cnt in code_counts.most_common(5):
                print(f"      {code}: {cnt}")
            if len(code_counts) > 5:
                print(f"      ... and {len(code_counts) - 5} more error types")
            if failed_files:
                shown = ", ".join(Path(f).name for f in failed_files[:5])
                more = f", ... +{len(failed_files) - 5}" if len(failed_files) > 5 else ""
                print(f"      Failed files: {shown}{more}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=1) from None


@snapshot_app.command("list")
def list_cmd(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """List all snapshots

    [iter_231] 函数改名 `list_cmd` —— 模块级 `def list(...)` 会**遮蔽 builtin list**,
    导致本模块内所有 `list(...)` 调用都去执行这个命令 (实测: `snapshot save --json`
    打印 4956 行快照表; `snapshot save --filelist` 的 `list(sources.keys())` 也中招,
    静默拿到 None)。命令名仍是 `list` (显式 command("list"))。
    """
    manager = SnapshotManager()
    tags = manager.list_tags()
    # [iter_239 1b] 旧位置提示 (只提示, **不读取** —— 不做 silent fallback)
    from trace.core.snapshot_manager import LEGACY_SNAPSHOT_DIR
    _legacy = Path(LEGACY_SNAPSHOT_DIR)
    if not tags and _legacy.is_dir() and any(_legacy.glob("*.json")):
        print(f"💡 当前目录 ({manager.base_dir}) 无快照, 但旧位置 {LEGACY_SNAPSHOT_DIR}/ 有 "
              f"{len(list(_legacy.glob('*.json')))} 个 (iter_239 起默认不再写项目目录)。",
              file=sys.stderr)
        print(f"   要使用旧快照: SVQ_SNAPSHOT_DIR={LEGACY_SNAPSHOT_DIR} svq snapshot list",
              file=sys.stderr)
    snapshots = [manager.show(t) for t in tags]

    if json_output:
        print(json.dumps(snapshots, indent=2))
    else:
        if not snapshots:
            print("No snapshots found. Run: svq snapshot save <file> -t <tag>")
            return
        print(f"Found {len(snapshots)} snapshots:\n")
        print(f"{'Tag':<20} {'Created':<25} {'Nodes':<8} {'Edges':<8} Files")
        print("-" * 100)
        for s in snapshots:
            created = s.get("created_at", "")[:19]
            files = ", ".join([Path(f).name for f in s.get("files", [])[:3]])
            if len(s.get("files", [])) > 3:
                files += f" +{len(s['files']) - 3} more"
            print(f"{s['tag']:<20} {created:<25} {s['node_count']:<8} {s['edge_count']:<8} {files}")


@snapshot_app.command()
def show(
    tag: str = typer.Argument(..., help="Snapshot tag"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Show snapshot details"""
    manager = SnapshotManager()
    # [FIX 2026-07-06] SnapshotManager API 已用 'show(tag)' / 'delete(tag)', 不是 'get_snapshot' / 'delete_snapshot'
    info = manager.show(tag)
    if not info:
        print(f"Snapshot not found: {tag}")
        raise typer.Exit(code=1)

    if json_output:
        print(json.dumps(info, indent=2))
    else:
        print(f"Tag: {tag}")
        print(f"Created: {info.get('created_at', '')}")
        print(f"Git commit: {info.get('git_commit', 'N/A')}")
        print(f"Files: {len(info.get('files', []))}")
        for f in info.get("files", []):
            print(f"  - {f}")
        print(f"Nodes: {info['node_count']}")
        print(f"Edges: {info['edge_count']}")
        if info.get("elaboration_errors"):
            print(f"\nElaboration errors: {len(info['elaboration_errors'])}")


@snapshot_app.command()
def delete(
    tag: str = typer.Argument(..., help="Snapshot tag"),
    force: bool = typer.Option(False, "--force", "-f", help="Force delete without confirmation"),
    json_output: bool = typer.Option(False, "--json", "-j", help="[iter_231] Output JSON (core 契约)"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="[JSON] Pretty-print"),
):
    """Delete a snapshot"""
    manager = SnapshotManager()
    if not manager.show(tag):
        if json_output:
            print(json.dumps({"ok": False, "tag": tag, "deleted": False,
                              "error": "snapshot not found"},
                             indent=2 if pretty else None, ensure_ascii=False))
            raise typer.Exit(code=1)
        print(f"Snapshot not found: {tag}")
        raise typer.Exit(code=1)
    if not force:
        confirm = input(f"Delete snapshot '{tag}'? [y/N]: ")
        if confirm.lower() != "y":
            if json_output:
                print(json.dumps({"ok": True, "tag": tag, "deleted": False,
                                  "cancelled": True},
                                 indent=2 if pretty else None, ensure_ascii=False))
                return
            print("Cancelled")
            return
    manager.delete(tag)
    if json_output:
        print(json.dumps({"ok": True, "tag": tag, "deleted": True},
                         indent=2 if pretty else None, ensure_ascii=False))
        return
    print(f"✅ Deleted: {tag}")


@snapshot_app.command()
def compare(
    tag1: str = typer.Argument(..., help="First snapshot tag"),
    tag2: str = typer.Argument(..., help="Second snapshot tag"),
    top: int = typer.Option(20, "--top", "-n", help="Number of top changes to show"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    show_edges: bool = typer.Option(False, "--show-edges/--no-show-edges", help="Show edge-level diff details (default OFF, 跟旧行为兼容)"),
):
    """Compare two snapshots"""
    manager = SnapshotManager()
    snap1 = manager.load(tag1)
    snap2 = manager.load(tag2)

    if not snap1:
        print(f"Snapshot not found: {tag1}")
        raise typer.Exit(code=1)
    if not snap2:
        print(f"Snapshot not found: {tag2}")
        raise typer.Exit(code=1)

    # [FIX 2026-06-12] 直接用 SnapshotManager.compare (内置逻辑)
    result = manager.compare(tag1, tag2) or {}
    # [FIX 2026-06-12] 显示 node_count 差 (向后兼容 simple compare)
    if snap1 and snap2:
        nc1 = snap1.get("node_count", 0)
        nc2 = snap2.get("node_count", 0)
        result.setdefault("node_count_1", nc1)
        result.setdefault("node_count_2", nc2)
        result.setdefault("node_diff", nc2 - nc1)

    if json_output:
        print(json.dumps(result, indent=2 if pretty else None))
    else:
        if "error" in result:
            print(f"Error: {result['error']}")
            return

        print(f"=== Snapshot Compare: {tag1} vs {tag2} ===\n")
        if "stable_core" in result:
            print(f"Stable core ({result.get('stable_core_count', '?')} nodes):")
            stable = result["stable_core"]
            shown = ", ".join(stable[:5])
            more = f"... ({len(stable) - 5} more)" if len(stable) > 5 else ""
            print(f"  {shown}{more}")
        if "added_nodes" in result:
            nodes_list = result["added_nodes"][:top]
            suffix = f"... ({len(result['added_nodes']) - top} more)" if len(result["added_nodes"]) > top else ""
            print(f"\n  Added nodes ({len(result['added_nodes'])}): {', '.join(nodes_list)}{suffix}")
        if "removed_nodes" in result:
            nodes_list = result["removed_nodes"][:top]
            suffix = f"... ({len(result['removed_nodes']) - top} more)" if len(result["removed_nodes"]) > top else ""
            print(f"  Removed nodes ({len(result['removed_nodes'])}): {', '.join(nodes_list)}{suffix}")
        if "added_edges" in result:
            edges = result["added_edges"]
            print(f"\n  Added edges: {len(edges)}")
            if show_edges:
                for edge in edges[:top]:
                    try:
                        if len(edge) >= 2:
                            print(f"    + {edge[0]} → {edge[1]}")
                    except TypeError as e:
                        logger.warning("%s: 忽略 TypeError: %s", __name__, e)
                if len(edges) > top:
                    print(f"    ... ({len(edges) - top} more)")
        if "removed_edges" in result:
            edges = result["removed_edges"]
            print(f"  Removed edges: {len(edges)}")
            if show_edges:
                for edge in edges[:top]:
                    try:
                        if len(edge) >= 2:
                            print(f"    - {edge[0]} → {edge[1]}")
                    except TypeError as e:
                        logger.warning("%s: 忽略 TypeError: %s", __name__, e)
                if len(edges) > top:
                    print(f"    ... ({len(edges) - top} more)")

        # 兼容性输出
        if "coupling_level" in result:
            print(f"\n  Coupling level: {result['coupling_level']}")

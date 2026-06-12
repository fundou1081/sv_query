# ==============================================================================
# snapshot.py - snapshot management CLI commands
# [铁律13] 金标准测试优先
# ==============================================================================
# 子命令:
#   save <file> [-t tag]           保存当前代码的快照
#   list                            列出所有快照
#   show <tag>                     查看快照详情
#   delete <tag>                   删除快照
#   compare <tag1> <tag2>          对比两个快照
# ==============================================================================

import json
import logging
import sys
from pathlib import Path

import typer

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


from trace.core.snapshot_manager import SnapshotManager
from trace.unified_tracer import UnifiedTracer

snapshot_app = typer.Typer(help="Snapshot management for graph diff")

logger = logging.getLogger(__name__)


def _get_tracer_from_file(file_path: Path, strict: bool = False):
    """从文件构建 UnifiedTracer

    Args:
        file_path: .sv / .svh 文件或目录
        strict: True = elaboration error 立即 raise (默认 False, 允许部分图)

    [FIX 2026-06-11 Issue 17] 默认 strict=False 让 snapshot save 能存部分图
    """
    import os

    # 收集所有 .sv 文件
    sv_files = []
    if file_path.is_dir():
        for root, dirs, files in os.walk(file_path):
            # 跳过隐藏目录和 build 目录
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("build", "sim", "__pycache__")]
            for f in files:
                if f.endswith(".sv") or f.endswith(".svh"):
                    sv_files.append(Path(root) / f)
    elif file_path.suffix in (".sv", ".svh"):
        sv_files = [file_path]
    else:
        raise ValueError(f"Unsupported file type: {file_path}")

    if not sv_files:
        raise ValueError(f"No .sv files found in {file_path}")

    # 构建 sources 字典
    sources = {}
    for f in sv_files:
        try:
            with open(f) as fp:
                sources[str(f)] = fp.read()
        except Exception as e:
            logger.warning(f"Failed to read {f}: {e}")
            continue

    tracer = UnifiedTracer(sources=sources, strict=strict)
    tracer.build_graph()
    return tracer, [str(f) for f in sv_files]


@snapshot_app.command()
def save(
    path: Path = typer.Argument(..., help="File or directory to snapshot"),
    tag: str = typer.Option("", "--tag", "-t", help="Snapshot tag (e.g., v1.2.3)"),
    git: bool = typer.Option(False, "--git", "-g", help="Auto-capture git commit hash"),
    strict: bool = typer.Option(
        True, "--strict/--no-strict", help="Strict mode (default): elaboration error 时不存快照直接报错. Use --no-strict 存部分图并标记失败文件 (供分析不完整项目用)"
    ),
):
    """Save current code state as a snapshot

    [FIX 2026-06-11 Issue 17] 默认 non-strict: 即使有 elaboration error
    (MissingTimeScale / UndeclaredIdentifier / \$clog2 等) 仍存部分图,
    错误信息存到 snapshot metadata 供后续查询。 加上 --strict 才严格检查.
    """
    try:
        # 获取 git commit
        git_commit = ""
        if git:
            import subprocess

            try:
                git_commit = (
                    subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
                    .decode()
                    .strip()[:8]
                )
            except Exception:
                pass

        # 构建 tracer
        tracer, files = _get_tracer_from_file(path, strict=strict)
        graph = tracer.get_graph()

        # 获取 elaboration 错误 (即使 strict 模式也可拿到, 因为 build_graph 可能会跳过)
        elaboration_errors = tracer.get_elaboration_errors()
        failed_files = sorted({e["file"] for e in elaboration_errors if e.get("file")})

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
        # [FIX 2026-06-11 Issue 17] 把 elaboration 错误存到 snapshot metadata
        graph_data["elaboration_errors"] = elaboration_errors
        graph_data["failed_files"] = failed_files
        graph_data["strict_mode"] = strict
        saved_path = manager.save(tag, graph_data, git_commit=git_commit, files=files)

        print(f"✅ Snapshot saved: {tag}")
        print(f"   Path: {saved_path}")
        print(f"   Files: {len(files)}")
        print(f"   Nodes: {graph_data['node_count']}")
        print(f"   Edges: {graph_data['edge_count']}")
        if elaboration_errors:
            # 按失败文件汇总
            n_errors = len(elaboration_errors)
            n_files = len(failed_files)
            print(f"   ⚠️  Elaboration: {n_errors} error(s) in {n_files} file(s) (non-strict, 存了部分图)")
            # 按错误码统计
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


@snapshot_app.command()
def list(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """List all snapshots"""
    manager = SnapshotManager()
    snapshots = manager.list_summary()

    if not snapshots:
        print("No snapshots found. Run: svq diff snapshot save <file> -t <tag>")
        return

    if json_output:
        print(json.dumps(snapshots, indent=2, ensure_ascii=False))
    else:
        print(f"Found {len(snapshots)} snapshots:\n")
        print(f"{'TAG':<20} {'CREATED':<25} {'NODES':<8} {'EDGES':<8} {'FILES'}")
        print("-" * 80)
        for s in snapshots:
            created = s["created_at"][:19] if s["created_at"] else "N/A"
            files = ", ".join([Path(f).name for f in s["files"][:3]])
            if len(s["files"]) > 3:
                files += f" +{len(s['files']) - 3} more"
            print(f"{s['tag']:<20} {created:<25} {s['node_count']:<8} {s['edge_count']:<8} {files}")


@snapshot_app.command()
def show(
    tag: str = typer.Argument(..., help="Snapshot tag"),
):
    """Show snapshot details"""
    manager = SnapshotManager()
    info = manager.show(tag)

    if info is None:
        print(f"Snapshot not found: {tag}")
        raise typer.Exit(code=1)

    print(f"=== Snapshot: {tag} ===")
    print(f"Created: {info['created_at']}")
    print(f"Git commit: {info['git_commit'] or 'N/A'}")
    print(f"Files: {len(info['files'])}")
    for f in info["files"]:
        print(f"  - {f}")
    print(f"Nodes: {info['node_count']}")
    print(f"Edges: {info['edge_count']}")


@snapshot_app.command()
def delete(
    tag: str = typer.Argument(..., help="Snapshot tag to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Delete a snapshot"""
    if not force:
        confirm = input(f"Delete snapshot '{tag}'? [y/N] ")
        if confirm.lower() != "y":
            print("Cancelled")
            return

    manager = SnapshotManager()
    if manager.delete(tag):
        print(f"✅ Deleted: {tag}")
    else:
        print(f"Snapshot not found: {tag}")
        raise typer.Exit(code=1)


@snapshot_app.command()
def compare(
    tag1: str = typer.Argument(..., help="First snapshot tag"),
    tag2: str = typer.Argument(..., help="Second snapshot tag"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Compare two snapshots"""
    manager = SnapshotManager()
    result = manager.compare(tag1, tag2)

    if result is None:
        print(f"One or both snapshots not found: {tag1}, {tag2}")
        raise typer.Exit(code=1)

    if json_output:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"=== Comparing: {tag1} vs {tag2} ===\n")

        print("=== Graph Diff ===")
        if result["identical"]:
            print("  Graphs are identical")
        else:
            if result["added_nodes"]:
                print(
                    f"  Added nodes ({len(result['added_nodes'])}): {', '.join(result['added_nodes'][:5])}{'...' if len(result['added_nodes']) > 5 else ''}"
                )
            if result["removed_nodes"]:
                print(
                    f"  Removed nodes ({len(result['removed_nodes'])}): {', '.join(result['removed_nodes'][:5])}{'...' if len(result['removed_nodes']) > 5 else ''}"
                )
            if result["added_edges"]:
                print(f"  Added edges: {len(result['added_edges'])}")
            if result["removed_edges"]:
                print(f"  Removed edges: {len(result['removed_edges'])}")

        print("\n=== Architecture Health ===")
        print(f"  {tag1} health: {result['health_score_old']:.2%}")
        print(f"  {tag2} health: {result['health_score_new']:.2%}")
        print(f"  Delta: {result['health_delta']:+.2%}")

        print(
            f"\n  Stable core ({len(result['stable_core'])} nodes): {', '.join(result['stable_core'][:5])}{'...' if len(result['stable_core']) > 5 else ''}"
        )

        coupling = result.get("coupling_warning", {})
        level = coupling.get("level", "unknown")
        if level in ("critical", "high"):
            print(f"  Coupling warning: *** {level.upper()} ***")
        elif level == "medium":
            print("  Coupling warning: * MEDIUM *")
        else:
            print(f"  Coupling level: {level.upper()}")


if __name__ == "__main__":
    snapshot_app()

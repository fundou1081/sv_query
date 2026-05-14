#==============================================================================
# snapshot.py - snapshot management CLI commands
# [铁律13] 金标准测试优先
#==============================================================================
# 子命令:
#   save <file> [-t tag]           保存当前代码的快照
#   list                            列出所有快照
#   show <tag>                     查看快照详情
#   delete <tag>                   删除快照
#   compare <tag1> <tag2>          对比两个快照
#==============================================================================

import sys
import json
from pathlib import Path
import logging

import typer

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from trace.core.snapshot_manager import SnapshotManager
from trace.unified_tracer import UnifiedTracer
import pyslang

snapshot_app = typer.Typer(help="Snapshot management for graph diff")

logger = logging.getLogger(__name__)


def _get_tracer_from_file(file_path: Path):
    """从文件构建 UnifiedTracer"""
    import os
    
    # 收集所有 .sv 文件
    sv_files = []
    if file_path.is_dir():
        for root, dirs, files in os.walk(file_path):
            # 跳过隐藏目录和 build 目录
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('build', 'sim', '__pycache__')]
            for f in files:
                if f.endswith('.sv') or f.endswith('.svh'):
                    sv_files.append(Path(root) / f)
    elif file_path.suffix in ('.sv', '.svh'):
        sv_files = [file_path]
    else:
        raise ValueError(f"Unsupported file type: {file_path}")
    
    if not sv_files:
        raise ValueError(f"No .sv files found in {file_path}")
    
    # 构建 tracer
    trees = {}
    for f in sv_files:
        try:
            tree = pyslang.SyntaxTree.fromFile(str(f))
            trees[str(f)] = tree
        except Exception as e:
            logger.warning(f"Failed to parse {f}: {e}")
            continue
    
    tracer = UnifiedTracer(trees=trees)
    tracer.build_graph()
    return tracer, [str(f) for f in sv_files]


@snapshot_app.command()
def save(
    path: Path = typer.Argument(..., help="File or directory to snapshot"),
    tag: str = typer.Option("", "--tag", "-t", help="Snapshot tag (e.g., v1.2.3)"),
    git: bool = typer.Option(False, "--git", "-g", help="Auto-capture git commit hash"),
):
    """Save current code state as a snapshot"""
    try:
        # 获取 git commit
        git_commit = ""
        if git:
            import subprocess
            try:
                git_commit = subprocess.check_output(
                    ["git", "rev-parse", "HEAD"],
                    stderr=subprocess.DEVNULL
                ).decode().strip()[:8]
            except:
                pass
        
        # 构建 tracer
        tracer, files = _get_tracer_from_file(path)
        graph = tracer.get_graph()
        
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
        saved_path = manager.save(tag, graph_data, git_commit=git_commit, files=files)
        
        print(f"✅ Snapshot saved: {tag}")
        print(f"   Path: {saved_path}")
        print(f"   Files: {len(files)}")
        print(f"   Nodes: {graph_data['node_count']}")
        print(f"   Edges: {graph_data['edge_count']}")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=1)


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
            created = s['created_at'][:19] if s['created_at'] else 'N/A'
            files = ', '.join([Path(f).name for f in s['files'][:3]])
            if len(s['files']) > 3:
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
    for f in info['files']:
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
        if confirm.lower() != 'y':
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
        if result['identical']:
            print("  Graphs are identical")
        else:
            if result['added_nodes']:
                print(f"  Added nodes ({len(result['added_nodes'])}): {', '.join(result['added_nodes'][:5])}{'...' if len(result['added_nodes']) > 5 else ''}")
            if result['removed_nodes']:
                print(f"  Removed nodes ({len(result['removed_nodes'])}): {', '.join(result['removed_nodes'][:5])}{'...' if len(result['removed_nodes']) > 5 else ''}")
            if result['added_edges']:
                print(f"  Added edges: {len(result['added_edges'])}")
            if result['removed_edges']:
                print(f"  Removed edges: {len(result['removed_edges'])}")
        
        print("\n=== Architecture Health ===")
        print(f"  {tag1} health: {result['health_score_old']:.2%}")
        print(f"  {tag2} health: {result['health_score_new']:.2%}")
        print(f"  Delta: {result['health_delta']:+.2%}")
        
        print(f"\n  Stable core ({len(result['stable_core'])} nodes): {', '.join(result['stable_core'][:5])}{'...' if len(result['stable_core']) > 5 else ''}")
        
        coupling = result.get('coupling_warning', {})
        level = coupling.get('level', 'unknown')
        if level in ('critical', 'high'):
            print(f"  Coupling warning: *** {level.upper()} ***")
        elif level == 'medium':
            print(f"  Coupling warning: * MEDIUM *")
        else:
            print(f"  Coupling level: {level.upper()}")


if __name__ == "__main__":
    snapshot_app()

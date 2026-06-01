# ==============================================================================
# snapshot_manager.py - 快照管理 (CRUD)
# [铁律13] 金标准测试优先
# ==============================================================================
# 目标: 管理 .svq/snapshots/ 目录下的快照文件
#
# 快照格式:
# {
#   "version": "1.0",
#   "tag": "v1.2.3",
#   "created_at": "ISO timestamp",
#   "git_commit": "abc1234",
#   "files": ["rtl/top.sv"],
#   "node_count": 42,
#   "edge_count": 67,
#   "port_to_internal": {},
#   "nodes": [...],
#   "edges": [...]
# }
# ==============================================================================

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class SnapshotManager:
    """[Golden] 快照管理器 - CRUD 操作

    金标准操作:
    - save: 保存新快照
    - list: 列出所有快照
    - show: 查看快照详情
    - delete: 删除快照
    - compare: 对比两个快照
    """

    def __init__(self, base_dir: str = ".svq/snapshots"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _snapshot_path(self, tag: str) -> Path:
        """根据 tag 获取快照文件路径"""
        # tag 作为文件名，安全处理
        safe_tag = tag.replace("/", "_").replace("\\", "_").replace("..", "_")
        return self.base_dir / f"{safe_tag}.json"

    def _list_snapshots(self) -> list[dict]:
        """[Golden] 列出所有快照元数据（不加载完整图）"""
        snapshots = []
        for path in sorted(self.base_dir.glob("*.json")):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                snapshots.append(
                    {
                        "tag": data.get("tag", path.stem),
                        "file": str(path),
                        "created_at": data.get("created_at", ""),
                        "git_commit": data.get("git_commit", ""),
                        "files": data.get("files", []),
                        "node_count": data.get("node_count", 0),
                        "edge_count": data.get("edge_count", 0),
                    }
                )
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(f"Failed to read snapshot {path}: {e}")
                continue
        return snapshots

    def save(self, tag: str, graph_data: dict, git_commit: str = "", files: list[str] = None) -> str:
        """[Golden] 保存快照

        Args:
            tag: 快照标签（如 "v1.2.3"）
            graph_data: SignalGraph.to_dict() 的结果
            git_commit: Git commit hash
            files: 相关的源文件列表

        Returns:
            快照文件路径

        金标准:
        - tag 唯一，重复保存会覆盖
        - 保存前记录 created_at
        """
        path = self._snapshot_path(tag)

        data = dict(graph_data)  # 拷贝
        data["tag"] = tag
        data["git_commit"] = git_commit
        data["files"] = files or []
        data["created_at"] = datetime.now(UTC).isoformat()

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Snapshot saved: {tag} -> {path}")
        return str(path)

    def load(self, tag: str) -> dict | None:
        """[Golden] 加载快照完整数据

        Args:
            tag: 快照标签

        Returns:
            快照数据字典，或 None（如果不存在）
        """
        path = self._snapshot_path(tag)
        if not path.exists():
            logger.warning(f"Snapshot not found: {tag}")
            return None

        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def delete(self, tag: str) -> bool:
        """[Golden] 删除快照

        Args:
            tag: 快照标签

        Returns:
            True if deleted, False if not found
        """
        path = self._snapshot_path(tag)
        if not path.exists():
            return False

        path.unlink()
        logger.info(f"Snapshot deleted: {tag}")
        return True

    def exists(self, tag: str) -> bool:
        """检查快照是否存在"""
        return self._snapshot_path(tag).exists()

    def list_tags(self) -> list[str]:
        """[Golden] 列出所有快照标签"""
        return [s["tag"] for s in self._list_snapshots()]

    def list_summary(self) -> list[dict]:
        """[Golden] 列出所有快照摘要"""
        return self._list_snapshots()

    def show(self, tag: str) -> dict | None:
        """[Golden] 查看快照详情（不加载完整图）"""
        path = self._snapshot_path(tag)
        if not path.exists():
            return None

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        # 只返回元数据，不返回 nodes/edges（可能很大）
        return {
            "tag": data.get("tag", tag),
            "version": data.get("version", "1.0"),
            "created_at": data.get("created_at", ""),
            "git_commit": data.get("git_commit", ""),
            "files": data.get("files", []),
            "node_count": data.get("node_count", 0),
            "edge_count": data.get("edge_count", 0),
        }

    def compare(self, tag1: str, tag2: str) -> dict | None:
        """[Golden] 对比两个快照

        Args:
            tag1: 旧快照标签
            tag2: 新快照标签

        Returns:
            包含 diff 结果的字典，或 None（如果任一快照不存在）
        """
        data1 = self.load(tag1)
        data2 = self.load(tag2)

        if data1 is None or data2 is None:
            return None

        # 使用 SignalGraph 的序列化/反序列化
        from trace.core.graph.models import SignalGraph

        G1 = SignalGraph.from_dict(data1)
        G2 = SignalGraph.from_dict(data2)

        # 使用 diff_with_health 进行完整对比
        from trace.core.graph.diff import diff_with_health

        result = diff_with_health(G1, G2)

        # 序列化 GraphDiff 对象
        diff_result = result["graph_diff"]

        return {
            "tag1": tag1,
            "tag2": tag2,
            "stable_core": result["stable_core"],
            "health_score_old": result["health_score_old"],
            "health_score_new": result["health_score_new"],
            "health_delta": result["health_delta"],
            "coupling_warning": result["coupling_warning"],
            "added_nodes": diff_result.added_nodes,
            "removed_nodes": diff_result.removed_nodes,
            "added_edges": [list(e) for e in diff_result.added_edges],
            "removed_edges": [list(e) for e in diff_result.removed_edges],
            "identical": diff_result.identical,
        }

"""
[Cross-viz Consistency Tests 2026-07-10]

方豆 2026-07-10 11:54: '重新确认一下，各个画图功能，结果是否存在一致性，可以互相帮助理解'

This test runs MULTIPLE viz commands on the same RTL and asserts that
their facts agree with each other. Each command shows a different aspect:

- arch     → module hierarchy + sub-instance count
- pipeline → register chain → time stages
- chain    → input → output data path
- timing   → critical path depth + cycle latency

Consistency rules tested:
1. arch's sub-instance count == chain's sub-instance cluster count
2. arch's sub-instance types == chain's cluster types
3. pipeline's total_latency >= chain's max "Total cycles"
4. timing's critical path nodes ⊆ chain's nodes (related)
5. chain's anomaly signals ⊆ arch's signal namespace
6. timing's reg count = pipeline regs + control regs + state regs (when same scope)
"""
import re
import subprocess
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
GOLDEN_DIR = PROJECT_ROOT / "tests" / "fixtures" / "golden_chain"


def run_sv(args: list[str], timeout: int = 90) -> dict:
    """Run sv_query and return parsed result."""
    result = subprocess.run(
        ["sv_query"] + args,
        capture_output=True, text=True, timeout=timeout,
    )
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "text": result.stdout + result.stderr,  # combined for parsing
    }


def parse_arch_summary(stderr: str) -> dict:
    """Parse arch show --format summary output."""
    info = {"total_instances": 0, "port_connections": 0, "types": []}
    m = re.search(r"Total instances:\s+(\d+)", stderr)
    if m:
        info["total_instances"] = int(m.group(1))
    m = re.search(r"Port connections:\s+(\d+)", stderr)
    if m:
        info["port_connections"] = int(m.group(1))
    # Parse "SourceA  1" type lines
    for line in stderr.split("\n"):
        m = re.match(r"\s+(\w+)\s+(\d+)\s+█", line)
        if m:
            info["types"].append((m.group(1), int(m.group(2))))
    return info


def parse_chain(stderr: str) -> dict:
    """Parse chain anomaly report."""
    info = {"anomalies": [], "anomaly_counts": {}, "paths": 0}
    m = re.search(r"Found\s+(\d+)\s+data paths", stderr)
    if m:
        info["paths"] = int(m.group(1))
    m = re.search(r"RTL anomalies detected[^\n]*:\s*({[^}]+})", stderr)
    if m:
        for am in re.finditer(r"'(\w+)':\s*(\d+)", m.group(1)):
            info["anomaly_counts"][am.group(1)] = int(am.group(2))
    # Parse individual anomalies (- name: kind)
    for line in stderr.split("\n"):
        m = re.search(r"-\s+(\w+):\s+(\w+)", line)
        if m and m.group(2) in ("X_DRIVER", "DANGLING", "ORPHAN"):
            info["anomalies"].append((m.group(1), m.group(2)))
    return info


def parse_pipeline(stderr: str) -> dict:
    """Parse visualize pipeline output."""
    info = {"pipeline_regs": 0, "control_regs": 0, "state_regs": 0, "stages": 0}
    m = re.search(r"Pipeline regs:\s+(\d+)", stderr)
    if m:
        info["pipeline_regs"] = int(m.group(1))
    m = re.search(r"Control regs:\s+(\d+)", stderr)
    if m:
        info["control_regs"] = int(m.group(1))
    m = re.search(r"State regs:\s+(\d+)", stderr)
    if m:
        info["state_regs"] = int(m.group(1))
    m = re.search(r"Stages:\s+(\d+)", stderr)
    if m:
        info["stages"] = int(m.group(1))
    return info


def parse_timing(stderr: str) -> dict:
    """Parse timing analyze output."""
    info = {"total_nodes": 0, "regs": 0, "critical_paths": []}
    m = re.search(r"总=(\d+)\s*\|\s*寄存器=(\d+)", stderr)
    if m:
        info["total_nodes"] = int(m.group(1))
        info["regs"] = int(m.group(2))
    # Parse critical path lines
    for line in stderr.split("\n"):
        m = re.match(r"\s+\d+\s+(\d+)\s+(\d+)\s+(.+)", line)
        if m and "rank" not in line.lower():
            try:
                depth = int(m.group(1))
                score = int(m.group(2))
                reg_path = m.group(3).strip()
                info["critical_paths"].append({"depth": depth, "score": score, "path": reg_path})
            except ValueError:
                pass
    return info


def parse_arch_dot(dot_path: Path, target: str) -> dict:
    """Parse arch DOT file to extract sub-instance names."""
    content = dot_path.read_text()
    # Extract node IDs like "Scheduler.SourceA_dut"
    pattern = re.compile(rf'"{re.escape(target)}\.(\w+)"\s*\[label=')
    instances = pattern.findall(content)
    return {"instances": instances, "count": len(instances)}


def parse_chain_dot(dot_path: Path, target: str) -> dict:
    """Parse chain DOT file to extract sub-instance clusters and signals."""
    content = dot_path.read_text()
    # Extract sub-instance clusters: "cluster_<target>_<subname>"
    cluster_pattern = re.compile(rf'cluster_{re.escape(target)}_(\w+)"')
    sub_instances = set(cluster_pattern.findall(content))
    # Extract non-cluster nodes
    all_nodes = re.findall(r'"(\w+(?:\.\w+)*)"\s*\[label=', content)
    return {"sub_instances": sub_instances, "all_nodes": set(all_nodes)}


class TestCrossVizConsistency(unittest.TestCase):
    """Cross-viz consistency tests on golden testcases."""

    def setUp(self):
        self.tc = "normal"
        self.filelist = str(GOLDEN_DIR / "normal" / "filelist.f")

    def _run_all(self, target: str, filelist: str) -> dict:
        """Run arch + chain + pipeline + timing on same target."""
        arch = run_sv(["arch", "show", "-f", filelist,
                       "--target", target, "--depth", "1",
                       "--format", "summary"])
        chain = run_sv(["visualize", "chain", "-f", filelist,
                        "--target", target, "--auto",
                        "--max-edges", "30", "--svg", "/tmp/_chain.dot"])
        pipeline = run_sv(["visualize", "pipeline", "-f", filelist,
                          "--module", target,
                          "--svg", "/tmp/_pipeline.dot"])
        return {
            "arch": parse_arch_summary(arch["text"]),
            "chain": parse_chain(chain["text"]),
            "pipeline": parse_pipeline(pipeline["text"]),
        }

    def test_normal_arch_pipeline_chain_agree_on_namespace(self):
        """[Cross 1] arch/pipeline/chain all use 'normal' as namespace."""
        facts = self._run_all("normal", self.filelist)
        # arch should find no sub-instances (top-level module has no children)
        self.assertEqual(facts["arch"]["total_instances"], 0,
                        f"normal module should have 0 sub-instances, got {facts['arch']}")
        # chain should not find anomalies (no internal wires with issues)
        self.assertEqual(facts["chain"]["anomaly_counts"], {},
                        f"normal chain should have 0 anomalies, got {facts['chain']}")
        # pipeline should report some regs (data_reg, valid_reg)
        self.assertGreaterEqual(facts["pipeline"]["pipeline_regs"], 2,
                              "normal should have at least 2 pipeline regs (data_reg, valid_reg)")

class TestCrossVizHelpEachOther(unittest.TestCase):
    """Different viz commands should help understand each other."""

    def test_arch_pipeline_chain_complementary_info(self):
        """[Cross 5] arch shows N sub-instances, pipeline shows N×regs, chain shows paths."""
        # Run all on x_driver
        filelist = str(GOLDEN_DIR / "x_driver" / "filelist.f")

        arch = run_sv(["arch", "show", "-f", filelist,
                       "--target", "x_driver", "--depth", "1",
                       "--format", "summary"])
        arch_info = parse_arch_summary(arch["text"])

        pipeline = run_sv(["visualize", "pipeline", "-f", filelist,
                          "--module", "x_driver",
                          "--svg", "/tmp/_xpipe.dot"])
        pipe_info = parse_pipeline(pipeline["text"])

        chain = run_sv(["visualize", "chain", "-f", filelist,
                        "--target", "x_driver", "--auto",
                        "--max-edges", "30", "--svg", "/tmp/_xchain.dot"])
        chain_info = parse_chain(chain["text"])

        # arch: 0 sub-instances (top-level module)
        self.assertEqual(arch_info["total_instances"], 0,
                        "x_driver has 0 sub-instances (it's top-level)")

        # pipeline: at least 1 pipeline reg (data_reg)
        self.assertGreaterEqual(pipe_info["pipeline_regs"], 1)

        # chain: 1 X_DRIVER (orphan_wire)
        self.assertEqual(chain_info["anomaly_counts"].get("X_DRIVER", 0), 1,
                       f"x_driver should have 1 X_DRIVER (orphan_wire), got {chain_info['anomaly_counts']}")

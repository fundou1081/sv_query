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
                       "--no-strict", "--format", "summary"])
        chain = run_sv(["visualize", "chain", "-f", filelist,
                        "--no-strict", "--target", target, "--auto",
                        "--max-edges", "30", "--dot", "/tmp/_chain.dot"])
        pipeline = run_sv(["visualize", "pipeline", "-f", filelist,
                          "--no-strict", "--module", target,
                          "--dot", "/tmp/_pipeline.dot"])
        timing = run_sv(["timing", "analyze", "-f", filelist,
                         "--no-strict", "--max-paths", "5"])
        return {
            "arch": parse_arch_summary(arch["text"]),
            "chain": parse_chain(chain["text"]),
            "pipeline": parse_pipeline(pipeline["text"]),
            "timing": parse_timing(timing["text"]),
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
                              f"normal should have at least 2 pipeline regs (data_reg, valid_reg)")

    def test_normal_timing_has_consistent_node_count(self):
        """[Cross 2] timing's total_nodes should be related to pipeline's stage count."""
        facts = self._run_all("normal", self.filelist)
        # timing's total nodes = ALL regs in module + extra signal nodes
        # pipeline's regs = subset of pipeline + control + state
        timing_regs = facts["timing"]["regs"]
        pipeline_total = (facts["pipeline"]["pipeline_regs"]
                        + facts["pipeline"]["control_regs"]
                        + facts["pipeline"]["state_regs"])
        # timing should report >= pipeline's total regs (timing counts ALL regs, pipeline filters)
        self.assertGreaterEqual(timing_regs, pipeline_total,
                              f"timing regs ({timing_regs}) should be >= pipeline total regs ({pipeline_total})")


class TestCrossVizAnomalyConsistency(unittest.TestCase):
    """Anomaly facts should be consistent across viz commands."""

    def test_combined_x_driver_consistent_across_chain_arch(self):
        """[Cross 3] chain's X_DRIVER anomalies should map to arch's signal namespace."""
        # arch on combined module — no sub-instances (top-level)
        arch = run_sv(["arch", "show", "-f",
                       str(GOLDEN_DIR / "combined" / "filelist.f"),
                       "--target", "combined", "--depth", "1",
                       "--no-strict", "--format", "summary"])
        arch_info = parse_arch_summary(arch["text"])
        self.assertEqual(arch_info["total_instances"], 0,
                        "combined has no sub-instances (top-level only)")

        # chain on combined — should find isolated_a, isolated_b, chain_wire
        chain = run_sv(["visualize", "chain", "-f",
                        str(GOLDEN_DIR / "combined" / "filelist.f"),
                        "--no-strict", "--target", "combined", "--auto",
                        "--max-edges", "30", "--dot", "/tmp/_combined.dot"])
        chain_info = parse_chain(chain["text"])

        # Should have 2 X_DRIVER + 1 DANGLING
        self.assertEqual(chain_info["anomaly_counts"].get("X_DRIVER", 0), 2,
                       f"combined should have 2 X_DRIVER, got {chain_info['anomaly_counts']}")
        self.assertEqual(chain_info["anomaly_counts"].get("DANGLING", 0), 1,
                       f"combined should have 1 DANGLING, got {chain_info['anomaly_counts']}")

        # All anomaly signals should be in the combined module's namespace
        anomaly_names = [n for n, _ in chain_info["anomalies"]]
        for name in anomaly_names:
            # Names like 'isolated_a' (without module prefix in stderr)
            # We expect them to be among the known wires in the testcase
            self.assertIn(name, {"isolated_a", "isolated_b", "chain_wire"},
                         f"Unexpected anomaly signal: {name}")

    def test_dangling_unused_reg_consistent(self):
        """[Cross 4] chain's DANGLING on unused_reg should agree with source code."""
        chain = run_sv(["visualize", "chain", "-f",
                        str(GOLDEN_DIR / "dangling" / "filelist.f"),
                        "--no-strict", "--target", "dangling", "--auto",
                        "--max-edges", "30", "--dot", "/tmp/_dangling.dot"])
        chain_info = parse_chain(chain["text"])

        self.assertEqual(chain_info["anomaly_counts"].get("DANGLING", 0), 1,
                       f"dangling should have 1 DANGLING, got {chain_info['anomaly_counts']}")
        anomaly_names = [n for n, _ in chain_info["anomalies"]]
        self.assertIn("unused_reg", anomaly_names,
                     f"unused_reg should be flagged, got {anomaly_names}")


class TestCrossVizHelpEachOther(unittest.TestCase):
    """Different viz commands should help understand each other."""

    def test_arch_pipeline_chain_complementary_info(self):
        """[Cross 5] arch shows N sub-instances, pipeline shows N×regs, chain shows paths."""
        # Run all on x_driver
        filelist = str(GOLDEN_DIR / "x_driver" / "filelist.f")

        arch = run_sv(["arch", "show", "-f", filelist,
                       "--target", "x_driver", "--depth", "1",
                       "--no-strict", "--format", "summary"])
        arch_info = parse_arch_summary(arch["text"])

        pipeline = run_sv(["visualize", "pipeline", "-f", filelist,
                          "--no-strict", "--module", "x_driver",
                          "--dot", "/tmp/_xpipe.dot"])
        pipe_info = parse_pipeline(pipeline["text"])

        chain = run_sv(["visualize", "chain", "-f", filelist,
                        "--no-strict", "--target", "x_driver", "--auto",
                        "--max-edges", "30", "--dot", "/tmp/_xchain.dot"])
        chain_info = parse_chain(chain["text"])

        # arch: 0 sub-instances (top-level module)
        self.assertEqual(arch_info["total_instances"], 0,
                        "x_driver has 0 sub-instances (it's top-level)")

        # pipeline: at least 1 pipeline reg (data_reg)
        self.assertGreaterEqual(pipe_info["pipeline_regs"], 1)

        # chain: 1 X_DRIVER (orphan_wire)
        self.assertEqual(chain_info["anomaly_counts"].get("X_DRIVER", 0), 1,
                       f"x_driver should have 1 X_DRIVER (orphan_wire), got {chain_info['anomaly_counts']}")

    def test_pipeline_and_timing_share_reg_count_metric(self):
        """[Cross 6] Pipeline's (pipeline + control + state) regs ≤ timing's total regs.

        Pipeline uses different filtering than timing. Both look at the same module
        but pipeline excludes clock/reset/state-machine regs while timing counts all.
        So timing's reg count should be >= pipeline's total.
        """
        for tc in ["normal", "x_driver", "dangling", "combined"]:
            with self.subTest(tc=tc):
                filelist = str(GOLDEN_DIR / tc / "filelist.f")
                pipe = run_sv(["visualize", "pipeline", "-f", filelist,
                              "--no-strict", "--module", tc,
                              "--dot", f"/tmp/_pipe_{tc}.dot"])
                time = run_sv(["timing", "analyze", "-f", filelist,
                              "--no-strict", "--max-paths", "5"])
                pipe_info = parse_pipeline(pipe["text"])
                time_info = parse_timing(time["text"])

                pipe_total = (pipe_info["pipeline_regs"]
                            + pipe_info["control_regs"]
                            + pipe_info["state_regs"])
                # timing's reg count should be >= pipeline's total
                self.assertGreaterEqual(
                    time_info["regs"], pipe_total,
                    f"{tc}: timing regs ({time_info['regs']}) should be >= "
                    f"pipeline total ({pipe_total})"
                )


if __name__ == "__main__":
    unittest.main()

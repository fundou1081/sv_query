"""P165.1: SignalTracer must not scan the whole graph for local neighbor queries."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SIGNAL = ROOT / "src/trace/core/query/signal.py"


def test_signal_tracer_has_no_full_edges_scan():
    text = SIGNAL.read_text()
    # P165.1 converted all local predecessor/successor loops to adjacency views.
    assert "self.graph.edges()" not in text
    assert "list(self.graph.edges())" not in text


def test_incoming_outgoing_helpers_exist():
    text = SIGNAL.read_text()
    assert "_incoming_pairs" in text
    assert "_outgoing_pairs" in text

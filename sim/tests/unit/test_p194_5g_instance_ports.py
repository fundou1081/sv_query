"""P194.5g-adjacent — elaborated instance port metadata overrides weak maps."""
from __future__ import annotations

from types import SimpleNamespace

from sv_query.trace.core.connection_extractor import ConnectionExtractor


def test_instance_port_metadata_uses_elaborated_symbol():
    ports = [
        SimpleNamespace(name="i", direction="ArgumentDirection.In", type=SimpleNamespace(bitWidth=8)),
        SimpleNamespace(name="o", direction="ArgumentDirection.Out", type=SimpleNamespace(bitWidth=8)),
    ]
    inst = SimpleNamespace(_symbol=SimpleNamespace(
        portConnections=[SimpleNamespace(port=p) for p in ports]))
    got_ports, got_widths = ConnectionExtractor._instance_port_metadata(inst, {}, {})
    assert got_ports == {"i": "input", "o": "output"}
    assert got_widths == {"i": (7, 0), "o": (7, 0)}

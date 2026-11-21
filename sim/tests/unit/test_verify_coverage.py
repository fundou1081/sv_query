"""Hermetic coverage_complete state machine."""
import json

from sv_query.cli.core.semantic.verify import _coverage_complete


def test_unknown_check_is_not_complete():
    assert _coverage_complete([{"check": "connection", "status": "unknown"}]) is False
    assert _coverage_complete([{"check": "bit", "status": "pass"},
                               {"check": "connection", "status": "unknown"}]) is False


def test_truncated_check_is_not_complete():
    assert _coverage_complete([{"check": "bit", "status": "pass", "truncated": True}]) is False


def test_all_known_and_untruncated_is_complete():
    assert _coverage_complete([{"check": "bit", "status": "pass"},
                               {"check": "connection", "status": "fail"}]) is True


def test_consistency_command_wires_unknown_to_coverage(monkeypatch, capsys):
    from sv_query.cli.core.semantic import verify

    class Tracer:
        def get_graph(self):
            return object()

    monkeypatch.setattr(verify, "_build", lambda *a, **k: Tracer())
    monkeypatch.setattr(verify, "_check_connections", lambda *a, **k: {
        "check": "connection", "status": "unknown", "checked": 0,
        "skipped": 0, "violations": [],
    })
    verify.consistency_cmd(file=None, filelist=None, from_snapshot=None,
                            checks="connection", signal=None, max_nodes=200,
                            full=False, json_output=True, pretty=False,
                            log_level="WARNING")
    data = json.loads(capsys.readouterr().out)
    assert data["result"]["verified"] is False
    assert data["result"]["coverage_complete"] is False
    assert data["result"]["unknown_checks"] == ["connection"]

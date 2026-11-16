"""Hermetic coverage_complete state machine."""
from cli.core.semantic.verify import _coverage_complete


def test_unknown_check_is_not_complete():
    assert _coverage_complete([{"check": "connection", "status": "unknown"}]) is False
    assert _coverage_complete([{"check": "bit", "status": "pass"},
                               {"check": "connection", "status": "unknown"}]) is False


def test_truncated_check_is_not_complete():
    assert _coverage_complete([{"check": "bit", "status": "pass", "truncated": True}]) is False


def test_all_known_and_untruncated_is_complete():
    assert _coverage_complete([{"check": "bit", "status": "pass"},
                               {"check": "connection", "status": "fail"}]) is True

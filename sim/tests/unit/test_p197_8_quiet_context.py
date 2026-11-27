"""P197.8 — explicit quiet context and no argv mutation."""
from __future__ import annotations

import sys

from sv_query.trace.core.compiler import is_quiet, quiet_context


def test_quiet_context_is_scoped():
    assert is_quiet() is False
    with quiet_context():
        assert is_quiet() is True
    assert is_quiet() is False


def test_run_does_not_mutate_argv_and_filters_after_verb(monkeypatch):
    from sv_query.cli import main as cli_main

    captured = {}

    def fake(args=None):
        captured["args"] = list(args or [])
        captured["quiet"] = is_quiet()

    monkeypatch.setattr(cli_main, "app", fake)
    argv = ["sv_query", "drivers", "top.y", "--json", "--quiet", "--verbose"]
    monkeypatch.setattr(sys, "argv", list(argv))
    cli_main.run()
    assert sys.argv == argv
    assert captured["args"] == ["drivers", "top.y", "--json"]
    # --verbose wins over --json quiet default inside the invocation context.
    assert captured["quiet"] is False
    assert is_quiet() is False


def test_quiet_context_is_thread_local():
    import threading
    seen = {}
    def worker():
        with quiet_context():
            seen["inside"] = is_quiet()
        seen["after"] = is_quiet()
    t = threading.Thread(target=worker)
    t.start()
    t.join()
    assert seen == {"inside": True, "after": False}
    assert is_quiet() is False


def test_run_suppresses_logging_in_json_mode(monkeypatch, capsys):
    import logging

    from sv_query.cli import main as cli_main

    def fake(args=None):
        logging.getLogger("sv_query.test.quiet").warning("must be hidden")

    monkeypatch.setattr(cli_main, "app", fake)
    monkeypatch.setattr(sys, "argv", ["sv_query", "drivers", "x", "--json"])
    cli_main.run()
    assert capsys.readouterr().err == ""

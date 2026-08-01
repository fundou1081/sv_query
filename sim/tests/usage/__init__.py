"""Usage examples for external open-source projects.

These tests depend on external RTL projects (Ventus, OpenTitan,
PicoRV32, NaplesPU, etc.) that are NOT part of sv_query.
Run with:  PYTHONPATH=src python3 -m pytest sim/tests/usage/ -v
"""
# Also: test_deadlock_cli (needs OpenTitan), test_benchmark_pr5 (needs historical data)

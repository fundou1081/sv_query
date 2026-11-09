"""Parent bus fanin aggregates bit-slice drivers when no direct driver exists."""
import json
import os
import subprocess
import sys
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_FIXTURE = os.path.join(os.path.dirname(__file__), '..', 'fixtures',
                        'bus_bit_aggregation.sv')


class TestBusBitAggregation(unittest.TestCase):
    def test_parent_bus_drivers_include_bit_drivers(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(_ROOT, 'run_cli.py'), 'drivers',
             'top.bus', '-f', _FIXTURE, '--json'],
            capture_output=True, text=True, cwd=_ROOT)
        self.assertEqual(0, proc.returncode, proc.stderr[-1000:])
        sig = json.loads(proc.stdout)['result']['signals'][0]
        ids = {d['id'] for d in sig['drivers']}
        self.assertIn('top.a[0]', ids)
        self.assertIn('top.a[1]', ids)


if __name__ == '__main__':
    unittest.main()

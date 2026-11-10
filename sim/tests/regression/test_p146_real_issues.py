"""P146 real-use issue regressions."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_FIX = os.path.join(os.path.dirname(__file__), '..', 'fixtures')


def _run(*args, env=None):
    e = os.environ.copy()
    if env:
        e.update(env)
    return subprocess.run([sys.executable, os.path.join(_ROOT, 'run_cli.py'),
                           *args, '--json'], capture_output=True, text=True,
                          cwd=_ROOT, env=e)


class TestP146Issues(unittest.TestCase):
    def test_frontier_signal_probes_are_drivers_loads(self):
        p = _run('trace', 'frontier', 'top.w', '--direction', 'fanout',
                 '-f', os.path.join(_FIX, 'arch_pair.sv'))
        self.assertEqual(0, p.returncode, p.stderr[-1000:])
        rows = json.loads(p.stdout)['result']['frontier']
        self.assertTrue(rows)
        for row in rows:
            if row['reason'] != 'instance_boundary':
                self.assertTrue(all(not x.startswith('connections ')
                                    for x in row['next_probes']))

    def test_constant_has_no_loads(self):
        p = _run('loads', "1'b0", '-f', os.path.join(_FIX, 'golden_mini',
                                                     'calc_chain.sv'))
        self.assertEqual(0, p.returncode, p.stderr[-1000:])
        self.assertEqual(0, json.loads(p.stdout)['result']['signals'][0]['count'])

    def test_path_claim_reason_does_not_claim_reverse_checked(self):
        claim = json.dumps({"type": "path", "from": "top.y", "to": "top.x"})
        p = _run('verify', 'claim', '--claim', claim,
                 '-f', os.path.join(_FIX, 'arch_pair.sv'))
        self.assertEqual(0, p.returncode, p.stderr[-1000:])
        r = json.loads(p.stdout)['result']
        self.assertEqual('contradicted', r['status'])
        self.assertNotIn('reverse=True', r['reason'])

    def test_dataflow_unknown_has_json_error(self):
        p = _run('dataflow', 'analyze', 'no.such.sig', 'calc_chain.y',
                 '-f', os.path.join(_FIX, 'golden_mini', 'calc_chain.sv'))
        self.assertEqual(1, p.returncode)
        data = json.loads(p.stdout)
        self.assertFalse(data['ok'])
        self.assertIn('not found', data['error'])

    def test_controlflow_unknown_has_json_error(self):
        p = _run('controlflow', 'analyze', 'no.such.sig',
                 '-f', os.path.join(_FIX, 'golden_mini', 'calc_chain.sv'))
        self.assertEqual(1, p.returncode)
        data = json.loads(p.stdout)
        self.assertFalse(data['ok'])
        self.assertIn('signal not found', data['error'])

    def test_tb_join_bad_snapshot_has_json_error(self):
        with tempfile.TemporaryDirectory() as td:
            p = _run('trace', 'tb-join', 'tb_item.rcont',
                     '-f', os.path.join(_FIX, 'tb_join_tb.sv'),
                     '--from-snapshot', 'NO_SUCH',
                     env={'SVQ_SNAPSHOT_DIR': td})
        self.assertEqual(1, p.returncode)
        data = json.loads(p.stdout)
        self.assertFalse(data['ok'])
        self.assertIn('snapshot error', data['error'])

    def test_snapshot_compare_bad_tag_has_json_error(self):
        with tempfile.TemporaryDirectory() as td:
            p = _run('snapshot', 'compare', 'NO_SUCH', 'ALSO_NO',
                     env={'SVQ_SNAPSHOT_DIR': td})
        self.assertEqual(1, p.returncode)
        data = json.loads(p.stdout)
        self.assertFalse(data['ok'])
        self.assertIn('Snapshot not found', data['error'])

    def test_capabilities_contract_alias_and_coverage_fields(self):
        p = _run('capabilities')
        data = json.loads(p.stdout)
        c = data['json_contract']['commands']
        self.assertIn('drivers', c)
        self.assertIn('trace fanin', c)
        self.assertIn('complete', c['trace covergroups']['result_fields'])
        self.assertIn('reason', c['trace coverpoints']['result_fields'])


if __name__ == '__main__':
    unittest.main()

"""P144 schema ambiguities resolved in the registry/contract."""
import json
import os
import subprocess
import sys
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_FIXTURE = os.path.join(os.path.dirname(__file__), '..', 'fixtures',
                        'constraint_neighborhood.sv')
_COVER = os.path.join(os.path.dirname(__file__), '..', 'fixtures',
                      'golden_mini', 'coverage_demo.sv')


def _run(*args):
    return subprocess.run([sys.executable, os.path.join(_ROOT, 'run_cli.py'),
                           *args, '--json'], capture_output=True, text=True,
                          cwd=_ROOT)


class TestSchemaContractResolution(unittest.TestCase):
    def test_capabilities_exposes_envelope_and_write_scope(self):
        proc = _run('capabilities')
        self.assertEqual(0, proc.returncode, proc.stderr[-1000:])
        data = json.loads(proc.stdout)
        rows = {c['name']: c for c in data['commands']}
        self.assertEqual('direct', rows['search']['envelope'])
        self.assertEqual('cache', rows['snapshot save']['write_scope'])
        self.assertEqual('output', rows['filelist prune']['write_scope'])
        self.assertIn('envelope_policy', data['json_contract'])
        self.assertIn('write_scope_policy', data['json_contract'])

    def test_constraint_block_has_canonical_id_and_alias(self):
        proc = _run('trace', 'constraints', 'rnd_item.a', '-f', _FIXTURE)
        item = json.loads(proc.stdout)['result']['constraints'][0]
        self.assertEqual(item['id'], item['block'])

    def test_covergroups_empty_reason_is_machine_readable(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(_ROOT, 'run_cli.py'), 'trace',
             'covergroups', '--class', 'no_such_class', '-f', _COVER, '--json'],
            capture_output=True, text=True, cwd=_ROOT)
        self.assertEqual(0, proc.returncode, proc.stderr[-1000:])
        result = json.loads(proc.stdout)['result']
        self.assertTrue(result['complete'])
        self.assertEqual('no_match_in_filter', result['reason'])

    def test_coverpoints_empty_reason_is_machine_readable(self):
        proc = _run('trace', 'coverpoints', 'coverage_demo.other_q', '-f', _COVER)
        self.assertEqual(0, proc.returncode, proc.stderr[-1000:])
        result = json.loads(proc.stdout)['result']
        self.assertEqual('no_sampling_refs', result['reason'])
        self.assertTrue(result['complete'])

    def test_coverpoints_unknown_signal_is_explicit(self):
        proc = _run('trace', 'coverpoints', 'no.such.signal', '-f', _COVER)
        self.assertEqual(1, proc.returncode)
        data = json.loads(proc.stdout)
        self.assertFalse(data['ok'])
        self.assertIn('signal not found', data['error'])


if __name__ == '__main__':
    unittest.main()

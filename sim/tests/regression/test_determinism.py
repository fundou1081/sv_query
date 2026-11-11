"""P158.3: repeated graph builds of the same input must be identical."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_FIX = os.path.join(os.path.dirname(__file__), '..', 'fixtures', 'generate_forms',
                    'gen_forms.sv')
_FL = os.path.join(os.path.dirname(__file__), '..', 'fixtures', 'generate_forms',
                   'filelist.f')


def _run(args, env):
    return subprocess.run([sys.executable, os.path.join(_ROOT, 'run_cli.py'),
                           *args, '--json'], capture_output=True, text=True,
                          cwd=_ROOT, env=env)


def _canon_hash(path):
    d = json.load(open(path))
    payload = {
        "nodes": sorted((n["id"], json.dumps(n, sort_keys=True)) for n in d["nodes"]),
        "edges": sorted(json.dumps(e, sort_keys=True) for e in d["edges"]),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


class TestDeterminism(unittest.TestCase):
    def test_snapshot_build_is_deterministic(self):
        with tempfile.TemporaryDirectory() as td:
            env = os.environ.copy()
            env['SVQ_SNAPSHOT_DIR'] = td
            env['SVQ_CACHE_DIR'] = os.path.join(td, "cache")
            hashes = []
            for i in range(5):
                p = _run(['snapshot', 'save', _FIX, '--filelist', _FL,
                          '--tag', f'det{i}'], env)
                self.assertEqual(0, p.returncode, p.stderr[-1000:])
                hashes.append(_canon_hash(os.path.join(td, f'det{i}.json')))
            self.assertEqual(1, len(set(hashes)), hashes)


if __name__ == '__main__':
    unittest.main()

"""Missing-module warning must use real module declarations, not text/name only."""
import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.connection_extractor import ConnectionExtractor  # noqa: E402


class _Adapter:
    def __init__(self, sources):
        self._compiler = SimpleNamespace(sources=sources)


class TestModuleSourceKnown(unittest.TestCase):
    def test_commented_module_does_not_suppress(self):
        e = ConnectionExtractor(_Adapter({"foo.sv": "// module foo;\n"}))
        self.assertFalse(e._module_source_known("foo"))

    def test_real_module_declaration_suppresses(self):
        e = ConnectionExtractor(_Adapter({"foo.sv": "module foo; endmodule\n"}))
        self.assertTrue(e._module_source_known("foo"))


if __name__ == '__main__':
    unittest.main()

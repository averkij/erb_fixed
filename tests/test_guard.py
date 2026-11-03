import importlib
from pathlib import Path
import sys
import tempfile
import unittest

from erb.container_guard import module_names, resolve_spec


class ImportGuardTests(unittest.TestCase):
    def test_namespace_package_without_running_parent(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "pkg/ns").mkdir(parents=True)
            (root / "pkg/__init__.py").write_text("raise AssertionError('must not execute at build probe')\n")
            target = root / "pkg/ns/example.py"
            target.write_text("VALUE=1\n")
            sys.path.insert(0, d)
            try:
                importlib.invalidate_caches()
                self.assertEqual(Path(resolve_spec("pkg.ns.example").origin), target)
                self.assertNotIn("pkg", sys.modules)
            finally:
                sys.path.remove(d)

    def test_scripts_and_src_layout(self):
        self.assertEqual(module_names("src/pkg/__init__.py"), ["src.pkg", "pkg"])
        self.assertEqual(module_names("examples/tool.py"), ["examples.tool"])
        self.assertEqual(module_names("tool-with-hyphens.py"), ["tool-with-hyphens"])


if __name__ == "__main__":
    unittest.main()

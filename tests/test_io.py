import os
from pathlib import Path
import tempfile
import threading
import unittest

from erb.common import read_json, write_json


class DurableIOTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows file-sharing semantics required")
    def test_replace_survives_real_reader_lock(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "summary.json"
            write_json(path, {"recorded": 506})
            reader = path.open("rb")
            release = threading.Timer(0.25, reader.close)
            release.start()
            try:
                write_json(path, {"recorded": 507})
                self.assertEqual(read_json(path), {"recorded": 507})
                self.assertFalse(path.with_name("summary.json.tmp").exists())
            finally:
                release.join()
                reader.close()


if __name__ == "__main__":
    unittest.main()

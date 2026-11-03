import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from erb.artifacts import prepare_run, read_attempts
from erb.common import append_jsonl, manifest, run_lock
from erb.data import CATEGORIES, DATA_SHA, archive_members, clean_rows, extract_repository, safe_relative, select_tasks


def sample(**extra):
    return dict(repo_name="sample", file_name="/sample/pkg/a.py", prefix_code="a\r\n",
                middle_code="b", suffix_code=" c\n", context_code=[], fill_type=CATEGORIES[0], **extra)


class DataTests(unittest.TestCase):
    def test_clean_history_and_index_identity(self):
        rows = clean_rows([sample(generated_middle_code="old", es=99, is_pass=1, input="old", stderr="old")])
        self.assertEqual(rows[0]["task_id"], 0)
        self.assertEqual(rows[0]["dataset_sha256"], DATA_SHA)
        self.assertEqual(rows[0]["prefix_code"], "a\r\n")
        self.assertFalse({"generated_middle_code", "es", "is_pass", "input", "stderr"} & rows[0].keys())

    def test_paths(self):
        for path in ["../a", "/a", "a\\b", "C:/x", "a/../x", "a//b", "NUL.txt", "a.", "x:y"]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                safe_relative(path)

    def test_unsafe_archive_does_not_write(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "bad.zip"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("repos/sample/evaluate_repo.py", "pass")
                z.writestr("repos/sample/../../escape", "bad")
            with self.assertRaises(ValueError):
                extract_repository(path, "sample", Path(d) / "out")
            self.assertEqual(list((Path(d) / "out").iterdir()), [])

    def test_archive_links_and_collisions(self):
        for names in [["repos/a/A.py", "repos/a/a.py"], ["repos/a/link"]]:
            with tempfile.TemporaryDirectory() as d:
                with zipfile.ZipFile(Path(d) / "a.zip", "w") as z:
                    for name in names:
                        i = zipfile.ZipInfo(name)
                        if name.endswith("link"):
                            i.external_attr = 0o120777 << 16
                        z.writestr(i, "x")
                with zipfile.ZipFile(Path(d) / "a.zip") as z, self.assertRaises(ValueError):
                    list(archive_members(z))

    def test_cache_removal(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "a.zip"
            with zipfile.ZipFile(path, "w") as z:
                for n in ["evaluate_repo.py", "pkg/a.py", "pkg/a.pyc", "pkg/__pycache__/a.pyc", "build/lib/pkg/a.py"]:
                    z.writestr("repos/sample/" + n, "pass")
            out = Path(d) / "out"
            extract_repository(path, "sample", out)
            self.assertEqual(sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()),
                             ["build/lib/pkg/a.py", "evaluate_repo.py", "pkg/a.py"])

    def test_pilot(self):
        tasks = clean_rows([dict(sample(), fill_type=c) for c in CATEGORIES for _ in range(2)])
        self.assertEqual(len(select_tasks(tasks, "pilot")), 12)


class ArtifactTests(unittest.TestCase):
    def test_resume_empty_length_and_strict_corruption(self):
        with tempfile.TemporaryDirectory() as d, run_lock(d):
            m = manifest(dict(dataset_sha256=DATA_SHA, task_ids=[0], control="empty"), "generations")
            prepare_run(d, m, False)
            row = dict(task_id=0, dataset_sha256=DATA_SHA, fingerprint=m["fingerprint"], generated_middle="", finish_reason="length")
            path = Path(d) / "generations.jsonl"
            with path.open("w", encoding="utf-8") as f:
                append_jsonl(f, row)
            self.assertIn(0, prepare_run(d, m, True)[1])
            with self.assertRaises(ValueError):
                prepare_run(d, manifest(dict(m["config"], seed=1), "generations"), True)
            with path.open("a", encoding="utf-8") as f:
                f.write('{"task_id":')
            with self.assertRaises(ValueError):
                read_attempts(path, m)

    def test_missing_duplicate_unknown_hash(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "generations.jsonl"
            m = manifest(dict(dataset_sha256=DATA_SHA, task_ids=[0], control="gold"), "generations")
            with self.assertRaises(ValueError):
                read_attempts(path, m, True)
            row = dict(task_id=0, dataset_sha256=DATA_SHA, fingerprint=m["fingerprint"], generated_middle="x")
            for rows in [[row, row], [dict(row, task_id=1)], [dict(row, dataset_sha256="bad")]]:
                path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
                with self.assertRaises(ValueError):
                    read_attempts(path, m, True)


if __name__ == "__main__":
    unittest.main()

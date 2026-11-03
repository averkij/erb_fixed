from dataclasses import asdict
import importlib.abc
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import eval as evaluator
from erb.common import manifest, sha256, write_json
from erb.data import DATA_SHA, clean_rows
from erb.docker import Limits, create_args, daemon_info, InfrastructureError
from erb.metrics import edit_similarity, normalize, summarize
from test_data import sample


class EvaluationTests(unittest.TestCase):
    def test_no_model_dependencies(self):
        script = '''
import importlib.abc, sys
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self, fullname, path=None, target=None):
  if fullname.split('.')[0] in {'vllm','torch','transformers','numpy'}: raise AssertionError(fullname)
sys.meta_path.insert(0,Block())
import eval, prepare_images, controls
'''
        subprocess.run([sys.executable, "-c", script], check=True)

    def test_assembly_and_missing_control(self):
        tasks = clean_rows([sample()])
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            m = manifest(dict(dataset_sha256=DATA_SHA, task_ids=[0], control="gold"), "generations")
            write_json(root / "manifest.json", m)
            with self.assertRaises(ValueError):
                evaluator.validate_input(tasks, root)
            row = dict(task_id=0, dataset_sha256=DATA_SHA, fingerprint=m["fingerprint"], generated_middle="bad")
            (root / "generations.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                evaluator.validate_input(tasks, root)

    def test_normalization_and_fixed_backend(self):
        self.assertEqual(normalize(' \n"""doc"""\nx=1 # comment\n'), 'x=1 # comment')
        self.assertEqual(edit_similarity("a", "a"), 100)
        self.assertEqual(edit_similarity("", ""), 100)
        self.assertEqual(edit_similarity("a", ""), 0)
        self.assertEqual(edit_similarity("abcd", "abXY"), 50)
        self.assertEqual(edit_similarity('"""doc"""\na', "a"), 100)

    def test_denominators_and_missing_categories(self):
        tasks = clean_rows([sample()] * 5)
        rows = [dict(task_id=i, repo_name=t["repo_name"], fill_type=t["fill_type"], status=s, es=50)
                for i, (t, s) in enumerate(zip(tasks, ["pass", "test_fail", "timeout", "oom", "infrastructure_error"]))]
        s = summarize(rows, tasks)
        self.assertFalse(s["complete"])
        self.assertIsNone(s["micro_pass_at_1_percent"])
        self.assertEqual(s["observed_pass_fraction"], {"numerator": 1, "denominator": 4})
        self.assertEqual(s["es_denominator"], 5)
        self.assertEqual(len(s["categories"]), 6)
        self.assertEqual(sum(g["expected"] == 0 for g in s["categories"].values()), 5)
        rows[-1]["status"] = "test_fail"
        self.assertEqual(summarize(rows, tasks)["micro_pass_at_1_percent"], 20)

    def test_gold_gate(self):
        code = {"source_sha256": "fixed"}
        config = dict(dataset_sha256=DATA_SHA, control="gold", images={"r": "i"}, limits=asdict(Limits()), code=code, task_ids=list(range(1164)))
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "summary.json"
            m = manifest(config, "evaluation")
            write_json(path.parent / "manifest.json", m)
            results = path.parent / "results.jsonl"
            results.write_text("".join(json.dumps(dict(task_id=i, status="pass", dataset_sha256=DATA_SHA,
                               evaluation_fingerprint=m["fingerprint"])) + "\n" for i in range(1164)), encoding="utf-8")
            write_json(path, dict(complete=True, passes=1164, expected=1164, evaluation_config=config,
                                  evaluation_fingerprint=m["fingerprint"], results_sha256=sha256(results)))
            self.assertTrue(evaluator.gold_gate(path, {"r": "i"}, asdict(Limits()), code))
            with self.assertRaises(ValueError):
                evaluator.gold_gate(path, {"r": "other"}, asdict(Limits()), code)

    def test_isolation_flags_and_daemon(self):
        args = create_args("container", "sha256:1", Limits())
        self.assertIn("no-new-privileges:true", args)
        self.assertIn("10001:10001", args)
        self.assertEqual(args[args.index("--network") + 1], "none")
        self.assertFalse({"-v", "--mount", "--privileged", "--volume"} & set(args))
        with patch("erb.docker.output", return_value='{"OSType":"windows"}'), self.assertRaises(InfrastructureError):
            daemon_info()


if __name__ == "__main__":
    unittest.main()

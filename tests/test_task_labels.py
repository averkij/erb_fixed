import copy
import unittest

from erb.common import manifest
from erb.data import DATA_SHA, CATEGORIES
from task_labels import build_catalog, filtered_summary, select_labeled, validate_catalog


def evidence():
    result = dict(dataset_sha256=DATA_SHA, input_sha256={}, results={})
    for name in ["gold", "empty"]:
        result[name + "_manifest"] = manifest(dict(dataset_sha256=DATA_SHA, control=name), "evaluation")
        result["results"][name] = [dict(task_id=i, repo_name="repo", fill_type=CATEGORIES[0], status="pass") for i in range(1164)]
    result["results"]["gold"][0]["status"] = "test_fail"
    result["results"]["empty"][2]["status"] = "infrastructure_error"
    return result


class LabelTests(unittest.TestCase):
    def test_catalog_ids_overlap_and_no_false_unresolved_label(self):
        value = evidence()
        catalog = build_catalog(value, "source")
        tasks = validate_catalog(catalog)
        self.assertEqual(tasks[0]["labels"], ["test_fail", "empty_green"])
        self.assertEqual(tasks[2]["labels"], [])
        self.assertEqual(len(select_labeled(tasks, exclude=["test_fail", "empty_green"])), 1)
        self.assertEqual(len(select_labeled(tasks, only=["test_fail"])), 1)
        self.assertEqual(len(select_labeled(tasks, only=["test_fail", "empty_green"])), 1163)
        bad = copy.deepcopy(catalog["config"])
        bad["id_sets"]["test_fail"] = []
        with self.assertRaises(ValueError):
            validate_catalog(manifest(bad, "task_labels"))
        value["results"]["empty"][1]["task_id"] = 0
        with self.assertRaises(ValueError):
            build_catalog(value, "source")

    def test_filtered_denominators_missing_and_infrastructure(self):
        value = evidence()
        tasks = validate_catalog(build_catalog(value, "source"))
        rows = [dict(r, dataset_sha256=DATA_SHA, es=100) for r in value["results"]["gold"]]
        summary = filtered_summary(rows, tasks, exclude=["test_fail"])
        self.assertEqual((summary["passes"], summary["expected"]), (1163, 1163))
        self.assertEqual(summary["micro_pass_at_1_percent"], 100)
        self.assertIsNone(filtered_summary(rows[:-1], tasks)["micro_pass_at_1_percent"])
        rows[1]["status"] = "infrastructure_error"
        self.assertFalse(filtered_summary(rows, tasks)["complete"])
        with self.assertRaises(ValueError):
            filtered_summary(rows + [rows[0]], tasks)
        rows[0]["dataset_sha256"] = "other"
        with self.assertRaises(ValueError):
            filtered_summary(rows, tasks, exclude=["test_fail"])

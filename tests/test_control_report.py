"""Provenance checks prevent infrastructure retries from replacing test failures."""
import copy
import unittest

from report_controls import merge_infrastructure_retry


class RetryReportTests(unittest.TestCase):
    def test_only_matched_infrastructure_gaps_can_be_replaced(self):
        config = dict(control="empty", dataset_sha256="data", images={"repo": "image"},
                      limits={"timeout": 240}, image_manifest_sha256="images", code={"source_sha256": "code"})
        source = dict(config=config, fingerprint="original")
        retry = dict(config=dict(config, task_ids=[1], selection="infrastructure_retry", workers=1,
                                 retry_of_fingerprint="original", retry_of_results_sha256="rows"))
        original = [dict(task_id=0, status="test_fail"), dict(task_id=1, status="infrastructure_error")]
        attempts = [dict(task_id=1, status="test_fail")]
        merged = merge_infrastructure_retry(original, source, "rows", attempts, retry)
        self.assertEqual([r["status"] for r in merged], ["test_fail", "test_fail"])
        self.assertEqual(original[1]["status"], "infrastructure_error")
        for key, value in [("retry_of_results_sha256", "other"), ("limits", {"timeout": 1}), ("images", {}), ("code", {"source_sha256": "other"})]:
            bad = copy.deepcopy(retry)
            bad["config"][key] = value
            with self.assertRaises(ValueError):
                merge_infrastructure_retry(original, source, "rows", attempts, bad)
        with self.assertRaises(ValueError):
            merge_infrastructure_retry(original, source, "rows", [dict(task_id=0, status="pass")], retry)
        with self.assertRaises(ValueError):
            merge_infrastructure_retry(original, source, "rows", [], retry)

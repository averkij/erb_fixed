"""Explicit fresh attempts for infrastructure-only gaps in a measured control.

Original measurements are immutable. This does not retry candidate failures.
"""
import argparse
from pathlib import Path

from erb.common import append_jsonl, code_identity, manifest, run_lock, sha256, write_json
from erb.data import load_dataset
from erb.docker import Limits, daemon_info, evaluate_task
from erb.metrics import edit_similarity, summarize
from report_controls import control


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--control", choices=["gold", "empty"], required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()
    tasks = load_dataset(args.data)
    source, rows, summary = control(args.source, args.control, tasks)
    if summary["recorded"] != len(tasks):
        raise ValueError("Wait for the original full control to finish")
    config = source["config"]
    if code_identity()["source_sha256"] != config["code"]["source_sha256"]:
        raise ValueError("Retry requires the identical measured runtime source")
    ids = sorted(r["task_id"] for r in rows if r["status"] == "infrastructure_error")
    if not ids:
        raise ValueError("No infrastructure gaps to retry")
    selected = [t for t in tasks if t["task_id"] in ids]
    limits = Limits(**config["limits"]).validate()
    daemon = daemon_info()
    retry_config = dict(config, task_ids=ids, selection="infrastructure_retry", workers=1,
                        retry_of_fingerprint=source["fingerprint"],
                        retry_of_results_sha256=sha256(args.source / "results.jsonl"),
                        retry_tool_sha256=sha256(Path(__file__)), daemon=daemon)
    with run_lock(args.output_dir):
        if any(f.name != ".lock" for f in args.output_dir.iterdir()):
            raise ValueError("Retry output must be new/empty")
        run = manifest(retry_config, "evaluation")
        write_json(args.output_dir / "manifest.json", run, exclusive=True)
        results = []
        with (args.output_dir / "results.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
            for task in selected:
                middle = task["middle_code"] if args.control == "gold" else ""
                directory = args.output_dir / "tasks" / str(task["task_id"])
                result = evaluate_task(task, middle, config["images"][task["repo_name"]], limits, directory)
                result.update(dataset_sha256=config["dataset_sha256"], evaluation_fingerprint=run["fingerprint"],
                              es=edit_similarity(task["middle_code"], middle))
                write_json(directory / "result.json", result)
                append_jsonl(stream, result)
                results.append(result)
                print(f"Retry {task['task_id']}: {result['status']}", flush=True)
        result_summary = summarize(results, selected)
        result_summary.update(evaluation_config=retry_config, evaluation_fingerprint=run["fingerprint"],
                              results_sha256=sha256(args.output_dir / "results.jsonl"))
        write_json(args.output_dir / "summary.json", result_summary)
        return 0 if result_summary["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

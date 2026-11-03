"""Evaluate saved answers in fresh Linux containers. Python stdlib + Docker only."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
import sys

from erb.artifacts import read_attempts
from erb.common import append_jsonl, check_manifest, code_identity, digest, environment, manifest, now, read_json, read_jsonl, run_lock, sha256, write_json
from erb.data import DATA_SHA, load_dataset, select_tasks
from erb.docker import Limits, daemon_info, evaluate_task, output
from erb.metrics import ES_IMPLEMENTATION, edit_similarity, summarize


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, default=Path("data/exec_repo_bench.jsonl"))
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--images", type=Path, default=Path("images/manifest.json"))
    p.add_argument("--selection", choices=["full", "pilot"], default="full")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--cpus", type=float, default=2)
    p.add_argument("--memory", default="4g")
    p.add_argument("--pids", type=int, default=256)
    p.add_argument("--timeout", type=float, default=240)
    p.add_argument("--gold-summary", type=Path, help="Successful full gold summary.json; mandatory for full model evaluation")
    args = p.parse_args()
    if args.workers < 1:
        p.error("workers must be positive")
    return args


def validate_input(tasks, run_dir):
    m = check_manifest(read_json(run_dir / "manifest.json"), "generations")
    expected = [t["task_id"] for t in tasks]
    if m["config"].get("task_ids") != expected:
        raise ValueError("Selected task IDs differ from generation manifest (pilot/full mismatch)")
    answers = read_attempts(run_dir / "generations.jsonl", m, require_complete=True)
    control = m["config"].get("control")
    if control not in {None, "gold", "empty"}:
        raise ValueError("Unknown control type")
    if control:
        for task in tasks:
            expected_middle = task["middle_code"] if control == "gold" else ""
            if answers[task["task_id"]]["generated_middle"] != expected_middle:
                raise ValueError("Saved control differs from declared gold/empty")
    return m, answers


def gold_gate(summary_path, images, limits, code):
    if summary_path is None:
        raise ValueError("Full model evaluation requires --gold-summary with 1164/1164 passing gold tasks")
    summary = read_json(summary_path)
    config = summary.get("evaluation_config", {})
    if (summary.get("complete") is not True or summary.get("passes") != 1164 or summary.get("expected") != 1164
            or config.get("control") != "gold" or config.get("dataset_sha256") != DATA_SHA
            or config.get("images") != images or config.get("limits") != limits
            or config.get("code", {}).get("source_sha256") != code["source_sha256"]):
        raise ValueError("Gold must pass all 1164 tasks with identical data/images/limits/controller code")
    provenance = check_manifest(read_json(summary_path.parent / "manifest.json"), "evaluation")
    result_path = summary_path.parent / "results.jsonl"
    if (provenance["config"] != config or summary.get("evaluation_fingerprint") != provenance["fingerprint"]
            or summary.get("results_sha256") != sha256(result_path)
            or config.get("task_ids") != list(range(1164))):
        raise ValueError("Gold summary provenance or complete task selection differs")
    results = list(read_jsonl(result_path))
    if (len(results) != 1164 or {r.get("task_id") for r in results} != set(range(1164))
            or any(r.get("status") != "pass" or r.get("dataset_sha256") != DATA_SHA
                   or r.get("evaluation_fingerprint") != provenance["fingerprint"] for r in results)):
        raise ValueError("Gold results do not contain 1164 unique passing tasks")
    return sha256(summary_path)


def main():
    args = parse_args()
    limits = Limits(args.cpus, args.memory, args.pids, args.timeout).validate()
    tasks = select_tasks(load_dataset(args.data), args.selection)
    generation, answers = validate_input(tasks, args.run_dir)
    control = generation["config"].get("control")
    image_manifest = check_manifest(read_json(args.images), "images")
    if image_manifest["config"].get("dataset_sha256") != DATA_SHA:
        raise ValueError("Images were prepared for different data")
    available = image_manifest["config"]["images"]
    images = {}
    image_errors = {}
    for repo in sorted({t["repo_name"] for t in tasks}):
        item = available.get(repo, {})
        if item.get("status") != "ready" or not item.get("image_id", "").startswith("sha256:"):
            if control is None:
                raise ValueError(f"No prepared image for {repo}")
            images[repo] = None
            image_errors[repo] = item.get("error", f"No prepared image for {repo}")
        else:
            images[repo] = item["image_id"]
    daemon = daemon_info()
    for image in set(images.values()):
        if image is not None:
            output(["image", "inspect", image])
    code = code_identity()
    gold_sha = gold_gate(args.gold_summary, images, asdict(limits), code) if args.selection == "full" and not control else None
    config = dict(dataset_sha256=DATA_SHA, task_ids=[t["task_id"] for t in tasks], selection=args.selection,
                  control=control, generation_fingerprint=generation["fingerprint"],
                  generations_sha256=sha256(args.run_dir / "generations.jsonl"), images=images,
                  image_manifest_sha256=sha256(args.images), limits=asdict(limits), workers=args.workers,
                  image_preparation_errors=image_errors,
                  es_implementation=ES_IMPLEMENTATION, code=code, environment=environment(), daemon=daemon,
                  gold_summary_sha256=gold_sha)
    with run_lock(args.output_dir):
        if any(p.name != ".lock" for p in args.output_dir.iterdir()):
            raise ValueError("Evaluation output directory must be new/empty (no implicit resume/overwrite)")
        run = manifest(config, "evaluation")
        write_json(args.output_dir / "manifest.json", run, exclusive=True)
        artifacts = args.output_dir / "tasks"
        artifacts.mkdir()
        results = []

        def one(task):
            middle = answers[task["task_id"]]["generated_middle"]
            directory = artifacts / str(task["task_id"])
            if images[task["repo_name"]] is None:
                directory.mkdir()
                reason = image_errors[task["repo_name"]]
                (directory / "stdout.txt").write_bytes(b"")
                (directory / "stderr.txt").write_text(reason, encoding="utf-8")
                result = dict(task_id=task["task_id"], repo_name=task["repo_name"], fill_type=task["fill_type"],
                              status="infrastructure_error", infrastructure_error=reason, phase="image_preparation",
                              exit_code=None, oom_killed=False, timed_out=False, duration_seconds=0,
                              started_at=now(), completed_at=now(), image_id=None)
            else:
                result = evaluate_task(task, middle, images[task["repo_name"]], limits, directory)
            result.update(dataset_sha256=DATA_SHA, es=edit_similarity(task["middle_code"], middle),
                          evaluation_fingerprint=run["fingerprint"])
            return result

        with (args.output_dir / "results.jsonl").open("x", encoding="utf-8", newline="\n") as out:
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                futures = [pool.submit(one, t) for t in tasks]
                for future in as_completed(futures):
                    result = future.result()
                    append_jsonl(out, result)
                    results.append(result)
                    partial = summarize(results, tasks)
                    partial.update(evaluation_config=config, evaluation_fingerprint=run["fingerprint"],
                                   updated_at=now(), results_sha256=sha256(args.output_dir / "results.jsonl"))
                    write_json(args.output_dir / "summary.json", partial)
                    print(f"{len(results)}/{len(tasks)} task {result['task_id']}: {result['status']}", flush=True)
        summary = summarize(results, tasks)
        print(f"complete={summary['complete']} pass@1={summary['micro_pass_at_1_percent']} ({summary['passes']}/{summary['expected']})")
        return 0 if summary["complete"] else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, RuntimeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)

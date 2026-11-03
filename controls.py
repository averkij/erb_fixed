"""Explicit gold or empty saved answers, never an evaluator fallback."""
import argparse
from pathlib import Path

from erb.artifacts import prepare_run
from erb.common import append_jsonl, code_identity, manifest, now, run_lock
from erb.data import DATA_SHA, load_dataset, select_tasks


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, default=Path("data/exec_repo_bench.jsonl"))
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--control", required=True, choices=["gold", "empty"])
    p.add_argument("--selection", choices=["full", "pilot"], default="full")
    p.add_argument("--resume", action="store_true")
    args = p.parse_args()
    tasks = select_tasks(load_dataset(args.data), args.selection)
    config = dict(dataset_sha256=DATA_SHA, task_ids=[t["task_id"] for t in tasks], control=args.control,
                  selection=args.selection, code=code_identity())
    with run_lock(args.run_dir):
        m, completed = prepare_run(args.run_dir, manifest(config, "generations"), args.resume)
        with (args.run_dir / "generations.jsonl").open("a", encoding="utf-8", newline="\n") as f:
            for task in tasks:
                if task["task_id"] not in completed:
                    append_jsonl(f, dict(task_id=task["task_id"], dataset_sha256=DATA_SHA,
                                 fingerprint=m["fingerprint"], generated_middle=task["middle_code"] if args.control == "gold" else "",
                                 finish_reason="control", completed_at=now()))
    print(f"Saved {len(tasks)} explicit {args.control} attempts")


if __name__ == "__main__":
    main()

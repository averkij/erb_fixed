"""Frozen control labels and explicit post-hoc scoring; Python stdlib only."""
import argparse
import csv
import math
from pathlib import Path
import sys

from erb.common import check_manifest, manifest, read_json, read_jsonl, sha256, write_json
from erb.data import DATA_SHA
from erb.metrics import STATUSES, summarize

LABELS = {
    "test_fail": "Oracle/gold status is exactly test_fail in the frozen control audit; this is not the model/empty status or proof of a bad reference.",
    "empty_green": "Empty insertion status is pass in the frozen control audit.",
}


def build_catalog(evidence, evidence_sha256):
    if evidence["dataset_sha256"] != DATA_SHA:
        raise ValueError("Control evidence uses different data")
    controls = {}
    for name in ["gold", "empty"]:
        m = check_manifest(evidence[name + "_manifest"], "evaluation")
        if m["config"]["dataset_sha256"] != DATA_SHA or m["config"]["control"] != name:
            raise ValueError("Invalid control provenance")
        rows = evidence["results"][name]
        ids = [r["task_id"] for r in rows]
        if (any(type(i) is not int for i in ids) or len(ids) != 1164 or set(ids) != set(range(1164))
                or any(r["status"] not in STATUSES for r in rows)):
            raise ValueError("Control evidence must cover all 1164 unique IDs")
        controls[name] = {r["task_id"]: r for r in rows}
    tasks = []
    for i in range(1164):
        g, e = controls["gold"][i], controls["empty"][i]
        if any(g[k] != e[k] for k in ["repo_name", "fill_type"]):
            raise ValueError("Control task metadata differs")
        labels = []
        if g["status"] == "test_fail":
            labels.append("test_fail")
        if e["status"] == "pass":
            labels.append("empty_green")
        tasks.append(dict(task_id=i, repo_name=g["repo_name"], fill_type=g["fill_type"], labels=labels,
                          oracle_status=g["status"], empty_status=e["status"]))
    config = dict(dataset_sha256=DATA_SHA, task_id_definition="zero-based row index in the complete SHA256-pinned dataset",
                  label_definitions=LABELS, tasks=tasks,
                  id_sets={label: [t["task_id"] for t in tasks if label in t["labels"]] for label in LABELS},
                  source=dict(evidence_sha256=evidence_sha256, input_sha256=evidence["input_sha256"],
                              gold_fingerprint=evidence["gold_manifest"]["fingerprint"],
                              empty_fingerprint=evidence["empty_manifest"]["fingerprint"],
                              infrastructure_retries={k: v["results_sha256"] for k, v in evidence.get("infrastructure_retries", {}).items()}))
    return manifest(config, "task_labels")


def validate_catalog(catalog):
    config = check_manifest(catalog, "task_labels")["config"]
    tasks = config["tasks"]
    ids = [t["task_id"] for t in tasks]
    if (config["dataset_sha256"] != DATA_SHA or config["label_definitions"] != LABELS
            or any(type(i) is not int for i in ids) or ids != list(range(1164))):
        raise ValueError("Invalid label catalog data, IDs or definitions")
    for t in tasks:
        expected = (["test_fail"] if t["oracle_status"] == "test_fail" else []) + (["empty_green"] if t["empty_status"] == "pass" else [])
        if t["oracle_status"] not in STATUSES or t["empty_status"] not in STATUSES or t["labels"] != expected:
            raise ValueError("Labels differ from frozen control statuses")
    if config["id_sets"] != {label: [t["task_id"] for t in tasks if label in t["labels"]] for label in LABELS}:
        raise ValueError("Label ID sets differ from task rows")
    return tasks


def select_labeled(tasks, exclude=(), only=()):
    if (set(exclude) | set(only)) - LABELS.keys():
        raise ValueError("Unknown label")
    return [t for t in tasks if (not only or set(t["labels"]) & set(only))
            and not set(t["labels"]) & set(exclude)]


def filtered_summary(rows, tasks, exclude=(), only=()):
    known = {t["task_id"]: t for t in tasks}
    seen = set()
    for row in rows:
        i = row["task_id"]
        if type(i) is not int or i not in known or i in seen or row["status"] not in STATUSES:
            raise ValueError("Unknown/duplicate result ID or status")
        if (row["dataset_sha256"] != DATA_SHA or any(row[k] != known[i][k] for k in ["repo_name", "fill_type"])
                or type(row.get("es")) not in (int, float) or not math.isfinite(row["es"]) or not 0 <= row["es"] <= 100):
            raise ValueError("Result data/metadata/ES differs or is invalid")
        seen.add(i)
    selected = select_labeled(tasks, exclude, only)
    ids = {t["task_id"] for t in selected}
    summary = summarize([r for r in rows if r["task_id"] in ids], selected)
    summary.update(selection=dict(exclude_labels=sorted(set(exclude)), only_labels_any=sorted(set(only)),
                                  selected_ids=sorted(ids), excluded_ids=sorted(known.keys() - ids),
                                  source_task_count=len(tasks)))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="Save all IDs, labels and exact label ID sets from frozen evidence")
    export.add_argument("--evidence", type=Path, default=Path("control_report/evidence.json"))
    export.add_argument("--output-dir", type=Path, default=Path("control_report"))
    score = commands.add_parser("score", help="Explicit analytical rescore; never changes official evaluation artifacts")
    score.add_argument("--labels", type=Path, default=Path("control_report/task_labels.json"))
    score.add_argument("--results", type=Path, required=True, help="Measured results.jsonl; adjacent manifest.json is required")
    score.add_argument("--exclude-label", choices=LABELS, action="append", default=[])
    score.add_argument("--only-label", choices=LABELS, action="append", default=[])
    score.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "export":
        catalog = build_catalog(read_json(args.evidence), sha256(args.evidence))
        tasks = validate_catalog(catalog)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        write_json(args.output_dir / "task_labels.json", catalog)
        with (args.output_dir / "task_labels.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            fields = ["task_id", "dataset_sha256", "repo_name", "fill_type", "labels", "test_fail", "empty_green", "oracle_status", "empty_status"]
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for task in tasks:
                writer.writerow(dict(task, dataset_sha256=DATA_SHA, labels=";".join(task["labels"]),
                                     **{label: int(label in task["labels"]) for label in LABELS}))
        print({label: len(ids) for label, ids in catalog["config"]["id_sets"].items()})
        return 0
    catalog = read_json(args.labels)
    tasks = validate_catalog(catalog)
    m = check_manifest(read_json(args.results.parent / "manifest.json"), "evaluation")
    if m["config"]["dataset_sha256"] != DATA_SHA:
        raise ValueError("Evaluation data differs from labels")
    rows = list(read_jsonl(args.results))
    if any(r.get("evaluation_fingerprint") != m["fingerprint"] or r.get("task_id") not in m["config"]["task_ids"] for r in rows):
        raise ValueError("Results differ from evaluation manifest")
    summary = filtered_summary(rows, tasks, args.exclude_label, args.only_label)
    result = manifest(dict(analysis="explicit post-hoc subset; does not satisfy or override the full gold gate",
                           dataset_sha256=DATA_SHA, labels_sha256=sha256(args.labels), labels_fingerprint=catalog["fingerprint"],
                           results_sha256=sha256(args.results), evaluation_fingerprint=m["fingerprint"],
                           scorer_sha256=sha256(Path(__file__)), summary=summary), "filtered_score")
    if args.output.resolve() in {args.labels.resolve(), args.results.resolve(), (args.results.parent / "manifest.json").resolve(), (args.results.parent / "summary.json").resolve()}:
        raise ValueError("Output must not overwrite labels or measured evaluation artifacts")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, result)
    print(f"Selected {summary['expected']}; pass {summary['passes']}; pass@1={summary['micro_pass_at_1_percent']}; complete={summary['complete']}")
    return 0 if summary["complete"] else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(2)

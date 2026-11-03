"""One task ID, one durable attempt, bound to a complete run fingerprint."""
from pathlib import Path

from .common import check_manifest, read_json, read_jsonl, write_json
from .data import DATA_SHA


def read_attempts(path, run_manifest, require_complete=False):
    check_manifest(run_manifest, "generations")
    config = run_manifest["config"]
    if config.get("dataset_sha256") != DATA_SHA:
        raise ValueError("Generation dataset hash differs from pinned data")
    expected = config["task_ids"]
    if (not isinstance(expected, list) or not expected
            or any(type(i) is not int or i < 0 for i in expected) or len(set(expected)) != len(expected)):
        raise ValueError("Invalid manifest task IDs")
    results = {}
    if Path(path).exists():
        for row in read_jsonl(path):
            i = row.get("task_id")
            if type(i) is not int or i not in expected or i in results:
                raise ValueError(f"Duplicate or unknown generation ID: {i}")
            if (row.get("dataset_sha256") != DATA_SHA
                    or row.get("fingerprint") != run_manifest["fingerprint"]
                    or not isinstance(row.get("generated_middle"), str)):
                raise ValueError(f"Invalid generation record: {i}")
            if config.get("control") is None:
                if (not isinstance(row.get("prompt"), str)
                        or not isinstance(row.get("prompt_token_ids"), list)
                        or any(type(t) is not int or t < 0 for t in row["prompt_token_ids"])
                        or row.get("finish_reason") not in {"stop", "length"}
                        or not isinstance(row.get("usage"), dict)):
                    raise ValueError(f"Incomplete generation metadata: {i}")
            results[i] = row
    if require_complete and set(results) != set(expected):
        raise ValueError(f"Incomplete generations: got {len(results)}/{len(expected)}; missing {sorted(set(expected)-set(results))[:20]}")
    return results


def prepare_run(directory, wanted, resume):
    directory = Path(directory)
    manifest_path = directory / "manifest.json"
    answers = directory / "generations.jsonl"
    if manifest_path.exists():
        if not resume:
            raise ValueError("Run exists; use --resume with identical settings or a new directory")
        existing = check_manifest(read_json(manifest_path), "generations")
        if existing["fingerprint"] != wanted["fingerprint"]:
            raise ValueError("Resume fingerprint mismatch (data/code/model/settings/environment)")
        return existing, read_attempts(answers, existing)
    if resume or answers.exists() or any(p.name != ".lock" for p in directory.iterdir()):
        raise ValueError("New run must be empty; resume requires manifest.json")
    write_json(manifest_path, wanted, exclusive=True)
    return wanted, {}

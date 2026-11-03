"""Immutable entry point outside /repo; runs upstream evaluate_repo.py unchanged."""
import hashlib
import json
from pathlib import Path
import runpy
import sys
import traceback

from container_guard import OriginGuard


def main():
    detail = {"exit_code": 70, "infrastructure_error": None, "imports": []}
    guard = None
    try:
        task = json.loads(Path("/opt/erb/task.json").read_text())
        target = Path(task["target"])
        if not target.resolve().is_relative_to(Path("/repo")):
            raise ValueError("Target outside /repo")
        if hashlib.sha256(target.read_bytes()).hexdigest() != task["sha256"]:
            raise ValueError("Candidate content hash differs")
        provenance = json.loads(Path("/opt/erb/imports.json").read_text())
        guard = OriginGuard(provenance["modules"])
        sys.meta_path.insert(0, guard)
    except BaseException as e:
        detail["infrastructure_error"] = str(e)
        traceback.print_exc()
    else:
        try:
            sys.argv = ["/repo/evaluate_repo.py"]
            sys.path.insert(0, "/repo")
            runpy.run_path("/repo/evaluate_repo.py", run_name="__main__")
            detail["exit_code"] = 0
        except SystemExit as e:
            detail["exit_code"] = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        except BaseException:
            detail["exit_code"] = 1
            traceback.print_exc()
        if guard.errors:
            detail["infrastructure_error"] = "; ".join(guard.errors)
            detail["exit_code"] = 70
        detail["imports"] = guard.observed
        detail["target_import_observed"] = any(x["origin"] == str(target) for x in guard.observed)
    Path("/tmp/erb-result.json").write_text(json.dumps(detail), encoding="utf-8")
    return detail["exit_code"]


if __name__ == "__main__":
    sys.exit(main())

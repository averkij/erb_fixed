"""Pinned, clean task data and defensive archive handling."""
from collections import Counter
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import zipfile

from .common import ROOT, read_json, read_jsonl, sha256

LOCK = read_json(ROOT / "data.lock.json")
DATA_SHA = LOCK["files"]["exec_repo_bench.jsonl"]["sha256"]
CATEGORIES = (
    "Random Span Completion", "Random Single-line Completion", "Random Multi-line Completion",
    "grammar-based: expression", "grammar-based: statement", "grammar-based: block",
)
FIELDS = ("repo_name", "file_name", "prefix_code", "middle_code", "suffix_code", "context_code", "fill_type")


def safe_relative(name):
    if not isinstance(name, str) or not name or "\\" in name or "\x00" in name:
        raise ValueError(f"Unsafe path: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or any(x in {"", ".", ".."} for x in name.split("/")):
        raise ValueError(f"Unsafe path: {name!r}")
    for part in path.parts:
        if (re.search(r'[<>:"|?*\x00-\x1f]', part) or part.endswith((".", " "))
                or part.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}):
            raise ValueError(f"Nonportable path: {name!r}")
    return path


def task_path(name, repo):
    # The pinned release uses one leading slash as a repository-relative marker.
    path = safe_relative(name[1:] if name.startswith("/") else name)
    if path.parts[0] != repo or len(path.parts) < 2:
        raise ValueError(f"Path outside task repository: {name!r}")
    return path


def verify_file(path, name):
    expected = LOCK["files"][name]
    if Path(path).stat().st_size != expected["bytes"] or sha256(path) != expected["sha256"]:
        raise ValueError(f"Pinned size/SHA256 mismatch: {path}")


def clean_rows(rows):
    tasks = []
    for i, row in enumerate(rows):
        if any(k not in row for k in FIELDS):
            raise ValueError(f"Missing task fields at row {i}")
        obj = {k: row[k] for k in FIELDS}
        if any(not isinstance(obj[k], str) for k in FIELDS if k != "context_code"):
            raise ValueError(f"Non-string task field at row {i}")
        repo = obj["repo_name"]
        if safe_relative(repo).parts != (repo,) or obj["fill_type"] not in CATEGORIES:
            raise ValueError(f"Invalid repository/category at row {i}")
        task_path(obj["file_name"], repo)
        context = obj["context_code"]
        if not isinstance(context, list):
            raise ValueError(f"Invalid context at row {i}")
        names = set()
        for item in context:
            if not isinstance(item, list) or len(item) != 2 or not all(isinstance(s, str) for s in item):
                raise ValueError(f"Invalid context entry at row {i}")
            name = str(task_path(item[0], repo))
            if name in names:
                raise ValueError(f"Duplicate context path at row {i}: {name}")
            names.add(name)
        obj.update(task_id=i, dataset_sha256=DATA_SHA)
        tasks.append(obj)
    return tasks


def load_dataset(path):
    verify_file(path, "exec_repo_bench.jsonl")
    tasks = clean_rows(read_jsonl(path))
    counts = Counter(t["fill_type"] for t in tasks)
    if (len(tasks) != LOCK["rows"] or set(counts) != set(CATEGORIES)
            or len({t["repo_name"] for t in tasks}) != LOCK["repositories"]):
        raise ValueError("Unexpected task/category/repository counts")
    return tasks


def select_tasks(tasks, selection="full"):
    if selection == "full":
        return list(tasks)
    if selection != "pilot":
        raise ValueError("selection must be full or pilot")
    chosen = []
    for category in CATEGORIES:
        candidates = [t for t in tasks if t["fill_type"] == category]
        if len(candidates) < 2:
            raise ValueError(f"Insufficient pilot tasks: {category}")
        first = candidates[0]
        second = next((t for t in candidates[1:] if t["repo_name"] != first["repo_name"]), candidates[1])
        chosen.extend((first, second))
    return sorted(chosen, key=lambda t: t["task_id"])


def archive_members(archive):
    seen = {}
    for info in archive.infolist():
        name = info.filename.rstrip("/")
        path = safe_relative(name)
        mode = info.external_attr >> 16
        if stat.S_IFMT(mode) not in {0, stat.S_IFREG, stat.S_IFDIR}:
            raise ValueError(f"Archive link/special file: {name}")
        if path.parts[0] != "repos" or info.flag_bits & 1:
            raise ValueError(f"Unexpected/encrypted archive member: {name}")
        key = name.casefold()
        if key in seen:
            raise ValueError(f"Archive duplicate/case collision: {name}")
        seen[key] = name
        yield info, path


def extract_repository(archive_path, repo, destination):
    """New empty destination only. Caches/build artifacts cannot shadow edited source."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    if any(destination.iterdir()):
        raise ValueError(f"Extraction destination must be empty: {destination}")
    found = False
    with zipfile.ZipFile(archive_path) as archive:
        members = list(archive_members(archive))  # validate entire archive before writing
        for info, path in members:
            if len(path.parts) < 3 or path.parts[1] != repo:
                continue
            rel = path.parts[2:]
            if "__pycache__" in rel or rel[-1].endswith((".pyc", ".pyo")):
                continue
            dest = destination.joinpath(*rel)
            if info.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as src, dest.open("xb") as out:
                    shutil.copyfileobj(src, out)
                found = True
    if not found or not (destination / "evaluate_repo.py").is_file():
        raise ValueError(f"Repository/evaluate_repo.py missing: {repo}")

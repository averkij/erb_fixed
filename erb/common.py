"""Strict artifact IO shared by generation and evaluation (stdlib only)."""
import contextlib
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 1


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def loads(text):
    return json.loads(text, object_pairs_hook=_unique,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))


def read_json(path):
    return loads(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path):
    """Blank/truncated lines are errors, including a last record without LF."""
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        for line_no, line in enumerate(f, 1):
            try:
                if not line.endswith("\n") or not line.strip():
                    raise ValueError("blank or unterminated record")
                value = loads(line)
                if not isinstance(value, dict):
                    raise ValueError("record must be an object")
                yield value
            except (ValueError, TypeError) as e:
                raise ValueError(f"{path}:{line_no}: {e}") from e


def write_json(path, value, exclusive=False):
    path = Path(path)
    if exclusive:
        with path.open("x", encoding="utf-8", newline="\n") as f:
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
    else:
        temp = path.with_name(path.name + ".tmp")
        with temp.open("w", encoding="utf-8", newline="\n") as f:
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)


def append_jsonl(f, value):
    f.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n")
    f.flush()
    os.fsync(f.fileno())


@contextlib.contextmanager
def run_lock(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / ".lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as e:
        raise ValueError(f"Run is locked: {lock}; remove only after confirming no writer") from e
    try:
        os.write(fd, f"pid={os.getpid()} time={now()}\n".encode())
        os.close(fd)
        yield
    finally:
        lock.unlink()


def code_identity():
    files = sorted([*ROOT.glob("*.py"), *(ROOT / "erb").rglob("*.py"), *(ROOT / "tests").rglob("*.py")])
    files += [ROOT / "data.lock.json"]
    source_hash = digest({p.relative_to(ROOT).as_posix(): sha256(p) for p in files})
    try:
        commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                                         stderr=subprocess.DEVNULL, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    return {"commit": commit, "source_sha256": source_hash}


def environment():
    return {"python": sys.version, "platform": platform.platform()}


def manifest(config, kind):
    return {"schema_version": SCHEMA, "kind": kind, "created_at": now(),
            "fingerprint": digest(config), "config": config}


def check_manifest(value, kind=None):
    if (value.get("schema_version") != SCHEMA
            or value.get("fingerprint") != digest(value.get("config"))
            or (kind is not None and value.get("kind") != kind)):
        raise ValueError("Invalid manifest schema, kind or fingerprint")
    return value

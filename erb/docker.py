"""Docker CLI transport shared by Windows/Linux. No shell, host bind or socket mount."""
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import subprocess
import tempfile
import time
import uuid

from .common import now, read_json, sha256
from .data import task_path


class InfrastructureError(RuntimeError):
    pass


def command(args, timeout=60, check=True, **kwargs):
    try:
        result = subprocess.run(["docker", *map(str, args)], timeout=timeout, **kwargs)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise InfrastructureError(f"Docker command unavailable/timed out: {args[0]}: {e}") from e
    if check and result.returncode:
        error = getattr(result, "stderr", b"") or b""
        if isinstance(error, bytes):
            error = error.decode("utf-8", errors="replace")
        raise InfrastructureError(f"docker {args[0]} failed ({result.returncode}): {error[-4000:]}")
    return result


def output(args, timeout=60):
    return command(args, timeout=timeout, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode("utf-8").strip()


def daemon_info():
    info = json.loads(output(["info", "--format", "{{json .}}"], timeout=20))
    if info.get("OSType") != "linux":
        raise InfrastructureError("Docker must use Linux containers (Docker Desktop on Windows)")
    return {k: info.get(k) for k in ["OSType", "Architecture", "ServerVersion", "KernelVersion", "Name"]}


@dataclass(frozen=True)
class Limits:
    cpus: float = 2
    memory: str = "4g"
    pids: int = 256
    timeout: float = 240

    def validate(self):
        import re
        if self.cpus <= 0 or self.pids < 1 or self.timeout <= 0 or not re.fullmatch(r"[1-9][0-9]*[bkmgBKMG]?", self.memory):
            raise ValueError("Invalid CPU/memory/PID/timeout limit")
        return self


def create_args(name, image, limits):
    limits.validate()
    return ["create", "--name", name, "--network", "none", "--user", "10001:10001",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", "--init",
            "--cpus", str(limits.cpus), "--memory", limits.memory, "--memory-swap", limits.memory,
            "--pids-limit", str(limits.pids), "--workdir", "/repo", "--env", "PYTHONDONTWRITEBYTECODE=1",
            "--env", "PYTHONPATH=/opt/erb:/repo", "--env", "HOME=/tmp", image,
            "python", "/opt/erb/runner.py"]


def evaluate_task(task, middle, image, limits, artifact_dir):
    """A new writable *container layer* per task; host receives diagnostics only."""
    artifact_dir = Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=False)
    name = "erb-" + uuid.uuid4().hex
    started = time.monotonic()
    row = {"task_id": task["task_id"], "repo_name": task["repo_name"], "fill_type": task["fill_type"],
           "started_at": now(), "status": "infrastructure_error", "exit_code": None,
           "oom_killed": False, "timed_out": False, "container": name, "image_id": image}
    created = False
    try:
        with tempfile.TemporaryDirectory(prefix="erb candidate ") as directory:
            root = Path(directory)
            candidate = root / "candidate.py"
            # write_bytes prevents Windows text newline conversion.
            candidate.write_bytes((task["prefix_code"] + middle + task["suffix_code"]).encode("utf-8"))
            rel = task_path(task["file_name"], task["repo_name"])
            target = "/repo/" + "/".join(rel.parts[1:])
            row["candidate_sha256"] = sha256(candidate)
            output(create_args(name, image, limits))
            created = True
            output(["cp", candidate, f"{name}:{target}"])
            meta = root / "task.json"
            meta.write_text(json.dumps({"target": target, "sha256": row["candidate_sha256"]}), encoding="utf-8")
            output(["cp", meta, f"{name}:/opt/erb/task.json"])
            output(["start", name])
            # The bound covers candidate execution, including spawned children.
            try:
                output(["wait", name], timeout=limits.timeout)
            except InfrastructureError as e:
                if isinstance(e.__cause__, subprocess.TimeoutExpired):
                    row["timed_out"] = True
                    output(["kill", name], timeout=20)
                    output(["wait", name], timeout=20)
                else:
                    raise
            state = json.loads(output(["inspect", "--format", "{{json .State}}", name]))
            row.update(exit_code=state["ExitCode"], oom_killed=bool(state["OOMKilled"]), state=state)
            if state.get("Running") or state.get("Error"):
                raise InfrastructureError(f"Invalid container state: {state}")
            # Docker preserves separate stdout/stderr streams without a TTY.
            with (artifact_dir / "stdout.txt").open("wb") as stdout, (artifact_dir / "stderr.txt").open("wb") as stderr:
                command(["logs", name], stdout=stdout, stderr=stderr)
            diagnostics = root / "result.json"
            copied = command(["cp", f"{name}:/tmp/erb-result.json", diagnostics], check=False,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            detail = read_json(diagnostics) if copied.returncode == 0 else None
            row["runner"] = detail
            if row["oom_killed"]:
                row["status"] = "oom"
            elif row["timed_out"]:
                row["status"] = "timeout"
            elif detail is None or detail.get("infrastructure_error"):
                raise InfrastructureError("Runner missing or reported infrastructure error")
            elif detail.get("exit_code") != state["ExitCode"]:
                raise InfrastructureError("Runner/container exit codes differ")
            else:
                row["status"] = "pass" if state["ExitCode"] == 0 else "test_fail"
    except (InfrastructureError, OSError, ValueError, KeyError, TypeError) as e:
        row["status"] = "infrastructure_error"
        row["infrastructure_error"] = str(e)
    finally:
        if created:
            try:
                cleanup = command(["rm", "--force", name], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if cleanup.returncode:
                    raise InfrastructureError(cleanup.stderr.decode("utf-8", errors="replace"))
            except InfrastructureError as e:
                row["status"] = "infrastructure_error"
                row["cleanup_error"] = str(e)
        row["duration_seconds"] = time.monotonic() - started
        row["completed_at"] = now()
        # Keep diagnostics even if creation/start failed before docker logs existed.
        for file in ["stdout.txt", "stderr.txt"]:
            (artifact_dir / file).touch(exist_ok=True)
    return row

"""Build isolated Python 3.9 Linux images, one per pinned benchmark repository."""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid

from erb.common import ROOT, code_identity, digest, manifest, now, read_json, run_lock, sha256, write_json
from erb.data import DATA_SHA, LOCK, extract_repository, load_dataset, select_tasks, task_path, verify_file
from erb.docker import InfrastructureError, command, daemon_info, output


def build_repository(repo, tasks, args, base, destination):
    destination.mkdir(parents=True, exist_ok=True)
    targets = sorted({"/".join(task_path(t["file_name"], repo).parts[1:]) for t in tasks})
    config = {"repo": repo, "dataset_sha256": DATA_SHA, "archive_sha256": LOCK["files"]["repos.zip"]["sha256"],
              "base_image": base, "targets": targets,
              "build_files": {n: sha256(ROOT / n) for n in ["docker/Dockerfile", "docker/test-requirements.txt", "erb/container_guard.py", "erb/container_runner.py"]}}
    config["scm_pretend_version"] = "0.0.0+erb.archive" if repo == "eip712" else ""
    if repo == "python-sortedcontainers":
        # Archived pyannote-banyan uses C++03 null-pointer/allocator conventions.
        # Compile the unchanged dependency with its original language/ABI model.
        config["build_env"] = {"CFLAGS": "-std=c++03 -D_GLIBCXX_USE_CXX11_ABI=0",
                               "CXXFLAGS": "-std=c++03 -D_GLIBCXX_USE_CXX11_ABI=0"}
        # Its saved pylint<2.6 needs mccabe<0.7. The flake8 tool added for
        # cacheout's dev extra is not a dependency of this project/test driver.
        config["post_install_commands"] = [
            ["python", "-m", "pip", "uninstall", "-y", "flake8"],
            ["python", "-m", "pip", "install", "--no-cache-dir", "mccabe==0.6.1"]]
    fingerprint = digest(config)
    saved = destination / "image.json"
    if saved.exists():
        old = read_json(saved)
        if old.get("fingerprint") != fingerprint:
            if not args.rebuild_changed:
                raise ValueError(f"Image settings changed for {repo}; use a new --output-dir or --rebuild-changed")
            history = destination / "history" / old["fingerprint"]
            history.mkdir(parents=True, exist_ok=True)
            for name in ["image.json", "build.log", "packages.txt", "imports.json"]:
                if (destination / name).exists():
                    shutil.copyfile(destination / name, history / name)
        elif old.get("status") == "ready":
            output(["image", "inspect", old["image_id"]])
            return old
    record = dict(config, fingerprint=fingerprint, started_at=now(), status="infrastructure_error")
    try:
        with tempfile.TemporaryDirectory(prefix="erb image ") as directory:
            context = Path(directory)
            extract_repository(args.archive, repo, context / "repo")
            for source, name in [(ROOT / "docker/Dockerfile", "Dockerfile"),
                                 (ROOT / "docker/test-requirements.txt", "test-requirements.txt"),
                                 (ROOT / "erb/container_guard.py", "container_guard.py"),
                                 (ROOT / "erb/container_runner.py", "container_runner.py")]:
                shutil.copyfile(source, context / name)
            if config.get("build_env"):
                dockerfile = context / "Dockerfile"
                text = dockerfile.read_text("utf-8")
                marker = 'RUN if [ -n "$SCM_PRETEND_VERSION" ]'
                flags = config["build_env"]
                text = text.replace(marker, 'ENV CFLAGS="' + flags["CFLAGS"] + '" CXXFLAGS="' + flags["CXXFLAGS"] + '"\n' + marker, 1)
                dockerfile.write_text(text, encoding="utf-8", newline="\n")
            if config.get("post_install_commands"):
                dockerfile = context / "Dockerfile"
                text = dockerfile.read_text("utf-8")
                extra = "\n".join("RUN " + json.dumps(cmd) for cmd in config["post_install_commands"])
                text = text.replace("RUN python -m pip check", extra + "\nRUN python -m pip check", 1)
                dockerfile.write_text(text, encoding="utf-8", newline="\n")
            write_json(context / "targets.json", targets)
            tag = "erb-fixed/" + repo.lower() + ":" + fingerprint[:16]
            with (destination / "build.log").open("wb") as log:
                result = command(["build", "--progress=plain", "--build-arg", "BASE_IMAGE=" + base,
                                  "--build-arg", "SCM_PRETEND_VERSION=" + config["scm_pretend_version"],
                                  "--tag", tag, context], timeout=args.build_timeout, check=False,
                                 stdout=log, stderr=subprocess.STDOUT)
            if result.returncode:
                raise InfrastructureError(f"Build failed for {repo}; see {destination / 'build.log'}")
            image_id = output(["image", "inspect", "--format", "{{.Id}}", tag])
            container = "erb-provenance-" + uuid.uuid4().hex
            output(["create", "--name", container, "--network", "none", image_id])
            try:
                for file in ["packages.txt", "imports.json"]:
                    output(["cp", f"{container}:/opt/erb/{file}", destination / file])
            finally:
                output(["rm", "--force", container])
            record.update(status="ready", image_id=image_id, tag=tag,
                          packages_sha256=sha256(destination / "packages.txt"),
                          imports=read_json(destination / "imports.json"))
    except (InfrastructureError, OSError, ValueError) as e:
        record["error"] = str(e)
    record["completed_at"] = now()
    write_json(saved, record)
    return record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, default=Path("data/exec_repo_bench.jsonl"))
    p.add_argument("--archive", type=Path, default=Path("data/repos.zip"))
    p.add_argument("--output-dir", type=Path, default=Path("images"))
    p.add_argument("--base-image", help="Default: prior manifest digest, otherwise python:3.9-bookworm")
    p.add_argument("--selection", choices=["full", "pilot"], default="full")
    p.add_argument("--build-timeout", type=int, default=1800)
    p.add_argument("--build-workers", type=int, default=1)
    p.add_argument("--rebuild-changed", action="store_true", help="Archive previous build diagnostics before replacing derived records")
    args = p.parse_args()
    if args.build_timeout < 1 or args.build_workers < 1:
        p.error("build timeout and build workers must be positive")
    tasks = load_dataset(args.data)
    verify_file(args.archive, "repos.zip")
    daemon = daemon_info()
    previous = args.output_dir / "manifest.json"
    base_ref = args.base_image or (read_json(previous)["config"]["base_image"] if previous.exists() else "python:3.9-bookworm")
    command(["pull", base_ref], timeout=args.build_timeout)
    inspected = json.loads(output(["image", "inspect", base_ref]))[0]
    if inspected.get("Os") != "linux":
        raise ValueError("Base image must use Linux")
    digests = inspected.get("RepoDigests") or []
    if not digests:
        raise ValueError("Base image has no immutable registry digest")
    base = digests[0]
    by_repo = defaultdict(list)
    selected_repos = {t["repo_name"] for t in select_tasks(tasks, args.selection)}
    for task in tasks:
        if task["repo_name"] in selected_repos:
            by_repo[task["repo_name"]].append(task)
    with run_lock(args.output_dir):
        records = {}
        with ThreadPoolExecutor(max_workers=args.build_workers) as pool:
            futures = {pool.submit(build_repository, repo, by_repo[repo], args, base, args.output_dir / repo): repo
                       for repo in sorted(by_repo)}
            for future in as_completed(futures):
                repo = futures[future]
                records[repo] = future.result()
                print(f"{len(records)}/{len(by_repo)} {repo}: {records[repo]['status']}", flush=True)
                write_json(args.output_dir / "manifest.json", manifest(dict(dataset_sha256=DATA_SHA,
                           archive_sha256=LOCK["files"]["repos.zip"]["sha256"], base_image=base,
                           build_workers=args.build_workers, code=code_identity(), daemon=daemon, images=records), "images"))
        failures = [r for r in records if records[r]["status"] != "ready"]
        print(f"Ready: {len(records)-len(failures)}/{len(records)}; failures: {failures}")
        return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Explicit local Docker integration checks, synthetic project only (not benchmark scores).
Run from erb_fixed: python tests/docker_integration.py --base-image python:3.9-bookworm
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from erb.common import ROOT, write_json
from erb.data import CATEGORIES
from erb.docker import Limits, daemon_info, evaluate_task, output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-image", default="python:3.9-bookworm")
    parser.add_argument("--output-dir", type=Path, default=Path("test-artifacts/docker"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    daemon = daemon_info()
    tag = "erb-fixed-test:" + uuid.uuid4().hex[:12]
    try:
        with tempfile.TemporaryDirectory(prefix="erb synthetic ") as d:
            context = Path(d)
            (context / "repo/pkg").mkdir(parents=True)
            (context / "repo/pkg/__init__.py").write_text("", encoding="utf-8")
            (context / "repo/pkg/value.py").write_text("VALUE = 1\n", encoding="utf-8")
            (context / "repo/setup.py").write_text("from setuptools import setup\nsetup(name='erb-synthetic',version='1',packages=['pkg'])\n", encoding="utf-8")
            (context / "repo/evaluate_repo.py").write_text(
                "import os,sys\nfrom pkg.value import VALUE\nassert VALUE == 2, VALUE\nassert os.getuid() == 10001\n"
                "assert not os.path.exists('/var/run/docker.sock')\nprint('candidate imported', VALUE)\n", encoding="utf-8")
            for src, dest in [("erb/container_guard.py", "container_guard.py"), ("erb/container_runner.py", "runner.py")]:
                shutil.copyfile(ROOT / src, context / dest)
            write_json(context / "targets.json", ["pkg/value.py"])
            (context / "Dockerfile").write_text(
                "FROM " + args.base_image + "\nENV PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/opt/erb:/repo\nWORKDIR /repo\n"
                "COPY repo/ /repo/\nCOPY container_guard.py runner.py targets.json /opt/erb/\n"
                "RUN python -m pip install --no-build-isolation --no-deps -e .\n"
                "RUN python /opt/erb/container_guard.py > /opt/erb/imports.json\n"
                "RUN chown -R 10001:10001 /repo && chmod -R a+rX /opt/erb\nUSER 10001:10001\n", encoding="utf-8")
            with (args.output_dir / "build.log").open("wb") as log:
                subprocess.run(["docker", "build", "--progress=plain", "-t", tag, str(context)],
                               stdout=log, stderr=subprocess.STDOUT, check=True)
        image = output(["image", "inspect", "--format", "{{.Id}}", tag])
        def run(i, middle, limits=Limits(timeout=10)):
            task = dict(task_id=i, repo_name="synthetic", fill_type=CATEGORIES[0],
                        file_name="/synthetic/pkg/value.py", prefix_code="", suffix_code="")
            return evaluate_task(task, middle, image, limits, args.output_dir / (str(i) + "-" + uuid.uuid4().hex[:6]))
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(run, 0, "VALUE = 2\n")
            b = pool.submit(run, 1, "VALUE = 3\n")
            passed, failed = a.result(), b.result()
        assert passed["status"] == "pass", passed
        assert passed["runner"]["target_import_observed"], passed
        assert failed["status"] == "test_fail", failed
        # A child process is running when the whole container is killed.
        timeout = run(2, "import subprocess,time\nsubprocess.Popen(['python','-c','import time;time.sleep(100)'])\ntime.sleep(100)\nVALUE=2\n", Limits(timeout=1))
        assert timeout["status"] == "timeout", timeout
        oom = run(3, "x=[]\nwhile True: x.append(bytearray(16*1024*1024))\n", Limits(memory="128m", timeout=20))
        assert oom["status"] == "oom", oom
        missing = evaluate_task(dict(task_id=4, repo_name="synthetic", fill_type=CATEGORIES[0], file_name="/synthetic/pkg/value.py", prefix_code="", suffix_code=""),
                                "VALUE=2", "sha256:" + "0" * 64, Limits(timeout=2), args.output_dir / ("missing-" + uuid.uuid4().hex[:6]))
        assert missing["status"] == "infrastructure_error", missing
        for row in [passed, failed, timeout, oom, missing]:
            assert not output(["ps", "-a", "--filter", "name=" + row["container"], "--format", "{{.ID}}"]), row
        report = dict(daemon=daemon, image=image, results=[passed, failed, timeout, oom, missing],
                      scope="Synthetic local Docker checks only; no benchmark/GPU/server validation")
        write_json(args.output_dir / "report.json", report)
        print("PASS: candidate import, concurrent isolation, pass/fail/timeout/oom/infrastructure, full-container cleanup")
    finally:
        subprocess.run(["docker", "image", "rm", tag], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    main()

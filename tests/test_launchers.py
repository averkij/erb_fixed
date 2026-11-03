"""Real launcher invocation with capture interpreters, including paths with spaces."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from erb.common import ROOT

ARGS = ["--data", "data with spaces/input.jsonl", "--run-dir", "run with spaces",
        "--output-dir", "output with spaces", "--images", "images with spaces/manifest.json",
        "--workers", "3", "--cpus", "2.5", "--memory", "5g", "--pids", "300",
        "--timeout", "123", "--selection", "pilot", "--gold-summary", "gold with spaces/summary.json"]


class LauncherTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows PowerShell required")
    def test_powershell_arguments_and_exit(self):
        with tempfile.TemporaryDirectory(prefix="erb launcher spaces ") as d:
            root = Path(d)
            stub = root / "fake python.ps1"
            stub.write_text("[IO.File]::WriteAllText((Join-Path $PSScriptRoot 'args.json'), (ConvertTo-Json -InputObject @($args)))\n$global:LASTEXITCODE=37\n", encoding="utf-8")
            result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts/evaluate_local.ps1"), "--python", str(stub), *ARGS], capture_output=True)
            self.assertEqual(result.returncode, 37, result.stderr)
            captured = json.loads((root / "args.json").read_text("utf-8"))
            self.assertEqual(captured[1:], ARGS)
            self.assertEqual(Path(captured[0]).name, "eval.py")
            missing = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts/evaluate_local.ps1"), "--python"], capture_output=True)
            self.assertEqual(missing.returncode, 2)

    def test_bash_arguments_and_exit(self):
        if os.name == "nt":
            if not shutil.which("wsl"):
                self.skipTest("No WSL")
            prefix = ["wsl", "-d", "Ubuntu", "--exec"]
            def linux_path(path):
                return subprocess.check_output([*prefix, "wslpath", "-a", str(path)], text=True).strip()
        else:
            prefix = []
            linux_path = str
        # Keep fixtures on the same mounted workspace when crossing into WSL.
        (ROOT / "test-artifacts").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="launcher spaces ", dir=ROOT / "test-artifacts") as d:
            root = Path(d)
            stub = root / "fake python"
            stub.write_text("#!/usr/bin/python3\nimport json,pathlib,sys\npathlib.Path(__file__).with_name('args.json').write_text(json.dumps(sys.argv[1:]))\nsys.exit(37)\n", encoding="utf-8", newline="\n")
            subprocess.run([*prefix, "chmod", "+x", linux_path(stub)], check=True)
            launch = [*prefix, "bash", linux_path(ROOT / "scripts/evaluate_local.sh")]
            result = subprocess.run([*launch, "--python", linux_path(stub), *ARGS], capture_output=True)
            self.assertEqual(result.returncode, 37, result.stderr)
            captured = json.loads((root / "args.json").read_text("utf-8"))
            self.assertEqual(captured[1:], ARGS)
            self.assertEqual(Path(captured[0]).name, "eval.py")
            missing = subprocess.run([*launch, "--python"], capture_output=True)
            self.assertEqual(missing.returncode, 2)


if __name__ == "__main__":
    unittest.main()

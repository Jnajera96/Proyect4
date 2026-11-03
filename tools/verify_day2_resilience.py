"""Run offline Day 2 tests with unique short paths and a bounded wall-clock deadline."""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New directory for logs and evidence")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error("Evidence directory must not already exist")
    output.mkdir(parents=True)
    root = Path(__file__).resolve().parents[1]
    head = lambda: subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    before = head()
    # Short unique paths avoid Windows path limits and parallel pytest cleanup collisions.
    temporary = Path(tempfile.mkdtemp(prefix="aiswe-day2-")) / "pytest"
    assert not temporary.exists()
    suites = ["tests/stress/test_concurrency_and_crash.py",
              "tests/test_budget_pause_and_recovery.py", "tests/test_continuity_m.py",
              "tests/test_worker_claim_resilience.py"]
    command = [sys.executable, "-m", "pytest", *suites, "-v", "--tb=short",
               "--basetemp", str(temporary), "-o", "tmp_path_retention_policy=failed",
               "--junitxml=" + str(output / "results.xml")]
    with (output / "run.log").open("w", encoding="utf-8") as log:
        try:
            result = subprocess.run(command, cwd=root, stdout=log, stderr=subprocess.STDOUT,
                                    timeout=180)
            code = result.returncode
        except subprocess.TimeoutExpired:
            code = 124
    after = head()
    report = dict(start_head=before, end_head=after, stable_head=before == after,
                  returncode=code, deadline_seconds=180, python=sys.version,
                  executable=sys.executable, platform=platform.platform(), command=command,
                  paid_api_calls=0, real_network=False)
    if (output / "results.xml").exists():
        report["suites"] = [s.attrib for s in ET.parse(output / "results.xml").iter("testsuite")]
    report["success"] = code == 0 and before == after
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return code if code else (0 if before == after else 2)


if __name__ == "__main__":
    raise SystemExit(main())

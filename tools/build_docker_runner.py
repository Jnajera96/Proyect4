"""Build only the pinned runner recipe and canonical static detector; no repository context."""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ai_swe.tools.docker_runner import docker_executable  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--iidfile", type=Path, required=True)
    args = parser.parse_args()
    output = args.iidfile.resolve()
    if output.exists():
        parser.error("Use a new image receipt path")
    with tempfile.TemporaryDirectory(prefix="aiswe-image-build-") as directory:
        context = Path(directory)
        for name in ("Dockerfile", ".dockerignore", "requirements.txt", "run_target.py"):
            shutil.copy2(ROOT / "packaging/docker-runner" / name, context / name)
        shutil.copy2(ROOT / "src/ai_swe/tools/dependency_detector.py",
                     context / "dependency_detector.py")
        config = context / "config"
        config.mkdir()
        (config / "config.json").write_text(json.dumps({"auths": {}}))
        subprocess.run([
            docker_executable(), "--host", "npipe:////./pipe/dockerDesktopLinuxEngine",
            "--config", str(config), "build", "--platform", "linux/amd64",
            "--iidfile", str(output), str(context),
        ], check=True)


if __name__ == "__main__":
    main()

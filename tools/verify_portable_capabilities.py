"""Offline proof of new capabilities using only the portable's signed Python."""

import argparse
import json
import os
import subprocess
from pathlib import Path

PROBE = r"""
import json, shutil, sys
from pathlib import Path
from types import SimpleNamespace
if not __debug__:
    raise RuntimeError('Assertions must remain enabled for verification')
bundle, output = map(lambda p: Path(p).resolve(), sys.argv[1:])
sys._ai_swe_bundle = bundle
import ai_swe
assert Path(ai_swe.__file__).resolve().is_relative_to(bundle/'app')
checks=['application imported from extracted portable']
def check(condition, name):
    assert condition, name
    checks.append(name)
check(shutil.which('python') is None and shutil.which('node') is None,
      'no development Python or Node on PATH')
from ai_swe.config import Settings
settings = Settings(_env_file=None)
check(settings.runtime_mode=='installed', 'signed bundle marker activates installed settings')
check(settings.stt_device=='cpu' and settings.stt_compute_type=='int8',
      'Windows STT defaults CPU int8')
import av, ctranslate2, faster_whisper
check(av.__version__=='18.1.0', 'PyAV 18.1.0 and Whisper native dependencies import offline')
repo = output/'repository'
repo.mkdir()
repo.joinpath('app.py').write_bytes(b'def answer():\n    return 42\n# synthetic-portable-private\n')
from ai_swe.security import register_secret
register_secret('synthetic-portable-private')
from ai_swe.mcp.client import read_context, MCPReadError
context = read_context(repo, ['app.py'])
check(context=={'app.py':'def answer():\n    return 42\n# [REDACTED]\n'},
      'installed MCP child starts through signed launcher and redacts literals')
try:
    read_context(repo, ['../outside.py'])
except MCPReadError as error:
    check(error.tool_calls==1, 'MCP denies escaping paths without fallback')
else:
    raise AssertionError('MCP path escape accepted')
from ai_swe.state.knowledge_graph import build_graph
graph = build_graph(repo, ['app.py'])
check(graph['provenance']=='EXTRACTED' and any(n['label']=='answer' for n in graph['nodes']),
      'local AST graph extracts actual packaged symbols')
from ai_swe.tools.runner import ejecutar, RunnerError
try:
    ejecutar(SimpleNamespace(raiz=repo), 'pytest.unit', permitidos=('pytest.unit',))
except RunnerError as error:
    check(error.operacion=='network_egress', 'native runner rejects strict network before launch')
else:
    raise AssertionError('Native strict execution accepted')
from ai_swe.tools.dependency_detector import SourceFile, detect_node_dependencies
from ai_swe.tools.policy import node_dependency_issues
manifest = detect_node_dependencies([SourceFile('package.json','{"dependencies":{"express":"4"}}')])
check(any('offline' in issue for issue in node_dependency_issues(manifest,['express'])),
      'authorized npm package remains unavailable without offline inventory')
check(manifest.preflight()['runtime_available'] is False,
      'Node preflight never borrows build-host runtime')
print(json.dumps(dict(success=True, checks=checks, paid_calls=0, real_stt_inference=False,
    real_audio=False, real_langfuse=False, sys_frozen=bool(getattr(sys,'frozen',False)),
    module=str(Path(ai_swe.__file__).resolve()),python=sys.version.split()[0])))
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    bundle, output = args.bundle.resolve(), args.output.resolve()
    if output.exists() or not (bundle / "runtime/python.exe").is_file():
        parser.error("Supply an extracted bundle and a new evidence directory")
    output.mkdir(parents=True)
    environment = {
        k: v
        for k, v in os.environ.items()
        if k.upper()
        in {
            "SYSTEMROOT",
            "SYSTEMDRIVE",
            "WINDIR",
            "COMSPEC",
            "PATHEXT",
            "TEMP",
            "TMP",
            "USERPROFILE",
            "HOME",
            "APPDATA",
            "PROGRAMDATA",
            "NUMBER_OF_PROCESSORS",
            "PROCESSOR_ARCHITECTURE",
        }
    }
    environment.update(
        LOCALAPPDATA=str(output / "userdata"),
        HF_HOME=str(output / "hf-cache"),
        HF_HUB_OFFLINE="1",
        PATH=str(Path(os.environ["SYSTEMROOT"]) / "System32"),
        PYTHONDONTWRITEBYTECODE="1",
    )
    completed = subprocess.run(
        [str(bundle / "runtime/python.exe"), "-B", "-c", PROBE, str(bundle), str(output)],
        cwd=output,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=90,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    (output / "stdout.log").write_text(completed.stdout, encoding="utf-8")
    (output / "stderr.log").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode:
        raise RuntimeError("Portable capabilities failed; inspect the isolated evidence logs")
    report = json.loads(completed.stdout.splitlines()[-1])
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

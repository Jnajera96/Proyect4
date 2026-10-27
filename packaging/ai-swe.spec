# PyInstaller onedir. Only built frontend assets, no .env, databases or model weights.
from pathlib import Path
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules, copy_metadata

root = Path(SPECPATH).parent
frontend = Path(os.environ["AI_SWE_PACKAGE_FRONTEND"])
datas = [(str(frontend), "frontend/dist")]
for distribution in ("ai-swe-system", "langgraph", "langchain-core", "langgraph-checkpoint", "langgraph-checkpoint-sqlite"):
    datas += copy_metadata(distribution)
datas += collect_data_files("faster_whisper")
datas += [(str(Path(sys.executable).parent / "ruff.exe"), "tools")]
datas += copy_metadata("pytest")
binaries = collect_dynamic_libs("ctranslate2")
hidden = collect_submodules("ai_swe") + [
    "uvicorn.logging", "uvicorn.loops.asyncio", "uvicorn.protocols.http.h11_impl",
    "uvicorn.lifespan.on", "langgraph.checkpoint.sqlite", "aiosqlite", "faster_whisper", "pytest",
]
a = Analysis(
    [str(root / "packaging/entrypoint.py")], pathex=[str(root / "src")],
    binaries=binaries, datas=datas, hiddenimports=hidden,
    excludes=["IPython", "jupyter", "notebook", "torch", "tensorflow", "matplotlib"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="AISWESystem", console=True, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="AISWESystem", upx=False)

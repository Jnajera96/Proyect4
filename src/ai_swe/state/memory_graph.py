"""Owner/repository-scoped file associations; no embeddings, network or inference."""

from __future__ import annotations

import hashlib
import itertools
import re
import sqlite3
from contextlib import closing
from pathlib import Path

IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
}
IGNORED_FILES = {
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "uv.lock",
    "poetry.lock",
    "pdm.lock",
}


def usable_path(path: str) -> bool:
    parts = Path(path.replace("\\", "/")).parts
    return (
        bool(parts)
        and not Path(path).is_absolute()
        and ".." not in parts
        and not any(p in IGNORED_DIRECTORIES or p.startswith(".env") for p in parts)
        and parts[-1] not in IGNORED_FILES
    )


def explicit_paths(query: str, candidates: list[str]) -> set[str]:
    text = query.lower()
    return {p for p in candidates if p.lower() in text or Path(p).name.lower() in text}


class FileMemoryGraph:
    def __init__(self, database: Path, owner: str = "legacy"):
        self.database, self.owner = Path(database), owner
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.database, timeout=30)) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS file_cooccurrence(
                    owner TEXT NOT NULL, repository TEXT NOT NULL,
                    source TEXT NOT NULL, target TEXT NOT NULL, weight REAL NOT NULL,
                    last_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(owner,repository,source,target));
                CREATE TABLE IF NOT EXISTS file_observations(
                    owner TEXT NOT NULL, repository TEXT NOT NULL, observation TEXT NOT NULL,
                    PRIMARY KEY(owner,repository,observation));
            """)

    def observe(self, repository: str, paths: list[str], *, observation: str) -> None:
        paths = sorted({p.replace("\\", "/") for p in paths if usable_path(p)})[:50]
        repo = str(Path(repository).resolve())
        fingerprint = hashlib.sha256("\n".join(paths).encode()).hexdigest()
        with closing(sqlite3.connect(self.database, timeout=30)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            inserted = db.execute(
                "INSERT OR IGNORE INTO file_observations VALUES(?,?,?)",
                (self.owner, repo, observation + ":" + fingerprint),
            )
            if not inserted.rowcount:
                return
            for source, target in itertools.permutations(paths, 2):
                db.execute(
                    """INSERT INTO file_cooccurrence(owner,repository,source,target,weight)
                    VALUES(?,?,?,?,1) ON CONFLICT(owner,repository,source,target)
                    DO UPDATE SET weight=weight+1,last_seen=CURRENT_TIMESTAMP""",
                    (self.owner, repo, source, target),
                )

    def select(self, repository: str, query: str, candidates: list[str], *, top_k: int = 8):
        candidates = sorted({p for p in candidates if usable_path(p)})
        top_k = max(1, min(50, top_k))
        terms = set(re.findall(r"[\w-]+", query.lower()[:20000]))
        scores, explicit = {}, explicit_paths(query, candidates)
        for path in candidates:
            parts = set(re.findall(r"[\w-]+", str(Path(path).with_suffix("")).lower()))
            scores[path] = float(len(terms & parts))
            if path in explicit:
                scores[path] += 100
        seeds = sorted((p for p in candidates if scores[p]), key=lambda p: (-scores[p], p))[:8]
        if not seeds:
            return candidates
        if seeds:
            with closing(sqlite3.connect(self.database, timeout=30)) as db, db:
                rows = db.execute(
                    "SELECT source,target,weight FROM file_cooccurrence "
                    "WHERE owner=? AND repository=?",
                    (self.owner, str(Path(repository).resolve())),
                )
                for source, target, weight in rows:
                    if source in seeds and target in scores:
                        scores[target] += min(float(weight), 50) / 10
        # Explicitly requested files are never dropped just to meet a reduction target.
        selected = sorted(explicit)
        selected.extend(
            p
            for p in sorted(candidates, key=lambda p: (-scores[p], p))
            if p not in explicit and len(selected) < top_k
        )
        return selected

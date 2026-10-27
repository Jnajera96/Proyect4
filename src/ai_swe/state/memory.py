"""Bounded, redacted, owner/repository-scoped local FTS5 projections."""
from contextlib import contextmanager
import json
from pathlib import Path
import re
import sqlite3

from ai_swe.contracts.state import HistoricalContext
from ai_swe.security import redact_deep


class MemoryStore:
    def __init__(self, database, owner):
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.owner = owner
        with self.connection() as con:
            con.executescript('''
                CREATE TABLE IF NOT EXISTS memory_documents (
                    id INTEGER PRIMARY KEY, owner TEXT NOT NULL, repository TEXT NOT NULL,
                    run_id TEXT NOT NULL, kind TEXT NOT NULL, text TEXT NOT NULL,
                    UNIQUE(owner, repository, run_id, kind));
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(text);
            ''')

    @contextmanager
    def connection(self):
        con = sqlite3.connect(self.database, timeout=15)
        con.row_factory = sqlite3.Row
        try:
            with con:
                yield con
        finally:
            con.close()

    def project(self, state):
        if not state.options.repo_path:
            return
        repository = str(Path(state.options.repo_path).resolve())
        values = {
            'interpretation': (
                {'instruction': state.instruction.text, 'interpretation': state.interpretation.model_dump(mode='json')}
                if state.interpretation is not None
                else None
            ),
            'plan': state.plan,
            'changed_paths': [f.path for f in state.artifacts.changed_files] or None,
            'code_proposal': state.outputs.code_proposal,
            'review': state.outputs.reviewer_output,
        }
        with self.connection() as con:
            for kind, value in values.items():
                if value is None:
                    continue
                data = value.model_dump(mode='json') if hasattr(value, 'model_dump') else value
                text = json.dumps(redact_deep(data), ensure_ascii=False)[:16000]
                row = con.execute('''INSERT INTO memory_documents(owner,repository,run_id,kind,text)
                    VALUES(?,?,?,?,?) ON CONFLICT(owner,repository,run_id,kind)
                    DO UPDATE SET text=excluded.text RETURNING id''',
                    (self.owner, repository, state.run_id, kind, text)).fetchone()
                con.execute('DELETE FROM memory_fts WHERE rowid=?', (row['id'],))
                con.execute('INSERT INTO memory_fts(rowid,text) VALUES(?,?)', (row['id'], text))

    def search(self, repository, query, *, exclude_run, limit=8):
        # Literal tokens, never raw MATCH syntax from a user/model.
        terms = list(dict.fromkeys(re.findall(r'\w+', query[:2000], re.UNICODE)))[:24]
        if not terms:
            return []
        match = ' OR '.join('"' + term.replace('"', '""') + '"' for term in terms)
        with self.connection() as con:
            rows = con.execute('''SELECT d.run_id,d.kind,d.text,bm25(memory_fts) AS score
                FROM memory_fts JOIN memory_documents d ON d.id=memory_fts.rowid
                WHERE memory_fts MATCH ? AND d.owner=? AND d.repository=? AND d.run_id<>?
                ORDER BY score,d.id DESC LIMIT ?''',
                (match, self.owner, str(Path(repository).resolve()), exclude_run, max(1,min(8,limit)))).fetchall()
        return [HistoricalContext(run_id=r['run_id'],kind=r['kind'],text=r['text'][:4000],score=r['score']) for r in rows]

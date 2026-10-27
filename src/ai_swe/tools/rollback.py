"""Path-scoped Git tree receipts. Never changes HEAD or the real Git index."""
from contextlib import contextmanager
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import tempfile
import uuid

from ai_swe.contracts.state import PromotionReceipt
from ai_swe.tools.policy import normalize_rel_path, path_within_scope

MAX_BYTES = 32 * 1024 * 1024


class RollbackError(RuntimeError):
    pass


def _git(repo, *args, data=None, index=None):
    env = os.environ.copy()
    for key in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE'):
        env.pop(key, None)
    if index is not None:
        env['GIT_INDEX_FILE'] = str(index)
    result = subprocess.run(['git', *args], cwd=repo, env=env, input=data,
                            capture_output=True, timeout=30, shell=False)
    if result.returncode:
        raise RollbackError('No se pudo verificar el objeto Git o el repositorio')
    return result.stdout


def _identity(repo):
    repo = Path(repo)
    if repo.is_symlink() or repo.is_junction():
        raise RollbackError('Raiz enlazada no permitida')
    root = repo.resolve(strict=True)
    actual = Path(_git(root, 'rev-parse', '--show-toplevel').decode().strip()).resolve()
    if root != actual:
        raise RollbackError('La raiz no es el repositorio autorizado')
    return root, _git(root, 'rev-parse', '--absolute-git-dir').decode().strip(), _git(root, 'rev-parse', 'HEAD').decode().strip()


def _paths(root, paths, allowed_paths=(), protected_paths=()):
    if not paths or len(paths) > 500 or len(set(paths)) != len(paths):
        raise RollbackError('Inventario de rutas invalido')
    for name in paths:
        normalized = normalize_rel_path(name)
        parts = name.split('/')
        if normalized != name or any(p in ('', '.', '..') for p in parts):
            raise RollbackError('Ruta no canonica')
        if any(p.casefold() in ('.git', '.env', '.codex', '.agents', '.aws') or ':' in p for p in parts):
            raise RollbackError('Ruta interna o protegida')
        if not path_within_scope(name, tuple(allowed_paths)):
            raise RollbackError('Ruta fuera del alcance')
        if protected_paths and path_within_scope(name, tuple(protected_paths)):
            raise RollbackError('Ruta protegida')
        current = root
        for part in parts:
            current = current / part
            if current.is_symlink() or current.is_junction():
                raise RollbackError('Enlaces no permitidos')
        if current.exists() and not current.is_file():
            raise RollbackError('La ruta no es un archivo regular')
        if not current.resolve().is_relative_to(root):
            raise RollbackError('Ruta fuera del repositorio')


def _inventory(root, paths):
    values = {}
    size = 0
    for name in paths:
        path = root / name
        if not path.exists():
            values[name] = None
            continue
        size += path.stat().st_size
        if size > MAX_BYTES:
            raise RollbackError('La captura supera 32 MiB')
        values[name] = (path.read_bytes(), path.stat().st_mode)
    return values


def _write_inventory(root, values):
    for name, item in values.items():
        path = root / name
        if item is None:
            path.unlink(missing_ok=True)
        else:
            data, mode = item
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(prefix='.aiswe-restore-', dir=path.parent)
            try:
                with os.fdopen(descriptor, 'wb') as stream:
                    stream.write(data)
                os.chmod(temporary, stat.S_IMODE(mode))
                os.replace(temporary, path)
            finally:
                Path(temporary).unlink(missing_ok=True)


class RollbackStore:
    def __init__(self, database, owner):
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.owner = owner
        with self.connection() as con:
            con.executescript('''
                CREATE TABLE IF NOT EXISTS promotion_receipts (
                    receipt_id TEXT PRIMARY KEY, owner TEXT NOT NULL, run_id TEXT NOT NULL,
                    root TEXT NOT NULL, git_dir TEXT NOT NULL, head TEXT NOT NULL,
                    before_tree TEXT NOT NULL, after_tree TEXT NOT NULL, paths TEXT NOT NULL,
                    status TEXT NOT NULL, UNIQUE(owner,run_id));
                CREATE TABLE IF NOT EXISTS rollback_audit (
                    id INTEGER PRIMARY KEY, receipt_id TEXT NOT NULL, actor TEXT NOT NULL,
                    at TEXT NOT NULL, outcome TEXT NOT NULL, detail TEXT NOT NULL);
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

    def capture(self, repo, paths, *, allowed_paths=(), protected_paths=()):
        root, _, _ = _identity(repo)
        _paths(root, paths, allowed_paths, protected_paths)
        values = _inventory(root, paths)
        with tempfile.TemporaryDirectory(prefix='aiswe-index-') as directory:
            index = Path(directory) / 'index'
            _git(root, 'read-tree', '--empty', index=index)
            for name, item in values.items():
                if item is None:
                    continue
                data, mode = item
                blob = _git(root, 'hash-object', '-w', '--stdin', data=data).decode().strip()
                git_mode = '100755' if os.name != 'nt' and mode & stat.S_IXUSR else '100644'
                _git(root, 'update-index', '--add', '--cacheinfo', git_mode, blob, name, index=index)
            return _git(root, 'write-tree', index=index).decode().strip()

    def record(self, run_id, repo, before, after, paths, *, status='promoted'):
        root, git_dir, head = _identity(repo)
        _paths(root, paths)
        for tree in (before, after):
            if _git(root, 'cat-file', '-t', tree).strip() != b'tree':
                raise RollbackError('El recibo requiere objetos de arbol')
        receipt_id = uuid.uuid4().hex
        with self.connection() as con:
            con.execute('INSERT INTO promotion_receipts VALUES(?,?,?,?,?,?,?,?,?,?)',
                        (receipt_id,self.owner,run_id,str(root),git_dir,head,before,after,json.dumps(paths),status))
        return self.for_run(run_id)

    def activate(self, receipt_id):
        with self.connection() as con:
            con.execute("UPDATE promotion_receipts SET status='promoted' WHERE receipt_id=? AND owner=? AND status='prepared'", (receipt_id,self.owner))

    def for_run(self, run_id):
        with self.connection() as con:
            row = con.execute('SELECT * FROM promotion_receipts WHERE owner=? AND run_id=?', (self.owner,run_id)).fetchone()
        if not row:
            return None
        return PromotionReceipt(receipt_id=row['receipt_id'],pre_promotion_sha=row['before_tree'],
            promoted_sha=row['after_tree'],head=row['head'],paths=json.loads(row['paths']),status=row['status'])

    def audit(self, receipt_id):
        with self.connection() as con:
            return [dict(r) for r in con.execute('SELECT at,outcome,detail FROM rollback_audit WHERE receipt_id=? AND actor=? ORDER BY id', (receipt_id,self.owner))]

    def _read_tree(self, root, tree, paths):
        entries = _git(root, 'ls-tree', '-rz', tree).split(b'\0')
        values = dict.fromkeys(paths)
        size = 0
        for entry in entries:
            if not entry:
                continue
            metadata, raw_name = entry.split(b'\t', 1)
            mode, kind, oid = metadata.decode().split()
            name = raw_name.decode('utf-8')
            if name not in values or kind != 'blob' or mode not in ('100644','100755'):
                raise RollbackError('Arbol fuera del inventario autorizado')
            size += int(_git(root,'cat-file','-s',oid))
            if size > MAX_BYTES:
                raise RollbackError('Arbol supera 32 MiB')
            values[name] = (_git(root,'cat-file','blob',oid), 0o755 if mode == '100755' else 0o644)
        return values

    def rollback(self, receipt_id, repo, *, allowed_paths=(), protected_paths=()):
        failure = None
        with self.connection() as con:
            con.execute('BEGIN IMMEDIATE')
            try:
                row = con.execute('SELECT * FROM promotion_receipts WHERE receipt_id=? AND owner=?', (receipt_id,self.owner)).fetchone()
                if not row or row['status'] != 'promoted':
                    raise RollbackError('Recibo ajeno, incompleto o ya revertido')
                root, git_dir, head = _identity(repo)
                if (str(root),git_dir,head) != (row['root'],row['git_dir'],row['head']):
                    raise RollbackError('La identidad, raiz o HEAD del repositorio cambio')
                paths = json.loads(row['paths'])
                _paths(root, paths, allowed_paths, protected_paths)
                if self.capture(root, paths) != row['after_tree']:
                    raise RollbackError('Hay cambios posteriores a la promocion')
                before = self._read_tree(root, row['before_tree'], paths)
                current = _inventory(root, paths)
                try:
                    _write_inventory(root, before)
                    if self.capture(root, paths) != row['before_tree']:
                        raise RollbackError('La restauracion no coincide con el arbol previo')
                except Exception:
                    _write_inventory(root, current)
                    raise
                con.execute("UPDATE promotion_receipts SET status='rolled_back' WHERE receipt_id=?", (receipt_id,))
                outcome, detail = 'rolled_back', 'Solo se restauraron las rutas del recibo'
            except (RollbackError, OSError, subprocess.SubprocessError) as exc:
                failure = RollbackError(str(exc))
                outcome, detail = 'rejected', str(exc)[:500]
            con.execute('INSERT INTO rollback_audit(receipt_id,actor,at,outcome,detail) VALUES(?,?,?,?,?)',
                (receipt_id,self.owner,datetime.now(UTC).isoformat(),outcome,detail))
        if failure:
            raise failure

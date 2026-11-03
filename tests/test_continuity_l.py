from datetime import UTC, datetime
from pathlib import Path
import sqlite3
import subprocess

import pytest

from ai_swe.config import Settings
from ai_swe.contracts import Instruction, RunOptions, RunState
from ai_swe.contracts.state import ExecutionMode
from ai_swe.graph import nodes
from ai_swe.graph.engine import RunEngine
from ai_swe.graph.workflow import construir_grafo
from ai_swe.state import RunStore
from ai_swe.state.memory import MemoryStore
from ai_swe.tools.rollback import RollbackStore, RollbackError


def git(repo, *args):
    result = subprocess.run(['git', *args], cwd=repo, capture_output=True, check=True)
    return result.stdout.decode().strip()


def repo_at(path):
    path.mkdir()
    git(path, 'init', '-q')
    (path / 'app.py').write_bytes(b'value = 1\n')
    (path / 'deleted.bin').write_bytes(b'\x00old\xff')
    git(path, 'add', '.')
    git(path, '-c', 'user.name=Test', '-c', 'user.email=test@localhost', 'commit', '-qm', 'base')
    return path


def state(repo, run='old', mode='FULL_PROPOSAL'):
    now = datetime.now(UTC)
    return RunState(run_id=run, trace_id=run, created_at=now, updated_at=now,
        instruction=Instruction(text='modifica app.py quartz', source='text', confirmed_by_user=True),
        options=RunOptions(repo_path=str(repo), mode=mode))


def test_memory_fts_persists_upserts_and_isolates(tmp_path):
    repo = repo_at(tmp_path / 'repo')
    db = tmp_path / 'alice.sqlite3'
    mem = MemoryStore(db, 'alice')
    old = state(repo)
    old.interpretation = nodes._interpretacion_determinista(old, motivo='quartz')
    mem.project(old)
    mem.project(old)
    with sqlite3.connect(db) as con:
        assert 'fts5' in con.execute("SELECT sql FROM sqlite_master WHERE name='memory_fts'").fetchone()[0]
        assert con.execute('SELECT count(*) FROM memory_documents').fetchone()[0] == 1
    found = MemoryStore(db, 'alice').search(repo, 'quartz', exclude_run='new')
    assert found and found[0].run_id == 'old'
    assert not mem.search(repo, 'quartz', exclude_run='old')
    assert not MemoryStore(db, 'bob').search(repo, 'quartz', exclude_run='new')
    assert not mem.search(tmp_path / 'other', 'quartz', exclude_run='new')
    assert not MemoryStore(tmp_path / 'bob.sqlite3', 'bob').search(repo, 'quartz', exclude_run='new')
    mem.search(repo, '\" OR * : NEAR(', exclude_run='new')


@pytest.mark.parametrize('mode', ['INSPECT_ONLY', 'PLAN_ONLY'])
def test_modes_real_graph_settings_and_entry_guards(tmp_path, monkeypatch, mode):
    repo = repo_at(tmp_path / 'repo')
    settings = Settings(_env_file=None, profile_id='alice', state_db_path=tmp_path / 'alice.sqlite3',
        workspace_root=tmp_path / 'worktrees', remote_model_roles=[])
    def forbidden(*args, **kwargs):
        pytest.fail('restricted mode reached a side effect/model boundary')
    monkeypatch.setattr(nodes, '_coder_del_modelo', forbidden)
    monkeypatch.setattr(nodes, 'ejecutar_target', forbidden)
    monkeypatch.setattr(nodes, 'promover', forbidden)
    graph = construir_grafo(settings=settings)
    for name in ('coder', 'apply_sandbox', 'run_tests', 'reviewer', 'promote_changes'):
        delta = graph.nodes[name].runnable.invoke(state(repo, mode=mode))
        assert delta['status'].is_terminal
    with RunStore(settings.state_db_path) as store:
        engine = RunEngine(store, settings=settings)
        run = engine.start(state(repo, 'new', mode))
        if run.status.is_awaiting_human:
            run = engine.resume(run.run_id, 'approved')
        assert run.status.value == 'completed'
        assert run.plan is not None if mode == 'PLAN_ONLY' else run.outputs.researcher_output is not None
        assert run.outputs.coder_output is None and run.outputs.reviewer_output is None
        assert not run.evidence.test_runs and not settings.workspace_root.exists()
        assert (repo / 'app.py').read_bytes() == b'value = 1\n'


def test_researcher_bound_memory_is_local_and_automatic(tmp_path):
    repo = repo_at(tmp_path / 'repo')
    settings = Settings(_env_file=None, profile_id='alice', state_db_path=tmp_path / 'alice.sqlite3', remote_model_roles=[])
    with RunStore(settings.state_db_path) as store:
        engine = RunEngine(store, settings=settings)
        old = engine.start(state(repo, 'old', 'PLAN_ONLY'))
        if old.status.is_awaiting_human:
            engine.resume('old', 'approved')
        new = engine.start(state(repo, 'new', 'INSPECT_ONLY'))
        assert new.historical_context
        assert all(hit.run_id == 'old' for hit in new.historical_context)
        assert all('quartz' not in f.evidence for f in new.evidence.findings)
    with RunStore(settings.state_db_path) as reopened:
        assert RunEngine(reopened, settings=settings).get('new').historical_context


def promotion_receipt(tmp_path):
    repo = repo_at(tmp_path / 'repo')
    (repo / 'unrelated').write_bytes(b'user work')
    git(repo, 'add', 'unrelated')
    index = Path(git(repo, 'rev-parse', '--absolute-git-dir')) / 'index'
    index_bytes = index.read_bytes()
    receipts = RollbackStore(tmp_path / 'state.sqlite3', 'alice')
    before = receipts.capture(repo, ['app.py', 'added.bin', 'deleted.bin'])
    (repo / 'app.py').write_bytes(b'value = 42\n')
    (repo / 'added.bin').write_bytes(b'\x00new\xfe')
    (repo / 'deleted.bin').unlink()
    after = receipts.capture(repo, ['app.py', 'added.bin', 'deleted.bin'])
    receipt = receipts.record('run-one', repo, before, after, ['app.py', 'added.bin', 'deleted.bin'])
    assert git(repo, 'cat-file', '-t', receipt.pre_promotion_sha) == 'tree'
    assert git(repo, 'cat-file', '-t', receipt.promoted_sha) == 'tree'
    assert index.read_bytes() == index_bytes
    return repo, receipts, receipt, index, index_bytes


def test_rollback_real_git_binary_add_delete_index_and_repeat(tmp_path):
    repo, receipts, receipt, index, original_index = promotion_receipt(tmp_path)
    receipts.rollback(receipt.receipt_id, repo)
    assert (repo / 'app.py').read_bytes() == b'value = 1\n'
    assert (repo / 'deleted.bin').read_bytes() == b'\x00old\xff'
    assert not (repo / 'added.bin').exists()
    assert (repo / 'unrelated').read_bytes() == b'user work'
    assert index.read_bytes() == original_index
    with pytest.raises(RollbackError):
        receipts.rollback(receipt.receipt_id, repo)
    assert [e['outcome'] for e in receipts.audit(receipt.receipt_id)] == ['rolled_back', 'rejected']


@pytest.mark.parametrize('attack', ['edit', 'head', 'owner', 'root', 'protected'])
def test_rollback_rejects_conflicts_without_changes(tmp_path, attack):
    repo, receipts, receipt, index, original_index = promotion_receipt(tmp_path)
    target = repo
    protected = ()
    if attack == 'edit':
        (repo / 'app.py').write_bytes(b'later edit')
    elif attack == 'head':
        git(repo, '-c', 'user.name=Test', '-c', 'user.email=test@localhost', 'commit', '--allow-empty', '-qm', 'later')
    elif attack == 'owner':
        receipts = RollbackStore(tmp_path / 'state.sqlite3', 'bob')
    elif attack == 'root':
        target = repo_at(tmp_path / 'other')
    elif attack == 'protected':
        protected = ('app.py',)
    expected = (repo / 'app.py').read_bytes()
    with pytest.raises(RollbackError):
        receipts.rollback(receipt.receipt_id, target, protected_paths=protected)
    assert (repo / 'app.py').read_bytes() == expected
    assert (repo / 'added.bin').exists()


def test_full_proposal_two_gates_promotion_receipt_and_rollback(tmp_path, monkeypatch):
    from ai_swe.contracts.outputs import CodeProposal, FileOperation, FileProposal, TestRun

    repo = repo_at(tmp_path / 'repo')
    settings = Settings(
        _env_file=None,
        profile_id='alice',
        state_db_path=tmp_path / 'alice.sqlite3',
        workspace_root=tmp_path / 'worktrees',
        remote_model_roles=[],
    )
    proposal = CodeProposal(
        files=[
            FileProposal(
                path='app.py',
                operation=FileOperation.MODIFY,
                new_content='value = 99\n',
                rationale='update value to 99',
            )
        ],
        rationale='update app.py',
    )
    change = nodes._cambio_desde_propuesta(proposal)
    monkeypatch.setattr(
        nodes,
        '_coder_del_modelo',
        lambda s: (change, s.budget, [], proposal),
    )
    monkeypatch.setattr(
        nodes,
        'ejecutar_target',
        lambda sandbox, target, permitidos=(), limits=None, network_egress_enabled=False: TestRun(
            target=target,
            command=['pytest', '-q'],
            exit_code=0,
            passed=True,
            duration_s=0.1,
            output_excerpt='1 passed',
        ),
    )
    with RunStore(settings.state_db_path) as store:
        engine = RunEngine(store, settings=settings)
        run = engine.start(state(repo, 'full-run', 'FULL_PROPOSAL'))
        assert run.status.value == 'awaiting_human_requirements_confirmation'
        run = engine.resume('full-run', 'approved')
        assert run.status.value == 'awaiting_approval'
        assert run.outputs.code_proposal is not None
        assert run.outputs.reviewer_output is not None
        assert run.promotion_receipt is None
        assert (repo / 'app.py').read_bytes() == b'value = 1\n'

        run = engine.resume('full-run', 'approved')
        assert run.status.value == 'completed'
        assert run.promotion_receipt is not None
        assert run.promotion_receipt.status == 'promoted'
        assert (repo / 'app.py').read_text(encoding='utf-8') == 'value = 99\n'

        reverted = engine.rollback('full-run')
        assert reverted.promotion_receipt is not None
        assert reverted.promotion_receipt.status == 'rolled_back'
        assert (repo / 'app.py').read_bytes() == b'value = 1\n'
        with pytest.raises(RollbackError):
            engine.rollback('full-run')


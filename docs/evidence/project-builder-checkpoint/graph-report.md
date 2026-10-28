# Offline project-builder graph implementation

Source frozen: src/ai_swe/graph/nodes.py and tests/test_project_builder_pipeline.py.
No provider requests, paid calls, installs, remote Git or commits were performed.

Changes:
- Researcher reads HTML/CSS/JS/MJS/TS/TSX/JSX/SQL; test exercises real enumeration/evidence.
- Trimming discards implementation files from the end before test_*.py or *_test.py,
  for BOTH file and line caps. Original surviving order and rationale remain stable.
  Hard caps still apply when tests alone exceed them. Warning identifies discarded paths.
- ANY trimmed proposal becomes needs_human, with inspectable proposal/output and SCOPE_TRIMMED.
  apply_sandbox respects terminal state. No test-only false green, promotion or completed status.
- Planner/Coder describe offline HTML/CSS/vanilla JS + Python stdlib HTTP, optional existing
  FastAPI only, JSON/SQLite, semantic CRUD/calculation/persistence pytest, no network builds.
- Reviewer no longer must accept because tests are green: nits are nonblocking but evidenced
  functional/security/data/scope issues can block. Deterministic test/Ruff veto unchanged.

Focused evidence:
- Existing F6 real Coder: 33 tests passed.
- Existing F9 Reviewer: 26 tests passed.
- New builder suite: 9 tests passed; final new-file Ruff check passed.
- Combined F6/F9/new suite passed when new suite had 7 tests; two subsequent added tests
  (all-tests hard caps and real Researcher web discovery) passed in final 9-test suite.
- Two true graph E2Es use FakeModelAdapter JSON responses for Coder AND Reviewer, disposable
  local Git repos, real worktree patch application, actual subprocess pytest.unit and
  ruff.check exit 0, requirements gate, promotion gate, completed and exact file SHA256/content.
  Gate approval content hash uses coder_output.diff_sha256 (current existing contract);
  materialized artifacts.diff can differ from the proposal diff (Git diff formatting).
- Both calendar/calories oversized E2Es stop before sandbox/tests/reviewer/promotion.
- Full nodes.py Ruff still has pre-existing lint debt (unused imports, import ordering,
  long lines and dead _unused_promote_tail undefined state); unrelated cleanup not performed.
  Relevant missing FileProposal import was fixed. No added lint violation remains.

Fixture interfaces and scope:
- Calendar: index.html/app.js/style.css + calendar_app.py Events JSON CRUD + storage.py dispatch
  + server.py stdlib HTTP + test_calendar.py + README.md (8 files, below default 400 lines).
- Calories: same layout with calories.py SQLite Calories CRUD/total + test_calories.py.
- Browser GET /api reads Python storage; POST /api creates/edits/deletes; frontend fetch uses
  that same backend. No separate localStorage shadow or network dependency.
- CLI: python server.py (127.0.0.1:8000). Fixture helper accepts a kind/port, generated sources
  under _tmp/project-builder-browser/<kind>. All defaults remain 10 files/400 lines.

Actual browser checks (installed Playwright MCP, local loopback only, 2026-10-28):
- Calendar October 2026 -> November -> October; select 2026-10-01; create Browser event;
  edit Updated event; reload preserves JSON event; delete removes event.
- Calories add Rice 150g @130 and Apple 200g @52 => total299.00; edit Rice100g =>234.00;
  reload preserves SQLite rows/total; delete Apple =>130.00; delete Rice =>0.00.
- Both loopback server processes stopped after checks. Only console errors were favicon404.
- Snapshots/console artifacts preserved in _tmp/project-builder-playwright-browser.
- Reproduce serving: .venv/Scripts/python.exe _tmp/project_builder_fixture_server.py calendar 18761
  (or calories 18762), then interact with http://127.0.0.1:<port>.

Limits of evidence:
Fake adapters validate graph integration, not remote provider compatibility or arbitrary model
project quality. Browser checks cover explicit deterministic fixtures, not all generated apps.
Generated pytest verifies domain month/leap-year/event CRUD and calorie SQLite CRUD/reopen/input
validation/calculations; it does not pretend file presence verifies browser interactions.
No source changes outside owned graph/tests; helper/report/evidence are ignored _tmp artifacts.

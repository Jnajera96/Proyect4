"""Offline fixtures exercise the real graph/tools, without claiming remote compatibility."""

import hashlib
import subprocess
import textwrap

import pytest

from ai_swe.config import Settings
from ai_swe.contracts import CodeProposal, RunOptions, Scope
from ai_swe.graph import RunEngine, model_routing, nodes
from ai_swe.models import FakeModelAdapter, ModelGateway
from ai_swe.state import RunStore


def source(text):
    return textwrap.dedent(text).lstrip()


CALENDAR_PY = source('''
    import calendar
    import json
    from pathlib import Path


    def month(year, number):
        return calendar.monthcalendar(year, number)


    class Events:
        def __init__(self, path):
            self.path = Path(path)
            self.data = json.loads(self.path.read_text()) if self.path.exists() else {}

        def put(self, date, title):
            from datetime import date as day

            day.fromisoformat(date)
            if not title.strip():
                raise ValueError("empty title")
            self.data[date] = title.strip()
            self.save()

        def delete(self, date):
            del self.data[date]
            self.save()

        def save(self):
            self.path.write_text(json.dumps(self.data))
''')

CALENDAR_JS = source('''
    let shown = new Date();
    shown.setDate(1);
    let events = JSON.parse(localStorage.getItem('events') || '{}');
    const grid = document.querySelector('#days');
    function save() { localStorage.setItem('events', JSON.stringify(events)); render(); }
    function render() {
      document.querySelector('#month').textContent = shown.toLocaleDateString('en', {
        month: 'long', year: 'numeric'
      });
      grid.replaceChildren();
      const y = shown.getFullYear(), m = shown.getMonth();
      for (let day = 1; day <= new Date(y, m + 1, 0).getDate(); day++) {
        const key = `${y}-${String(m + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        const button = document.createElement('button');
        button.dataset.date = key;
        button.textContent = `${day} ${events[key] || ''}`;
        button.onclick = () => {
          document.querySelector('#date').value = key;
          document.querySelector('#title').value = events[key] || '';
        };
        grid.append(button);
      }
    }
    document.querySelector('#prev').onclick = () => {
      shown.setMonth(shown.getMonth() - 1); render();
    };
    document.querySelector('#next').onclick = () => {
      shown.setMonth(shown.getMonth() + 1); render();
    };
    document.querySelector('form').onsubmit = event => {
      event.preventDefault();
      const date = document.querySelector('#date').value;
      const title = document.querySelector('#title').value.trim();
      if (date && title) { events[date] = title; save(); }
    };
    document.querySelector('#delete').onclick = () => {
      delete events[document.querySelector('#date').value]; save();
    };
    render();
''')

CALENDAR_HTML = source('''
    <!doctype html><html lang="en"><meta charset="utf-8"><title>Calendar</title>
    <link rel="stylesheet" href="style.css"><main>
    <h1>Calendar</h1><button id="prev">Previous month</button><h2 id="month"></h2>
    <button id="next">Next month</button><section id="days"></section>
    <form><label>Date<input id="date" type="date" required></label>
    <label>Event<input id="title" required></label><button>Save event</button></form>
    <button id="delete">Delete event</button></main><script src="app.js"></script></html>
''')

CALENDAR_TEST = source('''
    import pytest

    from calendar_app import Events, month


    def test_month_and_persistent_event_crud(tmp_path):
        assert sum(day != 0 for week in month(2024, 2) for day in week) == 29
        path = tmp_path / "events.json"
        events = Events(path)
        events.put("2024-02-29", "Lunch")
        assert Events(path).data == {"2024-02-29": "Lunch"}
        events.put("2024-02-29", "Dinner")
        assert Events(path).data["2024-02-29"] == "Dinner"
        events.delete("2024-02-29")
        assert Events(path).data == {}
        with pytest.raises(ValueError):
            events.put("2024-02-30", "Invalid")
        with pytest.raises(ValueError):
            events.put("2024-02-29", " ")
''')

CALORIES_PY = source('''
    import math
    import sqlite3


    class Calories:
        def __init__(self, path):
            self.db = sqlite3.connect(path)
            self.db.execute("CREATE TABLE IF NOT EXISTS meals (id INTEGER PRIMARY KEY, "
                            "name TEXT NOT NULL, grams REAL, per100 REAL)")

        def put(self, name, grams, per100, identifier=None):
            if not name.strip() or not all(math.isfinite(v) and v >= 0 for v in (grams, per100)):
                raise ValueError("invalid meal")
            if identifier is None:
                cursor = self.db.execute("INSERT INTO meals VALUES (NULL, ?, ?, ?)",
                                         (name.strip(), grams, per100))
                identifier = cursor.lastrowid
            else:
                self.db.execute("UPDATE meals SET name=?, grams=?, per100=? WHERE id=?",
                                (name.strip(), grams, per100, identifier))
            self.db.commit()
            return identifier

        def rows(self):
            query = "SELECT id, name, grams, per100 FROM meals ORDER BY id"
            return self.db.execute(query).fetchall()

        def total(self):
            return sum(row[2] * row[3] / 100 for row in self.rows())

        def delete(self, identifier):
            self.db.execute("DELETE FROM meals WHERE id=?", (identifier,))
            self.db.commit()

        def close(self):
            self.db.close()
''')

CALORIES_TEST = source('''
    import pytest

    from calories import Calories


    def test_sqlite_crud_calculations_and_reopen(tmp_path):
        path = tmp_path / "food.sqlite3"
        food = Calories(path)
        first = food.put("Rice", 150, 130)
        second = food.put("Apple", 200, 52)
        assert food.total() == pytest.approx(299)
        food.put("Rice", 100, 130, first)
        assert food.total() == pytest.approx(234)
        food.close()
        food = Calories(path)
        assert len(food.rows()) == 2
        assert food.total() == pytest.approx(234)
        food.delete(second)
        assert food.total() == pytest.approx(130)
        food.close()


    @pytest.mark.parametrize("name,grams,energy", [("", 1, 1), ("x", -1, 1),
                                                ("x", 1, float("nan"))])
    def test_invalid_input(tmp_path, name, grams, energy):
        food = Calories(tmp_path / "invalid.sqlite3")
        try:
            with pytest.raises(ValueError):
                food.put(name, grams, energy)
            assert food.rows() == []
        finally:
            food.close()
''')

# The browser uses the same Python persistence through the local stdlib server.
CALORIES_JS = source('''
    let meals = JSON.parse(localStorage.getItem('meals') || '[]');
    function render() {
      document.querySelector('#total').textContent = meals.reduce(
        (sum, row) => sum + row.grams * row.energy / 100, 0).toFixed(2);
      const list = document.querySelector('#meals'); list.replaceChildren();
      meals.forEach((row, i) => {
        const item = document.createElement('li');
        item.textContent = `${row.name}: ${row.grams}g `;
        const edit = document.createElement('button'); edit.textContent = 'Edit';
        edit.onclick = () => {
          document.querySelector('#name').value = row.name;
          document.querySelector('#grams').value = row.grams;
          document.querySelector('#energy').value = row.energy;
          document.querySelector('form').dataset.edit = i;
        };
        const remove = document.createElement('button'); remove.textContent = 'Delete';
        remove.onclick = () => { meals.splice(i, 1); save(); };
        item.append(edit, remove); list.append(item);
      });
    }
    function save() { localStorage.setItem('meals', JSON.stringify(meals)); render(); }
    document.querySelector('form').onsubmit = event => {
      event.preventDefault(); const form = event.currentTarget;
      const row = {name: document.querySelector('#name').value.trim(),
        grams: Number(document.querySelector('#grams').value),
        energy: Number(document.querySelector('#energy').value)};
      if (!row.name || !Number.isFinite(row.grams) || !Number.isFinite(row.energy)
          || row.grams < 0 || row.energy < 0) return;
      if (form.dataset.edit !== undefined) meals[Number(form.dataset.edit)] = row;
      else meals.push(row);
      delete form.dataset.edit; form.reset(); save();
    };
    render();
''')

CALORIES_HTML = source('''
    <!doctype html><html lang="en"><meta charset="utf-8"><title>Calories</title>
    <link rel="stylesheet" href="style.css"><main><h1>Calories</h1>
    <form><label>Name<input id="name" required></label>
    <label>Grams<input id="grams" type="number" min="0" step="any" required></label>
    <label>kcal/100g<input id="energy" type="number" min="0" step="any" required></label>
    <button>Save meal</button></form><output id="total"></output><ul id="meals"></ul>
    </main><script src="app.js"></script></html>
''')


def project_files(kind):
    calendar = kind == "calendar"
    js = CALENDAR_JS if calendar else CALORIES_JS
    if calendar:
        js = js.replace("JSON.parse(localStorage.getItem('events') || '{}')", "{}")
        js = js.replace(
            "function save() { localStorage.setItem('events', JSON.stringify(events)); render(); }",
            "async function save(payload) { events = await request(payload); render(); }")
        js = js.replace("events[date] = title; save();", "save({date, title});")
        js = js.replace("delete events[document.querySelector('#date').value]; save();",
                        "save({date: document.querySelector('#date').value, delete: true});")
        dispatch = source('''
            from calendar_app import Events


            def dispatch(payload):
                events = Events("events.json")
                if payload is not None:
                    if payload.get("delete"):
                        events.delete(payload["date"])
                    else:
                        events.put(payload["date"], payload["title"])
                return events.data
        ''')
    else:
        js = js.replace("JSON.parse(localStorage.getItem('meals') || '[]')", "[]")
        js = js.replace("meals.splice(i, 1); save();", "save({identifier: row.id, delete: true});")
        js = js.replace(
            "function save() { localStorage.setItem('meals', JSON.stringify(meals)); render(); }",
            "async function save(payload) { meals = await request(payload); render(); }")
        js = js.replace("if (form.dataset.edit !== undefined) "
                        "meals[Number(form.dataset.edit)] = row;",
                        "if (form.dataset.edit !== undefined) "
                        "row.identifier = meals[Number(form.dataset.edit)].id;")
        js = js.replace("else meals.push(row);", "save(row);")
        js = js.replace("delete form.dataset.edit; form.reset(); save();",
                        "delete form.dataset.edit; form.reset();")
        dispatch = source('''
            from calories import Calories


            def dispatch(payload):
                food = Calories("meals.sqlite3")
                try:
                    if payload is not None:
                        identifier = payload.get("identifier")
                        if payload.get("delete"):
                            food.delete(identifier)
                        else:
                            food.put(payload["name"], payload["grams"], payload["energy"],
                                     identifier)
                    return [{"id": r[0], "name": r[1], "grams": r[2], "energy": r[3]}
                            for r in food.rows()]
                finally:
                    food.close()
        ''')
    variable = "events" if calendar else "meals"
    js += source('''
        async function request(payload) {
          const options = payload === undefined ? {} : {method: 'POST',
            headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)};
          const response = await fetch('/api', options);
          if (!response.ok) throw new Error(await response.text());
          return response.json();
        }
    ''') + f"request().then(data => {{ {variable} = data; render(); }});\n"
    return {
        "calendar_app.py" if calendar else "calories.py": CALENDAR_PY if calendar else CALORIES_PY,
        f"test_{kind}.py": CALENDAR_TEST if calendar else CALORIES_TEST,
        "index.html": CALENDAR_HTML if calendar else CALORIES_HTML,
        "app.js": js,
        "server.py": SERVER_PY,
        "storage.py": dispatch,
        "style.css": "body {font-family: sans-serif; max-width: 60rem; margin: auto;}\n"
                     "#days {display: grid; grid-template-columns: repeat(7, 1fr); gap: .5rem;}\n",
        "README.md": "# Offline example\nRun python server.py and open localhost:8000.\n"
                     "Browser CRUD uses Python JSON/SQLite storage through /api.\n"
                     "pytest checks domain behavior, not browser interactions.\n",
    }


SERVER_PY = source('''
    import json
    from http.server import HTTPServer, SimpleHTTPRequestHandler

    from storage import dispatch


    class Handler(SimpleHTTPRequestHandler):
        def api(self, payload=None):
            try:
                content = json.dumps(dispatch(payload)).encode()
                self.send_response(200)
            except (ValueError, KeyError, TypeError):
                content = b'{"error": "invalid input"}'
                self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self):
            if self.path == "/api":
                self.api()
            elif self.path in ("/", "/index.html", "/style.css", "/app.js"):
                super().do_GET()
            else:
                self.send_error(404)

        def do_POST(self):
            if self.path != "/api":
                self.send_error(404)
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size < 10000:
                    raise ValueError("invalid length")
                payload = json.loads(self.rfile.read(size))
            except ValueError:
                self.send_error(400)
                return
            self.api(payload)


    if __name__ == "__main__":
        HTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
''')


class BuilderAdapter(FakeModelAdapter):
    def __init__(self, files):
        super().__init__()
        self.files = files

    def generate(self, request):
        if request.agent_role == "coder":
            self._structured = {
                "files": [{"path": path, "operation": "create", "new_content": content,
                           "rationale": "Offline functional fixture"}
                          for path, content in self.files.items()],
                "rationale": "Offline fixture; browser behavior needs browser checks",
            }
        else:
            assert request.agent_role == "reviewer"
            self._structured = {"decision": "accept", "findings": [], "required_fixes": [],
                                "summary": "Fixture accepted; pytest covers domain behavior only"}
        return super().generate(request)


@pytest.mark.parametrize("kind", ["calendar", "calories"])
@pytest.mark.parametrize("oversized", [False, True])
def test_real_graph_builds_offline_project_with_gates_and_promotion(
    tmp_path, monkeypatch, kind, oversized,
):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=Test", "-c",
                    "user.email=test@localhost", "commit", "--allow-empty", "-qm", "initial"],
                   check=True, capture_output=True)
    files = project_files(kind)
    assert len(files) <= Scope(repo_path=str(repo)).max_files_changed
    assert sum(nodes._contar_lineas(content) for content in files.values()) <= 400
    if oversized:
        files["oversized.py"] = "# implementation\n" * 401
    adapter = BuilderAdapter(files)
    monkeypatch.setattr(model_routing, "gateway_from_settings",
                        lambda _: ModelGateway([adapter]))
    settings = Settings(_env_file=None, profile_id="builder-test",
                        remote_model_roles=["coder", "reviewer"],
                        workspace_root=tmp_path / "worktrees",
                        allowed_test_targets=["pytest.unit", "ruff.check"])
    with RunStore(tmp_path / "state.sqlite3") as store:
        engine = RunEngine(store, settings=settings)
        state = engine.crear_estado(f"Construye {kind} con persistencia y pruebas",
                                   options=RunOptions(repo_path=str(repo)))
        requirements = engine.start(state)
        assert requirements.status == "awaiting_human_requirements_confirmation"
        assert adapter.calls == []
        approval = engine.resume(state.run_id, "approved")
        if oversized:
            assert approval.status == "needs_human", approval.errors
            assert any(error.error_class == "SCOPE_TRIMMED" for error in approval.errors)
            assert approval.evidence.test_runs == []
            assert approval.artifacts.worktree_path is None
            assert approval.outputs.reviewer_output is None
            assert not (repo / "index.html").exists()
            assert any(file.path == f"test_{kind}.py"
                       for file in approval.outputs.code_proposal.files)
            return
        assert approval.status == "awaiting_approval", approval.errors
        assert {run.target for run in approval.evidence.test_runs} == {"pytest.unit", "ruff.check"}
        assert all(run.exit_code == 0 for run in approval.evidence.test_runs), [
            run.stdout + run.stderr for run in approval.evidence.test_runs]
        assert approval.outputs.reviewer_output.decision == "accept"
        assert not (repo / "index.html").exists()
        for changed in approval.artifacts.changed_files:
            expected = hashlib.sha256(files[changed.path].encode()).hexdigest()
            assert changed.sha256 == expected
        completed = engine.resume(state.run_id, "approved")
        assert completed.status == "completed", completed.errors
        approved_hash = approval.outputs.coder_output.diff_sha256
        assert completed.approvals[-1].content_sha256 == approved_hash
        assert approved_hash == hashlib.sha256(
            approval.outputs.coder_output.diff.encode()).hexdigest()
        for path, content in files.items():
            assert (repo / path).read_text(encoding="utf-8") == content
        assert {call.agent_role for call in adapter.calls} == {"coder", "reviewer"}
        kinds = [event.kind for event in store.events(state.run_id)]
        assert kinds.count("test_target_completed") == 2


@pytest.mark.parametrize("limit", ["files", "lines"])
def test_limits_keep_both_test_names_before_implementation_with_stable_order(limit):
    files = {"main.py": "x\n" * 5, "test_root.py": "x\n", "ui.js": "x\n" * 5,
             "nested/store_test.py": "x\n"}
    proposal = CodeProposal.model_validate({"files": [
        {"path": path, "operation": "create", "new_content": content, "rationale": "r"}
        for path, content in files.items()], "rationale": "r"})
    scope = Scope(repo_path="/repo", max_files_changed=2 if limit == "files" else 10,
                  max_lines_changed=2 if limit == "lines" else 400)
    trimmed, warning = nodes._respetar_limites(proposal, scope)
    assert [file.path for file in trimmed.files] == ["test_root.py", "nested/store_test.py"]
    assert warning and "main.py" in warning and "ui.js" in warning
    assert trimmed.rationale == proposal.rationale


def test_offline_prompts_keep_independent_review_and_semantic_validation():
    for extension in (".html", ".css", ".js", ".mjs", ".ts", ".tsx", ".jsx", ".sql"):
        assert extension in nodes._EXTENSIONES
    for prompt in (nodes.PROMPT_CODIFICACION, nodes.PROMPT_PLANIFICACION):
        assert "SQLite" in prompt and "pytest" in prompt and "http.server" in prompt
    assert 'DEBE ser `"accept"`' not in nodes.PROMPT_REVISION
    assert "revision independiente" in nodes.PROMPT_REVISION
    assert "No apruebes con pruebas en rojo" in nodes.PROMPT_REVISION
    assert "incluso con `exit 0`" in nodes.PROMPT_REVISION


def test_test_priority_still_obeys_hard_limits():
    proposal = CodeProposal.model_validate({"files": [
        {"path": path, "operation": "create", "new_content": "x\n" * 3, "rationale": "r"}
        for path in ("test_first.py", "nested/second_test.py")], "rationale": "r"})
    trimmed, warning = nodes._respetar_limites(
        proposal, Scope(repo_path="/repo", max_files_changed=1, max_lines_changed=2))
    assert trimmed.files == []
    assert "test_first.py" in warning and "nested/second_test.py" in warning


def test_researcher_reads_web_and_database_sources(tmp_path):
    paths = [f"source{extension}" for extension in
             (".html", ".css", ".js", ".mjs", ".ts", ".tsx", ".jsx", ".sql")]
    for path in paths:
        (tmp_path / path).write_text(f"evidence for {path}\n", encoding="utf-8")
    with RunStore(tmp_path / "state.sqlite3") as store:
        state = RunEngine(store).crear_estado(
            "Analiza los archivos", options=RunOptions(repo_path=str(tmp_path)))
    delta = nodes.researcher(state)
    assert set(delta["outputs"].researcher_output.files_read) == set(paths)
    assert all(finding.evidence.startswith("evidence for")
               for finding in delta["evidence"].findings)

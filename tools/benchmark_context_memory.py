"""Offline paired measurement of real Researcher/Coder requests on synthetic repositories."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from ai_swe.config import Settings
from ai_swe.contracts import Instruction, RunOptions, RunState
from ai_swe.graph import model_routing, nodes
from ai_swe.models import FakeModelAdapter, ModelGateway
from ai_swe.state.memory_graph import FileMemoryGraph


def measure(directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    cases = []
    for product, query in [
        ("calculator", "Modifica src/calculator.py"),
        ("calendar", "Modifica src/calendar.py"),
        ("calories", "Modifica src/calories.py"),
        ("agenda", "Mejora la organización de mis citas"),
        ("operations", "El cálculo de la tangente da error"),
        ("actions", "El botón guardar no responde"),
    ]:
        repo = directory / product
        repo.mkdir()
        relevant = [f"src/{product}.py", f"tests/test_{product}.py"]
        paths = [f"a_noise_{i:02}.py" for i in range(22)] + relevant
        for index, name in enumerate(paths):
            path = repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                f"# Synthetic module {index}: local fixture, no dependencies.\nvalue = 1\n",
                encoding="utf-8",
            )
        fragment = {
            "agenda": "def registrar(citas, evento):\n    citas.append(evento)",
            "operations": "def tangente(angle):\n    return math.tan(angle)",
            "actions": "def guardar(documento):\n    return documento.copy()",
        }.get(product, "def calculate(value):\n    return value + 1")
        (repo / relevant[0]).write_text(fragment + "\n", encoding="utf-8")
        (repo / relevant[1]).write_text(
            "def test_result():\n    assert 1 + 1 == 2\n", encoding="utf-8"
        )
        arms = {}
        for arm in ("bounded_baseline", "content_only", "associative"):
            settings = Settings(
                _env_file=None,
                state_db_path=directory / f"{product}-{arm}.sqlite3",
                remote_model_roles=[],
                allowed_test_targets=[],
            )
            if arm == "associative":
                FileMemoryGraph(settings.state_db_path).observe(
                    str(repo), relevant, observation="synthetic-coedit"
                )
            now = datetime(2026, 10, 30, tzinfo=UTC)
            state = RunState(
                run_id="context-benchmark",
                trace_id="context-benchmark",
                created_at=now,
                updated_at=now,
                instruction=Instruction(text=query, source="text", confirmed_by_user=True),
                options=RunOptions(repo_path=str(repo)),
            )
            research = model_routing.bind_settings_node(nodes.researcher, settings)
            if arm == "bounded_baseline":
                # Controlled ablation, not a production setting; keep the same 20-file safety cap.
                with patch.object(
                    FileMemoryGraph,
                    "select",
                    lambda self, repository, query, candidates: sorted(candidates),
                ):
                    findings = research(state)
            else:
                findings = research(state)
            state = state.model_copy(update=findings)
            adapter = FakeModelAdapter(structured={"files": [], "rationale": "Offline measurement"})
            with patch.object(
                model_routing, "gateway_for_node", return_value=ModelGateway([adapter])
            ):
                model_routing.bind_settings_node(nodes._coder_del_modelo, settings)(state)
            assert len(adapter.calls) == 1
            request = adapter.calls[0]
            encoded = request.model_dump_json().encode()
            selected = state.outputs.researcher_output.files_read
            arms[arm] = {
                "selected_files": selected,
                "code_body_received": fragment in "\n".join(m.content for m in request.messages),
                "required_file_recall": len(set(selected) & set(relevant)) / len(relevant),
                "message_utf8_bytes": sum(len(m.content.encode()) for m in request.messages),
                "request_utf8_bytes": len(encoded),
                "conservative_reservation_units": len(encoded) + 1024,
                "request_sha256": hashlib.sha256(encoded).hexdigest(),
            }
        baseline = arms["bounded_baseline"]
        for metrics in arms.values():
            metrics["message_byte_reduction"] = (
                1 - metrics["message_utf8_bytes"] / baseline["message_utf8_bytes"]
            )
        cases.append(
            {"product": product, "query": query, "candidate_files": len(paths), "arms": arms}
        )
    return {
        "offline": True,
        "paid_calls": 0,
        "adapter": "FakeModelAdapter",
        "tokenizer": None,
        "billed_token_savings_measured": False,
        "note": "Bytes/reservation units are not measured model tokens or billed savings. "
        "Recall uses a synthetic oracle, not model-generated code quality.",
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        parser.error("Use a new report path")
    with tempfile.TemporaryDirectory(prefix="context-memory-") as temporary:
        report = measure(Path(temporary))
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)
    for case in report["cases"]:
        arm = case["arms"]["associative"]
        print(
            case["product"],
            f"message bytes: {arm['message_byte_reduction']:.1%} reduction; "
            f"required-file recall: {arm['required_file_recall']:.0%}",
        )


if __name__ == "__main__":
    main()

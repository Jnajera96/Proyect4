"""Test-only factory: real app/graph/checkpoints, deterministic proposal, no network."""

from ai_swe.api.app import crear_app
from ai_swe.graph import nodes
from ai_swe.models import FakeModelAdapter, ModelGateway


def factory():
    nodes.usar_gateway(ModelGateway([FakeModelAdapter(structured={
        "files": [{"path": "src/app.py", "operation": "modify",
                   "new_content": "def f():\n    return 42\n",
                   "rationale": "corrige el retorno"}],
        "rationale": "propuesta determinista de verificacion",
    })]))
    return crear_app()

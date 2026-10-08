# 01 — Architecture

> **Capa de índice.** Alias de nomenclatura. El contenido canónico vive en los
> documentos enlazados; este fichero **no los duplica** para que no haya dos
> fuentes que se desincronicen.

## Documentos

| Documento | Qué contiene |
|---|---|
| [`01-arquitectura.md`](01-arquitectura.md) | Diseño original (M0): componentes, decisiones `DEC-xx`, requisitos `RF-xx`/`RNF-xx`. **Aviso `SUPERSEDED` parcial**: su información de *estado* puede estar desactualizada; el diseño sigue vigente |
| [`auditoria-2026-10-06/02_ARQUITECTURA_ACTUAL.md`](auditoria-2026-10-06/02_ARQUITECTURA_ACTUAL.md) | Arquitectura **implementada**, con diagrama Mermaid |
| [`auditoria-2026-10-06/03_ARQUITECTURA_OBJETIVO.md`](auditoria-2026-10-06/03_ARQUITECTURA_OBJETIVO.md) | Arquitectura objetivo hacia M2+ |
| [`03-flujo-e-implementacion.md`](03-flujo-e-implementacion.md) | Flujo de ejecución y plan de fases (registro histórico de M1) |
| [`diagrama-arquitectura.svg`](diagrama-arquitectura.svg) / `.png` | Diagrama generado por `tools/build_diagram.py`, con validación geométrica en código |

## La arquitectura en una vista

```
START → interpret ─┬→ explain_limits → finalize
                   └→ plan ─→ researcher ─→ (siguiente subtarea | finalize)
                                   coder ─→ apply_sandbox ─→ run_tests ─→ reviewer
                                                                              ├→ coder (ciclo acotado)
                                                                              ├→ escalate
                                                                              └→ mark_awaiting → approval_gate → finalize
```

Invariantes que la **forma del grafo** hace cumplir por sí misma:

- **Solo el Coder lleva a escritura.** No hay arista desde `researcher` ni desde
  `reviewer` hacia un nodo con efectos.
- **Toda promoción pasa por la puerta de aprobación.**
- **El ciclo de revisión está acotado** por `max_review_cycles`.
- **El plan es dato, no topología:** las aristas están escritas a mano y nunca se
  generan desde el plan, así que ningún plan circular puede crear un bucle.

La topología exacta está en [`src/ai_swe/graph/workflow.py`](../src/ai_swe/graph/workflow.py),
que es la fuente de verdad. Este documento la resume; el código la define.

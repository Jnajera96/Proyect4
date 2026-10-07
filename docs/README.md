# Índice de documentación

Este directorio contiene **dos capas** de documentación con propósitos distintos.
No son alternativas: la primera describe **qué existe y funciona hoy**, la segunda
describe **el diseño y el porqué**.

---

## Capa 1 — Estado real y plan (VIGENTE)

**`auditoria-2026-10-06/`** — conjunto derivado de la auditoría técnica externa de
solo lectura del 2026-10-06. Es la **fuente de verdad sobre el estado**.

| Documento | Contenido |
|---|---|
| `_PROCEDENCIA.txt` | Origen, jerarquía de evidencia aplicada y regla de reconciliación |
| `00_ESTADO_ACTUAL.md` | Qué está verificado, qué es parcial, qué no existe |
| `01_ESTRUCTURA_PROYECTO.md` | Árbol real del proyecto |
| `02_ARQUITECTURA_ACTUAL.md` | Arquitectura implementada (Mermaid) |
| `03_ARQUITECTURA_OBJETIVO.md` | Arquitectura objetivo hacia M2+ (Mermaid) |
| `04_CONTRATOS_STATE_BUDGET.md` | Reglas de contratos, `RunState` y `Budget` |
| `05_INSTRUCCIONES_AGENTE_DESARROLLO.md` | Reglas para el desarrollo de M2 |
| `06_MODEL_GATEWAY_M2.md` | Frontera única con proveedores de modelo |
| `07_AGENTES_M2.md` | Definición de cada agente de M2 |
| `08_SEGURIDAD_SANDBOX_TOOLS.md` | Flujo de tool call y HITL obligatorio |
| `09_ROADMAP.md` | Fases F0–F16 |
| `10_EVALUACION_METRICAS.md` | Suite de evaluación y métricas |
| `11_DEFINITION_OF_DONE_M2.md` | Criterio de término de M2 |
| `12_GIT_REPRODUCIBILIDAD.md` | Estado de Git y reproducibilidad |
| `13_PROXIMO_PROMPT_AGENTE.md` | Prompt previsto para iniciar M2 |
| `PROJECT_SNAPSHOT.json` | Snapshot estructurado del estado |
| `UPLOAD_ORDER.md` | Orden de integración del conjunto |

**`AUDITORIA-EXTERNA.md`** — informe completo de la auditoría (50 secciones + 25
preguntas) con toda la evidencia recolectada. Es el origen del conjunto anterior.

**`BASELINE-M1-POST-DOCUMENTACION.md`** — reporte de la sesión de integración
documental: qué se cambió, estado de Git, validaciones ejecutadas y matriz de
preparación para M2.

**`BASELINE-PRE-M2.md`** — acta de cierre de la fase `F1` (reproducibilidad +
hardening de seguridad pre-M2): lockfile, versión de Python, redacción de secretos,
configuración y `Budget`, con el veredicto `READY_FOR_MODEL_GATEWAY`. **Es la
evidencia más reciente del estado de la reproducibilidad y la seguridad.**

**`MODEL-GATEWAY.md`** — referencia de uso del `ModelGateway` (`F2`): contratos,
adapters, errores, retry, fallback, timeout, presupuesto, seguridad, structured
output y cómo añadir un proveedor.

**`MODEL-GATEWAY-DESIGN.md`** — diseño previo a la implementación de `F2`, con las
decisiones y su justificación (por qué síncrono, por qué HTTP y no SDK, por qué el
presupuesto no vive en el gateway).

**`BASELINE-MODEL-GATEWAY.md`** — acta de cierre de `F2`, con el veredicto
`MODEL_GATEWAY_READY`.

---

## Capa 2 — Diseño histórico (M0)

Los documentos `01-*` a `06-*` son la **documentación de diseño original (fase M0)**.
Siguen siendo válidos como diseño y como registro de las decisiones `DEC-xx`.

> ⚠️ **Su información de ESTADO puede estar desactualizada.** Donde un dato de
> estado contradiga la realidad verificada, prevalece `auditoria-2026-10-06/`.
> Los documentos afectados llevan un aviso `SUPERSEDED` en su cabecera.

| Documento | Contenido | Estado del contenido |
|---|---|---|
| `01-arquitectura.md` | Arquitectura, decisiones `DEC-xx`, requisitos `RF-xx`/`RNF-xx` | Diseño vigente; algunas rutas descritas no existen |
| `02-tecnologias.md` | Selección de tecnologías (ocho preguntas por tecnología) | Vigente |
| `03-flujo-e-implementacion.md` | Flujo, plan de fases, resultado de M1 | Vigente; es el registro histórico de M1 |
| `04-defensa.md` | Defensa arquitectónica y preguntas del profesor | Vigente como material de defensa |
| `05-graphify-evaluacion.md` | Evaluación de Graphify como capa de contexto | Propuesta `[PROP]`, no implementada |
| `06-contrato-frontend-backend.md` | Contrato frontend↔backend | Vigente |
| `diagrama-arquitectura.svg` / `.png` | Diagrama generado con validación geométrica | Vigente (generado por `tools/build_diagram.py`) |

---

## Cómo decidir cuál consultar

- **"¿Esto funciona?"** → Capa 1 (`00_ESTADO_ACTUAL.md`).
- **"¿Por qué se decidió así?"** → Capa 2 (`01-arquitectura.md`, decisiones `DEC-xx`).
- **"¿Qué falta y en qué orden?"** → Capa 1 (`09_ROADMAP.md`).
- **"¿Cómo se defiende esto?"** → Capa 2 (`04-defensa.md`).

**Regla ante contradicción:** prevalece el código ejecutable, después los tests, y
solo entonces la documentación. Está desarrollada en `auditoria-2026-10-06/_PROCEDENCIA.txt`.

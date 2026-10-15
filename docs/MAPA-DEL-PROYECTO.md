# Mapa del proyecto y guía de lectura

Fecha: 14 de octubre de 2026. Guía para trabajar por cuenta propia mientras la
productización está pausada. Complementa el índice `docs/README.md`; no sustituye
los documentos canónicos ni convierte los planes en funciones implementadas.

## 1. Estado que conviene tener presente

- **Base funcional:** candidato local de entrega de Fase C, congelado en
  `delivery-rc1` → `2d35a59`. Backend, frontend, gates y promoción E2E verificados.
- **Trabajo actual:** rama `productization/v0.1.0`; preparación parcial del Model
  Lab guardada en `bc5f8a2`. El código del producto no cambió en este checkpoint.
- **Nueva evidencia:** 709 pruebas Python aprobadas, 3 omitidas, cero fallos;
  19 de ellas pertenecen al nuevo laboratorio. Ruff focalizado aprobado.
- **Evidencia anterior de C:** frontend 24 pruebas, navegador 114 comprobaciones y
  promoción 29. No se repitieron en D porque no se modificó el runtime/frontend.
- **Lo nuevo:** notebook, herramientas de laboratorio, casos de evaluación,
  consulta pública de 268 pares modelo/proveedor. No hubo inferencia ni gasto.
- **Lo pendiente:** benchmarks HF reales y selección de routing; integración real
  progresiva; micrófono/STT real; configuración instalada, launcher, EXE,
  instalador, entorno limpio y release final. No hay producto Windows terminado.
- **Seguridad:** prototipo local/single-user; no certificado para producción.
- **Pausa explícita:** no hay reanudación automática ni pruebas pendientes.

Las tres pruebas omitidas son proveedor real, transcripción real y construcción
de un vector de enlace simbólico que Windows no permitió por privilegios.

## 2. Qué leer primero

1. **Este mapa:** orientación, vocabulario y dónde encontrar cada cosa.
2. **`00-PROJECT-BRIEF.md`:** qué problema resuelve el sistema y qué queda fuera.
3. **`01-arquitectura.md` + `03-flujo-e-implementacion.md`:** cómo trabajan las piezas.
4. **`RELEASE-CANDIDATE-PHASE-C.md`:** qué se verificó realmente antes de productizar.
5. **`PRODUCTIZATION-PROGRESS.md` + `MODEL-LAB-REPORT.md`:** trabajo más reciente.
6. **`RESUME-PRODUCTIZATION-v0.1.0.md`:** instrucciones operativas para retomarlo.

Regla práctica: un acta de una fase pasada describe ese momento, no el estado
actual de cada archivo. Auditorías antiguas pueden señalar defectos ya corregidos.
Si hay contradicción, comprobar runtime/tests/código y la evidencia fechada más
reciente. Un plan o una carpeta con nombre prometedor no demuestra implementación.

## 3. Estructura del repositorio

```text
proyecto4-ai-swe/
├── README.md                 entrada general y uso desde fuentes
├── PROJECT_SNAPSHOT.json     estado estructurado y evidencias históricas por fase
├── pyproject.toml / uv.lock  manifiesto Python y resolución reproducible
├── .env.example              nombres de opciones, sin credenciales reales
├── Dockerfile / docker-compose.yml  ejecución en contenedor ya existente
├── src/ai_swe/               backend y lógica del sistema
│   ├── api/                  FastAPI, endpoints y entrega del frontend compilado
│   ├── contracts/            contratos Pydantic de entradas, estado y resultados
│   ├── graph/                LangGraph, nodos, motor y trabajador
│   ├── models/               ModelGateway, adapters, errores, usage y presupuesto
│   ├── state/                SQLite, ejecuciones, proyectos y checkpoints
│   ├── tools/                políticas, parches, pruebas y promoción
│   ├── security/             roles, redacción y contenido no confiable
│   ├── stt/                  interfaz de voz y adapters
│   ├── evaluation/           evaluación experimental controlada single/multi-agent
│   ├── sandbox.py            worktrees Git y confinamiento de rutas
│   ├── config.py             configuración tipada
│   └── mcp/, observability/  reservas de estructura; no integración completa
├── frontend/                React/TypeScript, estilos, componentes y contratos
├── tests/                   suite Python offline y pruebas reales opt-in
├── tools/                   verificadores, exportadores y laboratorio externo
├── notebooks/               interfaz experimental del Model Lab
├── docs/                    diseño, actas, informes, auditoría y archivo histórico
├── var/                     datos/resultados locales; solo JSON concretos versionados
└── _tmp/                    evidencias y repositorios descartables ignorados por Git
```

`.venv`, `frontend/node_modules`, `frontend/dist`, cachés y temporales son artefactos
locales, no documentación ni código fuente que deba editarse. El directorio
`frontend/dist` es una compilación web; no es todavía un paquete Windows.

## 4. Documentos principales y función de cada uno

| Archivo | Para qué sirve | Cómo usarlo |
| --- | --- | --- |
| `../README.md` | Presentación, instalación desde fuentes y uso general | Entrada al proyecto; no tomar todos sus párrafos históricos como acta nueva |
| `../PROJECT_SNAPSHOT.json` | Estado legible por herramientas, fases y resultados | Consultar la sección de la fase correspondiente; no reemplaza evidencia nueva |
| `README.md` | Índice documental oficial | Localizar fuentes canónicas e históricas |
| `00-PROJECT-BRIEF.md` | Problema, objetivos y alcance | Revisar propuesta de valor y requisitos de producto |
| `01-arquitectura.md` | Arquitectura, decisiones DEC, requisitos RF/RNF y métricas MET | Entender decisiones y relaciones; contiene también propuestas futuras |
| `02-tecnologias.md` | Justificación de tecnologías y dependencias | Evaluar por qué se eligió cada componente |
| `03-flujo-e-implementacion.md` | Flujo de ejecución y topología del grafo | Seguir instrucción → requisitos → gates → código → pruebas → promoción |
| `04-defensa.md` | Preguntas y respuestas para defensa académica/técnica | Preparar presentación, explicación y demostración |
| `05-graphify-evaluacion.md` | Evaluación/propuesta de Graphify | Investigación futura; Graphify no está integrado |
| `06-EVALUATION.md` | Resultados experimentales single vs multi-agent | Evidencia del arnés controlado; no prueba modelos HF reales; generado |
| `07-contrato-frontend-backend.md` | Mapeo entre UI, API y datos | Saber qué respalda cada interacción y detectar promesas sin endpoint |
| `MODEL-GATEWAY.md` | Referencia de uso del gateway y sus contratos | Configuración, structured output, errores, retry, fallback y budget |
| `MODEL-GATEWAY-DESIGN.md` | Diseño y razones previas del gateway | Contexto de decisiones; contrastar con implementación vigente |
| `ROADMAP.md` | Secuencia de fases y capacidades futuras | Planificación; el progreso D más nuevo está en PRODUCTIZATION-PROGRESS |
| `diagrama-arquitectura.svg` / `.png` | Representación visual de arquitectura | Se regeneran con `tools/build_diagram.py`; evitar dibujar encima del generado |

## 5. Actas de estabilización y entrega

| Archivo | Qué registra |
| --- | --- |
| `BASELINE-PRE-STABILIZATION.md` | Punto de partida y plan antes de la estabilización |
| `BASELINE-POST-CLEANUP.md` | Limpieza y consolidación documental de aquella fase |
| `BASELINE-CONFIG-CONTRACTS.md` | Correcciones para que contratos y configuración fueran efectivos |
| `BASELINE-LOCAL-HARDENING.md` | Endurecimiento del borde local: límites, headers, hosts, audio y otros controles |
| `BASELINE-PUBLIC-EXPOSURE.md` | Auth/roles y limitaciones pendientes; el título no certifica producción |
| `BASELINE-FRONTEND-DELIVERY.md` | Implementación de Fase B, diseño, semántica de estados y verificaciones de UI |
| `RELEASE-CANDIDATE-PHASE-C.md` | Validación final de C, tres defectos corregidos, promoción real y límites |

Son actas de hechos y resultados fechados. Al avanzar el producto, añadir evidencia
nueva y enlazarla; no reescribir resultados antiguos como si hubieran ocurrido hoy.

## 6. Documentos del trabajo pausado

| Archivo | Función |
| --- | --- |
| `PRODUCTIZATION-PROGRESS.md` | Bitácora breve: qué está hecho, pendiente y por qué se pausó |
| `RESUME-PRODUCTIZATION-v0.1.0.md` | Handoff operativo: rama, herramientas, comandos, gates y siguiente acción |
| `MODEL-LAB-REPORT.md` | Investigación HF, pruebas offline, métricas, reservas y límites del laboratorio |
| `superpowers/plans/2026-10-14-productization-v0.1.0.md` | Plan de ejecución D–J; casillas no equivalen a pruebas superadas |
| `../notebooks/01_HF_AGENT_MODEL_LAB.ipynb` | Interfaz experimental; no es parte del servidor ni guarda outputs |
| `../var/model_lab_results.json` | Snapshot real de catálogo; measurements y routing vacíos hasta medir |
| `../var/evaluation_results.json` | Resultados del experimento previo controlado; diferente del laboratorio HF |

Antes de retomar D faltan dos comprobaciones humanas potenciales: disponibilidad
de HF_TOKEN y autorización económica si no puede demostrarse consumo incluido.
La existencia del token todavía no se comprobó. No guardar secretos en documentos.

## 7. Auditoría `audit/`: función de cada informe

Este conjunto describe una revisión anterior, de octubre de 2026. Sus hallazgos
sirven de contexto y trazabilidad; no todos siguen abiertos tras las correcciones.

| Archivo dentro de audit/ | Función |
| --- | --- |
| `00-EXECUTIVE-AUDIT.md` | Resumen ejecutivo y prioridades de la auditoría |
| `01-FILE-INVENTORY.md` | Inventario explicado de archivos |
| `02-FUNCTIONAL-INVENTORY.md` | Capacidades encontradas y su estado entonces |
| `03-INTERNAL-DEPENDENCY-MAP.md` | Dependencias entre componentes internos |
| `04-CLEANUP-CANDIDATES.md` | Candidatos de limpieza detectados entonces |
| `05-DOCUMENTATION-AUDIT.md` | Coherencia y vacíos documentales |
| `06-BACKEND-API-AUDIT.md` | Revisión de API y backend |
| `07-CONTRACTS-DATA-AUDIT.md` | Revisión de contratos y datos |
| `08-WORKFLOW-AUDIT.md` | Revisión del grafo y flujo |
| `09-AGENT-AUDIT.md` | Responsabilidades/capacidades de agentes |
| `10-MODEL-INFRASTRUCTURE-AUDIT.md` | Infraestructura y abstracción de modelos |
| `11-STT-AUDIT.md` | Estado de speech-to-text |
| `12-TOOLS-POLICY-AUDIT.md` | Herramientas y reglas de autorización |
| `13-SANDBOX-EXECUTION-AUDIT.md` | Worktrees, ejecución y límites de aislamiento |
| `14-TEST-COVERAGE-AUDIT.md` | Cobertura y carencias de pruebas encontradas |
| `15-FRONTEND-AUDIT.md` | Revisión del frontend anterior |
| `16-FRONTEND-BACKEND-MAPPING.md` | Correspondencia de UI con endpoints |
| `17-FRONTEND-CAPABILITY-PLAN.md` | Plan de capacidades frontend de ese momento |
| `18-USER-ACTIONS-REQUIRED.md` | Intervenciones humanas que se estimaron necesarias entonces |
| `19-THREAT-MODEL.md` | Activos, atacantes, fronteras y amenazas |
| `20-SECURITY-RISK-REGISTER.md` | Registro de riesgos y prioridades |
| `21-CYBERSECURITY-MATURITY.md` | Evaluación de madurez de seguridad |
| `22-CYBERSECURITY-HARDENING-PLAN.md` | Propuesta de endurecimiento |
| `23-INFRASTRUCTURE-AUDIT.md` | Infraestructura y despliegue existentes |
| `24-DEPENDENCY-AUDIT.md` | Dependencias y riesgos asociados |
| `25-CONFIGURATION-AUDIT.md` | Configuración y coherencia operativa |
| `26-PERFORMANCE-AUDIT.md` | Observaciones y límites de rendimiento |
| `27-DATA-PRIVACY-AUDIT.md` | Datos, privacidad y exposición |
| `28-FEATURE-GAP-ANALYSIS.md` | Diferencias entre alcance deseado e implementación de entonces |
| `29-PROJECT-COMPLETENESS-MATRIX.md` | Matriz de completitud auditada |
| `30-PROPOSED-CLEAN-ARCHITECTURE.md` | Arquitectura propuesta; no asumirla implementada |
| `31-FRONTEND-FUNCTIONAL-SPEC.md` | Especificación funcional propuesta de UI |
| `32-FRONTEND-DESIGN-READINESS.md` | Preparación para rediseño en aquella revisión |
| `FINAL-PROJECT-AUDIT.md` | Informe maestro que consolida la auditoría |
| `AUDIT-SNAPSHOT.json` | Resumen estructurado de esa auditoría |
| `file-inventory.json` | Inventario técnico legible por herramientas |

## 8. Archivo `history/`

Conservar como evidencia; no usarlo como lista actual de tareas. El catálogo
individual de documentos y sus títulos se encuentra al final de este mapa.

- `BASELINE-*`: actas de M1/F1 y del gateway, Analyst, Supervisor, Coder y sandbox.
- `AUDITORIA-EXTERNA.md`: auditoría externa que originó hallazgos AUD.
- `AUDITORIA-F2-PARA-ARQUITECTO.md`: entrega puntual de la fase de modelos.
- `01-ARCHITECTURE.md` a `05-DECISIONS.md`: documentos antiguos en inglés,
  reemplazados como fuentes canónicas por la documentación actual.
- `DATA-TASKS-FORMAT.md`: formato histórico de tareas.
- `auditoria-2026-10-06/`: paquete original de diagnóstico, objetivos, instrucciones,
  contratos, seguridad, agentes, métricas, reproducibilidad y orden de entrega.

## 9. Archivos técnicos que también documentan contratos

| Archivo/grupo | Función y precaución |
| --- | --- |
| `../pyproject.toml` | Dependencias, extras y configuración pytest/Ruff |
| `../uv.lock` | Versiones reproducibles; se regenera con uv, no editar a mano |
| `../.env.example` | Opciones disponibles; usar valores ficticios, nunca credenciales reales |
| `../frontend/package.json` | Dependencias y comandos de frontend |
| `../frontend/contracts.json` | Contratos exportados del backend; usar exportador, no editar manualmente |
| `../tests/` y `../frontend/tests/` | Propiedades ejecutables del sistema; no son solo ejemplos |
| `../tools/verify_*` | Verificadores de navegador, promoción, voz y mutaciones; leer sus límites |
| `../_tmp/*.xml`, logs y capturas | Evidencias locales de ejecuciones concretas; no prueba universal ni fuentes canónicas |

## 10. Dónde puedes avanzar por tu cuenta

| Si quieres trabajar en… | Punto de partida | Resultado útil |
| --- | --- | --- |
| Objetivos, usuario y alcance | Brief + roadmap | Aclaraciones de requisitos y exclusiones |
| Defensa/presentación | Defensa + arquitectura + acta C | Narrativa, preguntas y guion de demostración |
| Uso e instalación futura | Mapa + progreso + plan G–J | Expectativas del primer arranque y mensajes entendibles |
| Criterios de aceptación | Contrato UI/API + acta C | Casos concretos con resultado esperado y evidencia necesaria |
| Seguridad | Threat model + actas de hardening | Riesgos aceptados y pendientes, diferenciando local de producción |
| Modelos | MODEL-LAB-REPORT | Criterios de calidad por rol; no seleccionar solo por popularidad |
| Observaciones de interfaz | Baseline frontend | Lista de problemas reproducibles con vista, acción y resultado |

Para que tus aportaciones no se mezclen con hechos verificados, registra cada
idea como **propuesta**, **observación reproducida** o **decisión**. Mantén separados
resultado actual y resultado deseado. Puedes editar fuentes de requisitos/defensa
o añadir notas nuevas; evita sobrescribir actas, JSON generados y métricas antiguas.
Al retomar revisaré tus cambios y los incorporaré sin descartarlos.

Los documentos finales PRODUCT-v0.1.0, INSTALLATION-WINDOWS,
REAL-MODEL-VALIDATION, REAL-STT-VALIDATION, PACKAGING-REPORT y
KNOWN-LIMITATIONS-v0.1.0 todavía no existen: pertenecen a fases posteriores.

## 11. Catálogo individual del archivo histórico

Cada fila enlaza el documento conservado y muestra su título original. Su función
es conservar el diagnóstico, decisión, formato o acta de esa fase, no declarar
el estado actual del producto.

| Documento histórico | Contenido/título original |
| --- | --- |
| [01-ARCHITECTURE.md](history/01-ARCHITECTURE.md) | 01 — Architecture |
| [02-CONTRACTS.md](history/02-CONTRACTS.md) | 02 — Contracts |
| [03-SECURITY.md](history/03-SECURITY.md) | 03 — Security |
| [04-ROADMAP.md](history/04-ROADMAP.md) | 04 — Roadmap |
| [05-DECISIONS.md](history/05-DECISIONS.md) | 05 — Decisions (ADR index) |
| [00_ESTADO_ACTUAL.md](history/auditoria-2026-10-06/00_ESTADO_ACTUAL.md) | 00 — Estado actual verificado |
| [01_ESTRUCTURA_PROYECTO.md](history/auditoria-2026-10-06/01_ESTRUCTURA_PROYECTO.md) | 01 — Estructura actual del proyecto |
| [02_ARQUITECTURA_ACTUAL.md](history/auditoria-2026-10-06/02_ARQUITECTURA_ACTUAL.md) | 02 — Arquitectura actual |
| [03_ARQUITECTURA_OBJETIVO.md](history/auditoria-2026-10-06/03_ARQUITECTURA_OBJETIVO.md) | 03 — Arquitectura objetivo |
| [04_CONTRATOS_STATE_BUDGET.md](history/auditoria-2026-10-06/04_CONTRATOS_STATE_BUDGET.md) | 04 — Contratos, State y Budget |
| [05_INSTRUCCIONES_AGENTE_DESARROLLO.md](history/auditoria-2026-10-06/05_INSTRUCCIONES_AGENTE_DESARROLLO.md) | 05 — Instrucciones para el agente de desarrollo |
| [06_MODEL_GATEWAY_M2.md](history/auditoria-2026-10-06/06_MODEL_GATEWAY_M2.md) | 06 — Model Gateway para M2 |
| [07_AGENTES_M2.md](history/auditoria-2026-10-06/07_AGENTES_M2.md) | 07 — Agentes de M2 |
| [08_SEGURIDAD_SANDBOX_TOOLS.md](history/auditoria-2026-10-06/08_SEGURIDAD_SANDBOX_TOOLS.md) | 08 — Seguridad, sandbox y herramientas |
| [09_ROADMAP.md](history/auditoria-2026-10-06/09_ROADMAP.md) | 09 — Roadmap actualizado |
| [10_EVALUACION_METRICAS.md](history/auditoria-2026-10-06/10_EVALUACION_METRICAS.md) | 10 — Evaluación single-agent vs multi-agent |
| [11_DEFINITION_OF_DONE_M2.md](history/auditoria-2026-10-06/11_DEFINITION_OF_DONE_M2.md) | 11 — Definition of Done de M2 |
| [12-bis_PLAN_REPRODUCIBILIDAD.md](history/auditoria-2026-10-06/12-bis_PLAN_REPRODUCIBILIDAD.md) | 12-bis — Plan de reproducibilidad (documento de trabajo) |
| [12_GIT_REPRODUCIBILIDAD.md](history/auditoria-2026-10-06/12_GIT_REPRODUCIBILIDAD.md) | 12 — Git y reproducibilidad |
| [13_PROXIMO_PROMPT_AGENTE.md](history/auditoria-2026-10-06/13_PROXIMO_PROMPT_AGENTE.md) | 13 — Prompt para iniciar M2 |
| [UPLOAD_ORDER.md](history/auditoria-2026-10-06/UPLOAD_ORDER.md) | Orden sugerido de integración |
| [AUDITORIA-EXTERNA.md](history/AUDITORIA-EXTERNA.md) | Auditoría técnica externa — AI Software Engineering System (Proyecto 4) |
| [AUDITORIA-F2-PARA-ARQUITECTO.md](history/AUDITORIA-F2-PARA-ARQUITECTO.md) | Auditoría arquitectónica del estado actual — para el Arquitecto Principal |
| [BASELINE-F3-REQUIREMENTS-ANALYST.md](history/BASELINE-F3-REQUIREMENTS-ANALYST.md) | Baseline de F3 — Requirements Analyst |
| [BASELINE-F4-SUPERVISOR.md](history/BASELINE-F4-SUPERVISOR.md) | Acta de cierre — FASE F4 (Supervisor) |
| [BASELINE-F6-REAL-CODER.md](history/BASELINE-F6-REAL-CODER.md) | Acta de cierre — FASE F6 (The Real Coder) |
| [BASELINE-F7-SANDBOX.md](history/BASELINE-F7-SANDBOX.md) | Acta de cierre — FASE F7 (Sandbox y Aplicacion de Parches) |
| [BASELINE-M1-POST-DOCUMENTACION.md](history/BASELINE-M1-POST-DOCUMENTACION.md) | BASELINE M1 — Reporte post-integración documental |
| [BASELINE-MODEL-GATEWAY.md](history/BASELINE-MODEL-GATEWAY.md) | Baseline del Model Gateway (`F2`) |
| [BASELINE-PRE-M2.md](history/BASELINE-PRE-M2.md) | Baseline pre-M2 — reproducibilidad y hardening de seguridad |
| [DATA-TASKS-FORMAT.md](history/DATA-TASKS-FORMAT.md) | Suite de evaluación |

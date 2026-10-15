# Baseline de frontend para entrega

Fecha: 14 de octubre de 2026, America/Mexico_City. Esta baseline describe el
frontend implementado sobre el backend existente. La validación integral final
de Fase C requiere autorización separada.

## Preservación y cierre de Fase A

- `f095729`: preservación del rediseño pendiente, sin llamarlo completo.
- `245a4a8`: redacción en handlers, última decisión de aprobación, promoción
  basada en resultado terminal/evidencia y subtareas compatibles con el run.
- Los handlers configurados después del arranque requieren repetir la instalación
  idempotente del redactor. No se afirma una garantía sobre handlers no instalados.

## Composición y estructura

React + TypeScript + Vite, sin framework de UI ni nuevas dependencias de producto.
Sidebar con navegación y proyectos reales; topbar de salud, sesión y tema;
contenido principal con siete vistas. El estado de navegación vive en React, sin
router ni URLs de recursos. El tema se mantiene en memoria y permite sistema,
claro u oscuro. Las únicas decoraciones del hero son CSS y SVG locales.

La referencia visual determina composición y jerarquía, no capacidades. Se usan
hero/compositor, cuatro métricas reales, workflow y actividad. No se copian los
nombres, avatar, modelos, porcentajes, búsqueda, notificaciones ni Knowledge Graph
de la imagen. Los roles se distinguen de los modelos; Researcher sigue siendo
determinista. No hay porcentaje de progreso universal: existen ramas y ciclos.

Archivos principales: `App.tsx`, `components/Navegacion.tsx`, `Compositor.tsx`,
`EditorRutas.tsx`, `Icono.tsx`, `DiagramaFlujo.tsx`, `PanelVoz.tsx`,
`VisorDiff.tsx`, `evidencia.tsx`, `hooks/useEventosRun.ts`, `lib/api.ts` y
`views/`. Se conserva el diseño y los controles anteriores, con composición nueva.

## Mapeo de capacidades reales

| Vista/control | Fuente |
|---|---|
| Salud, fase, disponibilidad del adaptador | `GET /health` |
| Sidebar y listado de proyectos | `GET /projects` |
| Registro y detalle de proyecto | `POST /projects`, `GET /projects/{id}` |
| Compositor y editor de alcance | `POST /runs`, `options.allowed_paths`, `protected_paths` |
| Historial | `GET /runs` |
| Detalle, plan, investigación, diff, pruebas, revisor | `GET /runs/{id}` |
| Actividad | SSE `GET /runs/{id}/events` |
| Requisitos | `POST /runs/{id}/confirm-requirements` |
| Decisión sobre cambios | `POST /runs/{id}/approve` |
| Presupuesto, aprobaciones, errores e informe final | Campos reales de `RunState` |
| Dictado | `POST /transcriptions`, después confirmación y creación explícita |

Proyectos utiliza una página por defecto del servidor; ejecuciones solicita
hasta 200 con fallback al límite por defecto. Las etiquetas no afirman totalidad.
`RunSummary` no contiene instrucción ni project_id: esos datos se consultan en el
detalle. No se inventan columnas ni se realizan cientos de fetches para aparentarlos.

## Estados y evidencia

- El workflow utiliza estado global, `next_step`, salidas, evidencia y última
  decisión relevante. Aprobar autoriza, no demuestra promoción exitosa.
- Se exige estado completado, informe de cambios aplicados y ausencia de errores
  de promoción para mostrar promoción completada. `PROMOTION_FAILED` es fallo.
- Una prueba vigente fallida marca la etapa fallida aunque otro objetivo pase;
  se toma el último intento por target. El listado conserva todos los intentos.
- No hay campo de test skipped: no se inventa. PASS/FAIL se deriva de exit_code.
- El índice de plan solo marca actividad con run running y siguiente paso
  compatible. `Subtask.status/attempts` siguen sin actualización completa del backend.
- La timeline muestra los hitos recibidos, con sus timestamps, sin horas creadas.
  Es un resumen del primer hito por tipo, no una vista del log crudo completo.
- `max_cost=null` significa ausencia de límite monetario. Un acumulado cero es
  ambiguo y se presenta como coste no disponible. Uno positivo se etiqueta como
  registrado y potencialmente parcial. No se inventa moneda.
- `elapsed_seconds` no se presenta como cronómetro real. Se muestra el límite
  de tiempo. Una duración global fiable necesita medición adicional del backend.

## Autenticación, voz y seguridad

API key en memoria, input password, máscara y ausencia de persistencia propia.
401 borra la credencial y devuelve al acceso. 403 conserva la sesión y comunica
permiso insuficiente, también si la UI pasa a solo lectura. El rol se aprende de
un rechazo real; no existe endpoint de identidad. El servidor conserva la autoridad
sobre los permisos. Logout solo borra la credencial local, no revoca la API key.

SSE conserva autenticación por query y utiliza cursores de eventos para continuar
entre puertas. **TD-02 sigue pendiente:** reemplazar la API key de query por un
ticket de un uso. La UI no presenta la URL ni la clave completa.

Voz: archivo o micrófono → transcripción → revisión editable → confirmación →
compositor → ejecutar explícitamente. Confirmar texto no crea un run. Una edición
manual posterior elimina la procedencia dictada. STT disponible significa lo que
`/health` comprueba del adaptador, no que haya un modelo cargado ni GPU preparada.

Se declara confinamiento de escritura en worktree, no aislamiento completo de
procesos, red o recursos. No se añade una afirmación global de "Safety Passed".
La UI presenta incidencias registradas de política, presupuesto y fallback.

## Accesibilidad y responsive

Botones nativos dentro del historial, foco visible, navegación etiquetada, salto
al contenido, labels de campos y chips de rutas removibles con nombre accesible.
El drawer móvil se abre con botón y se cierra con Escape, devolviendo el foco.
Los errores usan alert y las cargas status; se respeta prefers-reduced-motion.

Desktop mantiene sidebar y workflow en tarjetas horizontales; a 1024–1279 la
sidebar es compacta; por debajo de 1024 se usa menú. En móvil el workflow es
vertical y las tablas tienen scroll local, sin desborde global.

Tamaños comprobados: 1920×1080, 1440×900, 1366×768, 1024×768, 834×1112 y
390×844. La comprobación focalizada de contraste no equivale a una certificación
WCAG completa ni a una auditoría con lector de pantalla.

## Verificación reproducible

Se usa `.venv` creado por `uv sync --frozen --extra dev --python 3.13
--no-python-downloads`, con dependencias existentes del lock, sin paquetes globales
ni descarga de modelos. Playwright usa el runtime disponible y Chromium instalado.

Comandos desde la raíz, salvo donde se indica:

```text
node --test frontend/tests/estados.test.mjs
npm --prefix frontend run typecheck
npm --prefix frontend run build
.venv/Scripts/python.exe -B -m pytest tests/test_redaction.py tests/test_logging_output.py tests/test_auth.py -q -p no:cacheprovider
.venv/Scripts/python.exe -B tools/verify_frontend.py
.venv/Scripts/python.exe -B tools/verify_frontend.py --auth
.venv/Scripts/python.exe -B tools/verify_voz.py
node tools/verify_delivery.cjs
.venv/Scripts/python.exe -B tools/verify_delivery_mutations.py
```

El test de componentes se ejecuta con cwd `frontend` en los verificadores.
Los artefactos de navegador se guardan bajo `_tmp/`, ignorado por Git. Se crea
una base independiente por modo. Los escenarios de aprobación/fallo están
sembrados expresamente para inspección: no tienen checkpoint, y no prueban un
clic exitoso de promoción. Los 401/403 de voz son respuestas de prueba controladas;
el flujo normal usa FastAPI y STT fake reales. Nada de esto se activa en el producto.

Las mutaciones deben compilar y provocar fallo semántico del verificador asignado;
un fallo de compilación o timeout no cuenta. Se compara restauración byte a byte
y se reconstruye dist. Antes de capturas finales se vuelve a construir desde el
fuente restaurado. La suite completa, proveedores reales, STT real y Docker no
forman parte de esta validación focalizada de Fase B.

## JUPYTER / HUGGING FACE AGENT MODEL LAB

**Estado: PLANNED.** No hay notebook, endpoint, pantalla ni resultados simulados.

Laboratorio externo para descubrir candidatos y proveedores en Hugging Face,
comparar structured output, tool calling, contexto, latencia, tokens, coste fiable,
errores y fallbacks por Requirements Analyst, Supervisor, Coder y Reviewer.
Researcher solo se incorporará si posteriormente utiliza un modelo.

Modalidades futuras: Inference Providers remotos desde Jupyter, o cloud GPU
(Colab/Kaggle/JupyterHub/VM) con modelos del Hub y transformers/PyTorch. HF_TOKEN
se obtiene del entorno o secretos del notebook; nunca se incluye en fuentes ni
outputs. Exportación futura de resultados JSON reproducibles y recomendación de
routing para ModelGateway. Primero se prueba OpenAICompatibleAdapter; otro adapter
solo se justifica por incompatibilidad demostrada.

Arquitectura: runtime local independiente + experimentación Jupyter/Hugging Face.
El producto debe funcionar si el notebook o la GPU cloud se apagan. Entregables
futuros: `notebooks/01_HF_AGENT_MODEL_LAB.ipynb`, `var/model_lab_results.json` y
`docs/MODEL-LAB-REPORT.md`. Registrado también en arquitectura y ROADMAP.md.

## Deuda restante

- **Pre-delivery:** Fase C integral autorizada por separado; ensayo final de
  promoción con checkpoint y repositorio descartable, y revisión humana visual.
- **Post-delivery:** paginación completa, identidad tipada, medición global de
  duración/disponibilidad de coste, estados de subtareas y mejoras de observabilidad.
- **Producción:** TD-02, TLS, secretos, auditoría persistente, límites operativos,
  aislamiento de procesos/red/recursos, monitorización, retención y backups.
- **Capacidades ausentes:** MCP, Graphify/Knowledge Graph, integración Langfuse,
  TTS, cancelación funcional, borrado, selector de modelos y Model Lab implementado.

## Resultado final de Fase B — 2026-10-14

| Verificación focalizada | Resultado |
| --- | --- |
| Python: auth, logging y redaction | 84/84 |
| Componentes y contratos frontend | 24/24 |
| TypeScript y build Vite | PASS |
| Navegador existente: local / auth / voz | 17/17 · 24/24 · 20/20 |
| Navegador de entrega: local y auth | 114 comprobaciones PASS |
| Mutaciones semánticas | 6/6 detectadas; restauración y build PASS |
| Ruff: dos herramientas Python nuevas | PASS |

Evidencia local ignorada por Git: `_tmp/frontend-delivery-python.xml`,
`_tmp/delivery-final/1792037206444/report.json` y capturas del mismo directorio;
`_tmp/delivery-mutations-1792035326/report.json`. Las capturas utilizan bases
aisladas de verificación, proveedor fake y STT fake. No prueban micrófono real,
Whisper real ni promoción con checkpoint auténtico. No se ejecutó la Fase C ni
se certifica entrega integral o preparación para producción.

Fase A cerrada en `245a4a8`, sobre baseline preservada `f095729`.

# Handoff para Antigravity — actualización segura y pendientes

Fecha: 31 de octubre de 2026. Rama `feature/v0.2.0-madre-continuity`.
Base del cierre de actualización segura: `203bc70`; el commit de cierre posterior
contiene migraciones, herramientas y resultados. La aprobación se limita al host validado. Comprobar HEAD y árbol antes de modificar, sin retroceder
a una base antigua ni descartar avances.

## Estado que conservar

- Avance estimado: **84/100** hacia Windows local confiable y recuperable,
  ponderación 83,90 en `PROJECT-STATUS-2026-10-30.md`. No es aprobación de producción.
- Entrega canónica: `dist/windows-v0.2.0-rc11/AISWESystem-windows-x64.zip`.
- SHA-256: `e57a3e87e37059f52691e644d0ed741215cd5e50165e019982439739204fee60`.
- **1.050 backend PASS / 4 SKIP**, **38 frontend PASS**, build aprobado,
  **28 pruebas de migración/actualización PASS**, actualización y retorno nativos verificados.
- Smoke rc11 estándar de **14/14 PASS**, sin instrumentación ni plazos abreviados;
  ambos cierres código 0, SQLite/checkpoint persistentes, logs limpios. Los dos
  smokes anteriores de rc8 corregido siguen documentados en su acta.
- No hubo llamadas pagadas ni publicación. Los candidatos anteriores se conservan;
  el rc8 original continúa como evidencia histórica de fallo, no como entrega.

Ya implementado: requisitos universales editables y puertas humanas, readiness,
recuperación SSE, cancelación cooperativa, perfiles/bóveda, recuperación desde acceso,
múltiples rutas de repositorio, memoria de coocurrencia, FTS5 en Coder (3 entradas /
800 caracteres totales redactados y no confiables), modos/rollback, prueba local,
guía final y asistente GitHub. No reimplementar estas piezas por confundir una
validación pendiente con funcionalidad ausente.

## Pendientes priorizados

| Orden | Tipo y trabajo | Referencias | Criterio de cierre |
| --- | --- | --- | --- |
| 1 | Validar recuperación integral por UI entre dos PC | `state/continuity.py`, `api/profiles.py`, `RestaurarPerfil.tsx`, `VistaSesion.tsx`; `PORTABLE-SECOND-PC-PILOT.md` | Exportar perfil de prueba pausado antes de aprobación, importar/reasignar varios repositorios en otra PC y reanudar sin repetir Coder/Reviewer, perder gasto/historial/archivos ni aprobar automáticamente. Probar contraseña errónea, destino ocupado, reinicio, auto-backup y clave de rescate. Registrar versión/hash y Windows/SAC. |
| 2 | Mejorar recuperación de contexto sin coincidencias y suficiencia del código enviado | `state/memory_graph.py`, `state/memory.py`, `graph/nodes.py`; `CONTEXT-MEMORY-MEASUREMENT.md`, `tools/benchmark_context_memory.py` | El fixture ambiguo tiene cobertura 0 %. Hoy Coder recibe extractos del Researcher, no necesariamente el cuerpo de funciones necesario. Reproducir con proyectos nuevos y existentes; mejorar selección/contenido acotado sin diccionario cerrado de tres productos, sin pérdida silenciosa de archivos ni quitar límites/políticas. Medir cobertura y calidad antes de reclamar optimización. |
| 3 | Evaluar utilidad del historial FTS5 y ahorro real de contexto | `_historial_para_coder`, `tests/test_coder_historical_context.py`, benchmark | Casos nuevos/multilenguaje con y sin historial, sin contaminación entre usuario/repositorio ni instrucciones maliciosas. Tokenizer verificado del modelo correcto y mensajes completos; bytes/archivos no son tokens facturados. La medición actual ronda 16 % en fixtures con anclas y 0 % sin ellas; no demuestra 50–70 % de ahorro. |
| 4 | Validar publicación real GitHub | `github_publish.py`, `api/delivery.py`, `PublicarGitHubModal.tsx` | Cuenta y repo de prueba elegidos explícitamente por el usuario; permisos/PAT, commit/push, privacidad, errores y limpieza del secreto. El asistente ya existe y está probado con mocks. No publicar sin autorización concreta. |
| 5 | Validar más productos con modelos reales | `graph/nodes.py`, `models/`, worktrees y guías | Proyectos fuera de calculadora, oráculos funcionales independientes, Reviewer sin aceptación forzada, tests reales y promoción aprobada. FakeModelAdapter acredita flujo/contrato, no calidad de generación. Requiere presupuesto explícito disponible en ledger. |
| 6 | **Cerrado localmente:** actualización/migración y recuperación operativa | `tools/build_windows.py`, `packaging/`, `state/`, `config.py` | Actualizar entre versiones preservando bóvedas/SQLite/ledger; respaldo previo, migraciones probadas, fallo recuperable y retorno de versión sin borrar datos. Matriz Windows/SAC independiente y guía para usuario no técnico. |
| 7 | Implementar aislamiento fuerte antes de producción pública | `tools/runner.py`, `sandbox.py`, políticas y despliegue | Worktree no es aislamiento de procesos/red. Diseñar Runner aislado con límites de recursos/red/archivos y validar ataques; después TLS, secretos, límites operativos, auditoría, backup/restauración y política de datos. No convertir el prototipo local en servicio público sin este cierre. |

Los dos PC y las cuentas externas no se simulan como evidencia real. Se puede
avanzar offline en 2, 3, pruebas de 6 y diseño/pruebas de 7 mientras el usuario
realiza el piloto de 1. No garantizar fechas o porcentaje 100 solo por tests verdes.

## Arranque seguro de trabajo

1. Leer `ROADMAP.md`, `PROJECT-STATUS-2026-10-30.md`,
   `RC8-SHUTDOWN-FTS-CLOSURE.md` y el acta del área elegida.
2. Verificar rama, HEAD, estado y diff. Conservar cambios ajenos; no reset/clean,
   restore global, rebase, push ni tags por iniciativa propia.
3. Reproducir un defecto antes de corregirlo; hacer una entrega acotada con tests
   offline/FakeModelAdapter y actualizar actas. No desmontar LangGraph, contratos
   Pydantic, worktrees ni puertas humanas.
4. Para cambios de fuente nuevos, ejecutar las suites pertinentes y build frontend;
   ampliar a suite completa al cerrar release. Mantener omisiones como SKIP.
5. Crear cada portable en directorio nuevo, preservar anteriores, verificar ZIP
   extraído, manifiesto, CPython firmado, perfiles/reinicio/SQLite y SHA-256.
   `tools/verify_portable_profiles.py` usa Connection: close y tiempos estándar;
   no alargarlos ni usar wrappers para convertir un fallo en aprobado.

## Restricciones y secretos

No copiar `.env`, tokens, bóvedas reales, SQLite reales o logs sensibles al handoff,
ZIP o repositorio. Nunca pedir que se peguen credenciales en el chat. No desactivar
SAC/Defender/AppLocker; usar CPython oficial firmado y dependencias del lockfile.
No añadir binarios sin verificar ni descargar modelos por iniciativa propia.

El límite histórico del laboratorio es 5 USD acumulados, **no 5 USD nuevos**.
Existen reservas inciertas históricas; no liberarlas ni reiniciar el ledger para
habilitar llamadas. Esta sesión solo autoriza pruebas offline. Pedir autorización
concreta de gasto y saldo disponible antes de cualquier inferencia pagada.

No añadir Jupyter/MCP/Graphify/TTS ni grandes refactors como atajos de estos cierres.
La prioridad es calidad, continuidad y seguridad verificables del sistema actual.

### Actualización del pendiente 2 (2026-10-30)

Implementadas búsqueda por contenido y entrega de cuerpos de código al Coder;
consultas sin rutas: cobertura sintética 50% en frío / 100% con asociaciones.
Consultar `CONTEXT-MEMORY-MEASUREMENT.md`. El pendiente restante es evaluar
suficiencia y calidad en repositorios reales diversos; no volver a implementar
la búsqueda ya incorporada ni atribuir a bytes un ahorro de tokens facturados.
Esta actualización es de fuente, no una nueva compilación del portable rc8.

Validación final del punto 2: 993 backend PASS, 4 SKIP, 34 frontend PASS y build
aprobado. Regresión completa en `_tmp/content-context-project-confirmed.xml`;
incidencias y límites documentados en el acta de medición.

### Actualización del pendiente 3 — Evaluación offline

Implementada medición FTS5 con/sin historial en cuatro lenguajes, aislamiento y
entrada maliciosa sintética. 30 pruebas PASS. La nota llega al Coder y añade
~10% de bytes; no afirmar ahorro ni calidad remota. Acta:
`FTS-HISTORY-MEASUREMENT.md`. Quedan tokenizer/revisión exactos y oráculos reales
con presupuesto autorizado. Los pendientes 1, 4 y 5 aún requieren equipo/cuenta o
validación externa; 6 y 7 admiten trabajo offline acotado.

### Entrega rc9 verificada

Fuente `8b1ff87`, 994 backend PASS/4 SKIP, 34 frontend PASS y build,
30 focalizadas, 11 con módulos del ZIP y 14/14 smoke estándar aprobados.
Ambos candidatos se conservan.
Acta vigente: `RC9-CONTEXT-HISTORY-CLOSURE.md`. Avance global estimado: 81/100.

### Prioridad 6 cerrada — actualización segura (31 de octubre)

SchemaMigrator v1/v2/v3, respaldo obligatorio, rollback, CLI portable, reserva
de ejecución y diario de recuperación implementados. 28 pruebas solicitadas PASS;
regresión completa 1.022 PASS/4 SKIP. Actualización real rc9→rc10 y retorno al
snapshot v0 con runtimes firmados, perfil sintético, checkpoint y reserva intactos.
Acta y comandos: `SAFE-UPGRADE-MIGRATIONS.md`. Paquete de esta entrega:
`dist/windows-v0.2.0-safe-upgrade-rc10-verified/AISWESystem-windows-x64.zip`.
Los estados y conteos de rc9 anteriores son históricos; se conserva ese candidato.
La matriz Windows independiente y recuperación por UI entre PC siguen pendientes.

### Medición de tokens con referencias exactas

Tarea denominada Prioridad 4 por el usuario: corresponde al área de memoria/contexto,
no sustituye la publicación real GitHub de la tabla histórica. Contador y benchmark
implementados con tiktoken opcional y vocabularios locales versionados. Ahorro total
cl100k_base 28,293361%, o200k_base 30,075671%; solo código ~66%. Cobertura crítica
100% en tres fixtures, con funciones presentes en sus bloques. 1.030 backend PASS,
4 SKIP, 34 frontend PASS/build. Ver `MEMORY-TOKEN-SAVINGS-EVIDENCE.md`.
Quedan optimización global 40–70%, tokenizer específico del proveedor y calidad real.
No conectar estas referencias/fallback al ledger como si fueran facturación Qwen.
Para reproducir, instalar el extra token-metrics; no se incluye en el runtime
por defecto ni se regenera el portable en esta tarea.


### Rc11 — publicación y borradores

Implementación GitHub reforzada: GET /user, PAT clásico con scope repo, creación
privada/pública en cuenta u organización, commit de archivos permitidos, origin
sin credenciales y push con upstream. Progreso NDJSON real en el modal. La vista
previa de borradores se conserva con hashes y rutas verificados; no autoriza
publicación antes de completar promoción. 1.050 backend PASS/4 SKIP, 38 frontend
PASS/build, 38 focalizadas desde ZIP y smoke estándar 14/14 PASS. Acta:
`RC11-GITHUB-PUBLISH-AND-UNLOCKED-DELIVERY.md`. Rc10 y anteriores se conservan.

La tarea solicitada como Prioridad 3 corresponde a la publicación del pendiente
4 de la tabla histórica. Se cierra implementación/verificación offline, no el
piloto real GitHub: identidad/creación HTTPS simuladas y push real sólo a bare
local descartable. No hubo inferencia pagada ni push al remoto del proyecto.
Quedan publicación real autorizada, continuidad UI entre PC, matriz Windows/SAC,
calidad con modelos reales, meta global 40–70% de tokens y aislamiento fuerte.

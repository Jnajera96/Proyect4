# Handoff para Antigravity — cierre de rc8 y pendientes

Fecha: 30 de octubre de 2026. Rama `feature/v0.2.0-madre-continuity`.
Base del último trabajo: `8adcb0e`; el commit de cierre posterior de esta rama
contiene estos cambios. Comprobar HEAD y árbol antes de modificar, sin retroceder
a una base antigua ni descartar avances.

## Estado que conservar

- Avance estimado: **81/100** hacia Windows local confiable y recuperable,
  ponderación 80,90 en `PROJECT-STATUS-2026-10-30.md`. No es aprobación de producción.
- Entrega canónica: `dist/windows-v0.2.0-operational-rc8-fixed/AISWESystem-windows-x64.zip`.
- SHA-256: `f27bf21c14cb8c47f8c75be52592e70deada90632713c4069cc369300183429b`.
- **990 backend PASS / 4 SKIP**, **34 frontend PASS**, build aprobado,
  **54 focalizadas PASS**, **18 launcher/historial con runtime empaquetado PASS**.
- Dos smokes estándar de **14/14 PASS cada uno**, sin instrumentación ni plazos
  abreviados; cuatro cierres código 0, SQLite/checkpoint persistentes, logs limpios.
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
| 6 | Actualización/migración y recuperación operativa | `tools/build_windows.py`, `packaging/`, `state/`, `config.py` | Actualizar entre versiones preservando bóvedas/SQLite/ledger; respaldo previo, migraciones probadas, fallo recuperable y retorno de versión sin borrar datos. Matriz Windows/SAC independiente y guía para usuario no técnico. |
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

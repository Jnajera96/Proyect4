# 27 — Auditoría de privacidad y datos

> Qué datos del usuario se almacenan, dónde, cuánto tiempo y quién los ve.
> Commit `065db452`.

## 1. Inventario de datos

| # | DATO | ALMACENAMIENTO | RETENCIÓN | ¿SALE A UN PROVEEDOR? | ¿SENSIBLE? | ESTRATEGIA DE BORRADO |
|---|---|---|---|---|---|---|
| 1 | **Instrucción del usuario** (texto) | `var/state.sqlite3` → `runs`, checkpoint; y en `events` | **Indefinida** | **Sí** (va al prompt del modelo) | Media | **Ninguna** |
| 2 | **Requisitos interpretados** (`TaskInterpretation`) | Checkpoint + `runs` | Indefinida | Sí (contexto) | Baja | Ninguna |
| 3 | **Plan** (`RunPlan`) | Checkpoint | Indefinida | Sí (contexto) | Baja | Ninguna |
| 4 | **Código fuente del usuario** (diff, hallazgos) | `RunState.artifacts.diff`, `outputs`, `evidence` | Indefinida | **Sí** (el diff va al prompt del Reviewer) | **Alta** | Ninguna |
| 5 | **Peticiones al modelo** (prompt completo) | **No se persisten** en el estado; pueden ir a logs si `DEBUG` | — | Sí | Media | N/A |
| 6 | **Respuestas del modelo** | Derivadas: `CodeChange`, `ReviewVerdict`, `TaskInterpretation` | Indefinida | N/A | Media | Ninguna |
| 7 | **Audio crudo** | **NUNCA se persiste.** Bytes en memoria → `io.BytesIO` → descartado | 0 | No | **Alta** (biométrico) | N/A (no se guarda) |
| 8 | **Transcripción** | `RunState.instruction.text` (origen `voice`) + `TranscriptMeta` | Indefinida | **Sí** (como instrucción) | **Alta** | Ninguna |
| 9 | **Logs** | stdout; **redactados** por el filtro | La del proceso | No | Media | Rotación externa |
| 10 | **Eventos SSE** | `events` en la BD, **redactados** antes de persistir | Indefinida | No | Media | Ninguna |
| 11 | **Coste y tokens** | `RunState.budget` | Indefinida | No | Baja | Ninguna |
| 12 | **Rutas del sistema de ficheros** | `options.repo_path`, `artifacts.worktree_path` | Indefinida | No | Media (revela estructura) | Ninguna |
| 13 | **Credenciales** | Entorno; `SecretStr` en memoria | La del proceso | **Sí** (al proveedor, en la cabecera) | **Crítica** | N/A |
| 14 | **Aprobaciones** | `RunState.approvals` (actor, fecha, hash) | Indefinida | No | Baja | Ninguna |
| 15 | **Worktrees** | `var/workspaces/<run_id>` | Hasta `finalize` | No | **Alta** (copia del código) | `destruir()` |

## 2. Flujo de datos hacia terceros

```
┌───────────────────────────────────────────────────────────────┐
│ MÁQUINA DEL USUARIO                                           │
│                                                               │
│  instrucción ──┐                                              │
│  ficheros ─────┤                                              │
│  (hallazgos)   ├──► PROMPT ──► PROVEEDOR DEL MODELO           │
│  diff ─────────┘        │       (OpenAI/Anthropic/local)      │
│                         │                                     │
│                         └──► RESPUESTA ──► estado local       │
│                                                               │
│  audio ──► STT LOCAL ──► texto     (el audio NO sale)         │
└───────────────────────────────────────────────────────────────┘
```

**Lo que sale de la máquina: la instrucción, los hallazgos del repositorio y el
diff del cambio.** Es decir, **fragmentos del código del usuario**.

**Lo que NO sale: el audio** (STT local por diseño). Esto es un punto fuerte real y
debe destacarse en la defensa.

## 3. Riesgos de privacidad

| # | Riesgo | Severidad | Evidencia |
|---|---|---|---|
| 1 | **Código del usuario enviado a un proveedor externo** | **MEDIA-ALTA** | El diff y los hallazgos entran en el prompt. Un usuario que trabaje sobre código propietario **debería saberlo** |
| 2 | **Sin política de retención**: los datos se quedan para siempre | MEDIA | Nada se borra; no hay `DELETE` |
| 3 | **Sin aviso al usuario** de que su código va a un tercero | MEDIA | No hay UI ni documento que lo diga |
| 4 | **Sin cifrado en reposo**: `state.sqlite3` en claro | MEDIA | SQLite sin cifrar |
| 5 | **Sin borrado a petición** del usuario | MEDIA | No hay endpoint |
| 6 | **El worktree es una copia del código** en `var/workspaces/` | BAJA | Se limpia en `finalize`, pero **no** en rutas de excepción (`SEC-11`) |
| 7 | Rutas absolutas del sistema en el estado y servidas por la API | BAJA | `repo_path`, `worktree_path` |
| 8 | Transcripción de voz (dato sensible) persistida indefinidamente | MEDIA | Es texto en el estado |
| 9 | Sin registro de acceso | BAJA | No hay auth, así que no hay a quién auditar |

## 4. Lo que está bien

| Control | Evidencia |
|---|---|
| **El audio nunca se persiste** | Adaptador + contrato + API; probado |
| **Redacción de secretos en logs y en eventos** | `security/redaction.py`; mutaciones propias |
| **Sin secretos en el repositorio** | Escaneo negativo; `.env` no versionado |
| **Los prompts no se guardan como tales** | Solo se persisten las salidas derivadas |
| **El sistema funciona sin proveedor** | Un usuario puede usarlo 100 % offline (fallbacks deterministas) |

## 5. Recomendaciones

| Prioridad | Acción |
|---|---|
| P1 | **Avisar en la UI** de que la instrucción, los hallazgos y el diff se envían al proveedor configurado |
| P1 | Documentar qué sale de la máquina (sección de privacidad en `README`) |
| P2 | Política de retención configurable + endpoint de borrado |
| P2 | Cifrado en reposo de `var/state.sqlite3` si se despliega |
| P3 | Purgar rutas absolutas en las respuestas de la API |
| P3 | Borrar el worktree en las rutas de excepción (`SEC-11`) |

## 6. Conclusión

**La privacidad de la voz está resuelta de forma ejemplar**: el STT es local, el audio
nunca se persiste y el contrato impide que llegue al modelo.

**La privacidad del código no está tratada**: el código del usuario viaja al
proveedor del modelo sin que la interfaz lo advierta, y nada se borra nunca. No es
una vulnerabilidad, es una **carencia de diseño de producto** que conviene cerrar
antes de considerar el sistema terminado.

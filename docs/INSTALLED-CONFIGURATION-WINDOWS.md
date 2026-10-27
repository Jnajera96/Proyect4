# G — Configuración instalada para Windows

## Selección del modo

El repositorio conserva el modo `development`: carga `.env` del directorio actual,
SQLite en `var/state.sqlite3` y worktrees en `var/workspaces`, salvo overrides.
No se mueve, copia ni borra información existente durante esta fase.

El modo `installed` se selecciona con `AI_SWE_RUNTIME_MODE=installed` en el entorno
del proceso o mediante el argumento explícito de Settings. Un proceso empaquetado
con `sys.frozen` usa installed por defecto. El launcher/ejecutable es Fase H;
esta fase prepara y prueba su contrato de configuración, no entrega un instalador.

## Rutas externas

| Uso | Predeterminado instalado |
| --- | --- |
| Configuración y secretos | `%LOCALAPPDATA%/AISWESystem/config/.env` |
| SQLite | `%LOCALAPPDATA%/AISWESystem/data/state.sqlite3` |
| Logs | `%LOCALAPPDATA%/AISWESystem/logs/application.log` |
| Worktrees | `%LOCALAPPDATA%/AISWESystem/worktrees` |
| Caché | `%LOCALAPPDATA%/AISWESystem/cache` |
| Pesos STT descargados | `%LOCALAPPDATA%/AISWESystem/cache/speech` |

Settings solo calcula/lee rutas. `load_settings()` prepara directorios; no crea
un archivo de credenciales ni descarga modelos. Los assets/frontend siguen en
el código/bundle. Los logs de `ai_swe` usan rotación de 2 MiB con 3 respaldos,
redacción de secretos y cierre del handler al terminar la sesión de API.
No es una política general de borrado/retención de datos o auditoría de producción.

Se pueden usar rutas absolutas externas con `AI_SWE_STATE_DB_PATH`,
`AI_SWE_WORKSPACE_ROOT`, `AI_SWE_LOG_DIR`, `AI_SWE_CACHE_DIR` y
`AI_SWE_STT_DOWNLOAD_ROOT`. En installed se rechazan rutas relativas.
Las rutas explícitas quedan bajo responsabilidad del operador; no se migran datos.

Precedencia: argumentos explícitos de Settings > entorno del proceso > archivo
externo del usuario > valores predeterminados. Installed no lee `.env` del código
o del directorio de trabajo. `_env_file=None` sigue disponible para pruebas aisladas.
No se cambia el entorno global del proceso para configurar la caché STT: la ruta
se transmite directamente al adaptador perezoso.

## Primer arranque sin proveedor

Sin configuración remota la API inicia, `/health` responde 200, y proyectos,
historial y capacidades locales permanecen disponibles. El nuevo campo aditivo
`provider_configuration` informa:

- `status`: `not_configured`, `offline` o `configured`.
- `remote_enabled`: si se habilitaron roles remotos.
- `missing_fields`: nombres de ajustes que faltan, nunca valores secretos.
- `message`: explicación que la vista general presenta al faltar configuración.
- `credential_validated=false` e `inference_verified=false`: el diagnóstico de
  presencia no consulta el proveedor ni acredita token válido, saldo o inferencia.

`configured` significa únicamente configuración presente; no una conexión probada.
Con roles remotos habilitados y configuración incompleta, POST `/runs` responde
503 antes de encolar o guardar una ejecución. El gateway también rechaza una
credencial ausente para el router HF antes de construir el adaptador. Los endpoints
OpenAI-compatible locales con los alias `ollama`/`vllm` conservan la posibilidad
de operar sin clave. El alias genérico `openai_compatible` exige clave, como el gateway.
Con roles desactivados (`[]`), las ejecuciones deterministas siguen disponibles.

Para habilitar el perfil aceptado se crea/edita el archivo externo y se reinicia
la aplicación. Plantilla explicativa, no credencial real:

```dotenv
AI_SWE_MODEL_PROVIDER=openai_compatible
AI_SWE_MODEL_BASE_URL=https://router.huggingface.co/v1
AI_SWE_MODEL_NAME=Qwen/Qwen2.5-Coder-32B-Instruct:nscale
AI_SWE_REVIEWER_MODEL=Qwen/Qwen2.5-Coder-32B-Instruct:nscale
AI_SWE_REMOTE_MODEL_ROLES=["coder","reviewer"]
HF_TOKEN=PEGAR_TOKEN_PRIVADO_AQUI
AI_SWE_STT_MODEL=small
AI_SWE_STT_LANGUAGE=es
AI_SWE_STT_DEVICE=cpu
AI_SWE_STT_COMPUTE_TYPE=int8
```

`HF_TOKEN` solo sirve de respaldo de `AI_SWE_MODEL_API_KEY` cuando el destino es
exactamente `https://router.huggingface.co/v1`. Una clave explícita tiene prioridad.
No se reutiliza automáticamente el token HF para otro servidor. Se registra en
el redactor, incluso si aún no se usa. El archivo es externo al paquete, no cifrado:
debe quedar en el perfil del usuario con sus permisos habituales de Windows.
No se copió el token existente a esta ubicación ni se activaron roles de pago.
Los precios y presupuestos se configuran según REAL-MODEL-VALIDATION.md; esta
plantilla no autoriza gastos ni renueva el límite acumulado de 3 USD.

## Evidencia

`tests/test_installed_configuration.py`: precedencia y separación de rutas,
proceso frozen, rechazo de overrides relativos, HF limitado a su destino,
logs redactados, caché STT perezosa y primer arranque/API sin proveedor.

`tools/verify_installed_configuration.cjs` comprueba navegador y FastAPI reales con
LOCALAPPDATA temporal: aviso visible, salud y lectura local, carga del perfil externo,
503 sin token y cero runs, SQLite/caché/logs/worktrees fuera del árbol de código.
Requiere frontend construido y Playwright existente; no descarga modelos ni llama
a proveedores. La corrida final está en `_tmp/phase-g-installed-03/report.json`.
Las corridas 01 y 02 se conservaron: detectaron que `openai_compatible` no exigía
credencial para el router HF; se añadió una regresión con ese proveedor real antes
de corregirlo. No se debilitaron gates ni aserciones.

La revisión posterior alineó el diagnóstico del alias genérico con el gateway:
los alias locales sin clave son `ollama`/`vllm`. La primera prueba de compatibilidad
usó incorrectamente el alias genérico; se corrigió para comprobar el contrato local
existente. La prueba histórica del contrato exportado detectó que faltaba actualizar
su generador; se corrigió `tools/export_contracts.py` y se regeneró el JSON,
manteniendo intacta la aserción de sincronización.

No acredita todavía ejecutable, instalador, Windows limpio ni lanzamiento final.

## Resultado de cierre G

Configuración G completada. Suite final: **769 PASS, 3 SKIP, 0 FAIL**, 168.190 s
(`_tmp/phase-g-release-check.xml` del worktree aislado). Son 18 pruebas nuevas de
configuración/integración. TypeScript/build, 24 pruebas de estado del frontend,
Ruff focalizado, sintaxis del verificador y `git diff --check` aprobados.
Se conservaron las advertencias históricas de lint ajenas a los cambios.
La evidencia de navegador consolidada está en `INSTALLED-CONFIGURATION-EVIDENCE.json`.
No se consumió inferencia de pago ni se renovó el presupuesto.

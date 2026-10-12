# 21 — Madurez de ciberseguridad

> Escala: **0** inexistente · **1** inicial · **2** parcial · **3** razonable ·
> **4** robusto · **5** producción madura. Commit `065db452`.

## Puntuación

| Área | Nivel | Justificación |
|---|---|---|
| **Secretos** | **3 / 5** | `SecretStr` + redactor central + filtro de logging + redacción en SSE, con **mutaciones que lo protegen**. Sin gestor de secretos ni rotación. `.env` en disco |
| **Autenticación** | **0 / 5** | **No existe.** Es una decisión declarada (`AUD-06`), mitigada por binding local |
| **Autorización** | **1 / 5** | No hay usuarios ni roles de aplicación. **Sí** hay autorización *de agente* (matriz de permisos por rol) que es excelente, pero no protege el acceso a la API |
| **Validación de entrada** | **3 / 5** | Pydantic en todos los contratos, invariantes cruzados, validación del repositorio en el alta. **Falta**: límite de tamaño en subidas, validación de tipo MIME, tope superior en paginación |
| **Sistema de ficheros** | **4 / 5** | Confinamiento en **4 barreras** con comprobación física, aplicado en el patcher y en el sandbox. Verificado con tests. Un punto por debajo del 5 por la falta de pruebas de escape con symlinks reales en todas las plataformas |
| **Sandbox** | **2 / 5** | Cumple su objetivo declarado (contención de la **escritura**), pero **no aísla el proceso**: sin límites de CPU/memoria/procesos, sin aislamiento de red, sin contenedor |
| **Seguridad de LLM** | **3 / 5** | Salida validada por contrato, catálogo cerrado sin `run_shell`, agencia acotada, guardas deterministas que pueden vetar al modelo. **Sin defensa explícita contra prompt injection indirecta** |
| **Seguridad de API** | **2 / 5** | Errores tipados sin filtrar trazas, binding local, CORS desactivado por defecto. Sin auth, sin rate limiting, sin cabeceras de seguridad, sin `TrustedHost` |
| **Seguridad de frontend** | **4 / 5** | Sin `innerHTML`, sin `dangerouslySetInnerHTML`, sin almacenamiento de tokens, **3 dependencias de runtime**. Sin CSP ni cabeceras |
| **Supply chain** | **3 / 5** | Lockfiles presentes (`uv.lock`, `package-lock.json`), dependencias acotadas con techo de versión mayor, extras opcionales correctamente separados. **`pytest-asyncio` declarado sin uso**; `npm audit`/`pip-audit` no ejecutados |
| **Logging** | **4 / 5** | Filtro de redacción instalado en la app; los secretos se registran en el redactor al cargar ajustes; los eventos SSE se redactan antes de persistir. Sin rotación ni logs estructurados a fichero |
| **Monitorización** | **0 / 5** | `observability/` es un placeholder; `langfuse_*` declarado y nunca leído |
| **Backups** | **0 / 5** | No hay estrategia. La BD es un SQLite local sin copia |
| **Respuesta a incidentes** | **0 / 5** | No hay procedimiento, ni runbook, ni alertas |
| **Despliegue** | **1 / 5** | `Dockerfile` + `docker-compose` existen y son razonables **para desarrollo**, pero el `Dockerfile` abre `0.0.0.0` sin auth y no incluye el frontend. Sin TLS, sin proxy, sin gestor de procesos |
| **Privacidad de datos** | **1 / 5** | El audio no se persiste (bien), pero **no hay política de retención**, ni purga, ni aviso al usuario, ni cifrado de la BD |

## Puntuación global

| Cálculo | Valor |
|---|---|
| Media aritmética | **2,1 / 5** |
| Media de las áreas que importan para **uso local** (secretos, ficheros, LLM, frontend, logging, validación) | **3,5 / 5** |
| Media de las áreas que importan para **producción** (auth, sandbox, API, monitorización, backups, despliegue) | **0,9 / 5** |

## Interpretación

**El proyecto está bien construido para lo que dice ser y mal preparado para lo que
no dice ser.**

- Como **prototipo local de un solo usuario**, la postura de seguridad es
  **razonable**: no hay secretos versionados, no hay `shell=True`, la escritura está
  confinada con cuatro barreras probadas, el catálogo de herramientas no permite
  ejecutar comandos y las decisiones irreversibles exigen un humano.
- Como **producto desplegable**, está en nivel **inicial**: sin autenticación, sin
  aislamiento de ejecución, sin límites de recursos, sin monitorización y sin copias.

**El punto más fuerte** es el eje `Policy Engine + sandbox + catálogo cerrado`: es
una arquitectura de mínimo privilegio real, verificada con tests que afirman los
conjuntos exactos de permisos. Muchos proyectos con autenticación no tienen esa
disciplina.

**El punto más débil** no es un fallo de código, sino una **expectativa**: el nombre
`sandbox` sugiere aislamiento y lo que hay es confinamiento de escritura. Si alguien
despliega creyendo lo primero, el riesgo es alto.

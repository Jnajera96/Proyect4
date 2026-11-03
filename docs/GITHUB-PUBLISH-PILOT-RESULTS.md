# Registro de Resultados — Piloto del Asistente de Publicación GitHub (Día 4)

**Fecha:** 2026-11-03T23:44:14Z  
**Base Git:** `b4e070b746bd349926966b5f35f89cc12701c78c`  
**Entorno:** Python 3.13.14 en Windows-11-10.0.26300-SP0  
**Dictamen:** **APROBADO** (Gasto: **$0.00 USD**, cero fugas de credenciales)

---

## 1. Alcance y Objetivos Evaluados
El asistente de publicación en GitHub permite a los usuarios exportar aplicaciones revisadas y aprobadas a repositorios de GitHub con mínimas fricciones y con salvaguardas de seguridad automáticas:

1. **Gestión Segura de Credenciales (Bóveda DPAPI/AES-256-GCM):**
   - El Personal Access Token (PAT) se almacena cifrado en un sobre sellado con AES-256-GCM y derivación scrypt (`N=32768, r=8, p=1`).
   - El PAT en texto plano nunca se persiste en SQLite, ni en `.git/config`, ni en archivos de configuración.
   - Las expresiones regulares de redacción enmascaran automáticamente el token (`[REDACTED]`) en logs, trazas y mensajes de error HTTP.

2. **Publicación en Repositorio Descartable (`test-ai-swe-disposable`):**
   - Proyecto sintético generado con archivos de código y `README.md`.
   - Secuencia estricta de fases por streaming: `validating` $\rightarrow$ `creating` $\rightarrow$ `uploading` $\rightarrow$ `published`.
   - Solo se publican archivos aprobados formalmente en `state.artifacts.changed_files` y `README.md`.

3. **Aislamiento en Git Push:**
   - La autenticación contra GitHub se inyecta de forma estrictamente efímera mediante la variable `http.https://github.com/.extraHeader` en variables de entorno del subproceso `git push`.
   - Variables globales de Git y scripts de credenciales deshabilitados (`GIT_CONFIG_NOSYSTEM=1`, `GIT_TERMINAL_PROMPT=0`).
   - Protocolo restringido a `https` (`GIT_ALLOW_PROTOCOL=https`).
   - Tras el push, `.git/config` contiene únicamente la URL remota sin rastro alguno del token ni credenciales básicas.

4. **Fronteras y Rechazo de Escenarios Inseguros:**
   - Si el repositorio local ya cuenta con un remoto configurado (`git remote`), la publicación se aborta para impedir sobrescribir repositorios existentes.
   - Si existen cambios no aprobados, archivos `.env`, claves privadas (`.pem`, `.key`) o bases de datos locales (`.sqlite3`), la publicación se deniega antes de cualquier llamada a red.

---

## 2. Resumen de Pruebas Ejecutadas

| Control de Seguridad / Funcionalidad | Resultado | Detalle |
| :--- | :--- | :--- |
| **Cifrado en Bóveda (AES-256-GCM)** | **PASS** | Cifrado y descifrado verificado; token ausente en almacenamiento plano. |
| **Redacción Automática en Logs** | **PASS** | Token `ghp_*` reemplazado por `[REDACTED]` en toda salida textual. |
| **Publicación E2E Proyecto Descartable** | **PASS** | `test-ai-swe-disposable` empaquetado, comiteado y vinculado a remoto. |
| **Progresión por Streaming (Fases)** | **PASS** | Secuencia `validating` $\rightarrow$ `creating` $\rightarrow$ `uploading` $\rightarrow$ `published`. |
| **Inexistencia de Token en `.git/config`** | **PASS** | Archivo `.git/config` inspeccionado: 0 tokens / 0 prefijos filtrados. |
| **Protección contra Remotos Existentes** | **PASS** | Proyectos con remoto previo deniegan sobreescritura automáticamente. |
| **Protección contra Árbol Sucio / Archivos Extra** | **PASS** | Detección inmediata de cambios no aprobados previa a red. |

---

## 3. Verificación de Aislamiento y Costos
- **Gasto de API Facturado:** **$0.00 USD**.
- **Llamadas a LLMs de pago:** **0**.
- **Transportes de Red:** Mock hermético con adaptadores locales.

---

## 4. Conclusión
El Asistente de Publicación en GitHub cumple al 100% las garantías de seguridad, aislamiento de credenciales y protección del espacio de trabajo del usuario establecidas para el Hito v0.2.0.

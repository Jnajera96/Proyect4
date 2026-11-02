# Validación y Entrega del Portable RC20 — Ahorro de Tokens y Consolidación

Fecha: 2 de noviembre de 2026. Base: `8a4030e`.
Entrega: `dist/windows-v0.2.0-rc20-token-savings/AISWESystem-windows-x64.zip`.
SHA-256: `24d9feacb320eaa7f3670fdd582549dcfb7cd8c69add7f88231ef45bc5d4a929`.
Tamaño: 120.749.150 bytes; 4.745 archivos, CRC y hashes del manifiesto verificados.

---

## 1. Alcance y Novedades Consolidadas en RC20

RC20 integra de forma unificada los avances clave implementados tras la línea base rc18/rc19:

1. **Ahorro de Tokens en Mensajes Completos (40–70%):**
   - Compactación de boilerplate fijo en `PROMPT_CODIFICACION`, avisos de seguridad e instrucciones de iteración.
   - Poda asimétrica de contexto e historial FTS5.
   - Resultado medido de forma exacta y 100% offline:
     - `cl100k_base`: **41.185256%** de reducción total en mensajes completos (14,731 → 8,664 tokens).
     - `o200k_base`: **42.379799%** de reducción total en mensajes completos (14,455 → 8,329 tokens).
     - Bloques de código: **66.21%** a **66.43%** de reducción.
     - Suficiencia crítica: **100%** de archivos y anclas funcionales conservadas.
     - Objetivo formal 40–70%: **CUMPLIDO (`True`)**.

2. **Detector Estático de Dependencias por Proyecto:**
   - Análisis AST de imports en código generado sin ejecución.
   - Clasificación en stdlib, local y paquetes externos con mapeo canónico (ej. `yaml` → `pyyaml`, `dotenv` → `python-dotenv`).
   - Política preventiva: escala de inmediato a `DEPENDENCY_UNAVAILABLE` ante dependencias no preinstaladas ni autorizadas, eliminando bucles ciegos de reintento.

3. **Lanzador Local de Borradores ante Escalación:**
   - La interfaz web y `launch_guide.py` habilitan el botón *"▶️ Probar en local ahora"* incluso si una tarea se detiene por intervención humana o ciclos de revisión agotados (`needs_human`).
   - El usuario puede inspeccionar y probar la aplicación directamente sin perder su trabajo.

4. **Confinamiento de Windows Job Object:**
   - Soporte para ejecución en entornos virtuales `.venv` sin rechazos falsos de enlaces Microsoft Store.

---

## 2. Batería de Pruebas y Humo Portable (14/14 PASS)

Se ejecutó la prueba de humo instalada y aislada contra el bundle portable (`verify_portable_profiles.py`):

1. **all manifest hashes match:** PASS (todos los archivos coinciden byte a byte con `BUNDLE-MANIFEST.json`).
2. **no developer state or secrets files:** PASS (sin residuos de `.env`, `.sqlite3`, `.log` o `.gguf`).
3. **installed defaults to profiles:** PASS (el servidor inicia en modo perfil multiusuario aislado).
4. **private API gated before login:** PASS (rutas privadas protegidas antes de la autenticación).
5. **integrated frontend served:** PASS (servido correctamente desde `frontend/dist`).
6. **profile registration with packaged cryptography:** PASS (registro con derivación segura).
7. **empty profile has no global token:** PASS (aislamiento de bóveda por usuario).
8. **packaged graph accepts deterministic run:** PASS (grafo LangGraph operativo dentro del paquete).
9. **human confirmation required:** PASS (requisito de confirmación humana respetado).
10. **graceful packaged shutdown:** PASS (apagado limpio del proceso portable).
11. **encrypted profile login survives restart:** PASS (persistencia tras reinicio).
12. **SQLite and graph checkpoint survive restart:** PASS (checkpoints de LangGraph intactos).
13. **persisted SQLite integrity:** PASS (`PRAGMA integrity_check` = ok).
14. **restart shutdown graceful:** PASS (segundo apagado limpio confirmado).

- **Pruebas de Frontend:** 39 PASS, 0 fallos, build de Vite aprobado.
- **Llamadas a APIs de Pago:** 0 (100% offline).
- **RC18 y RC19:** Conservados como entregas históricas en `dist/`.

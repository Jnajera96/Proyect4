# Especificación y Directiva de Implementación para Codex: UX Intuitiva para No Programadores, Flujo Dual (Local vs. GitHub), Memoria Asociativa tipo Neuromapa y Homologación de Títulos

**Fecha:** 29 de octubre de 2026  
**Rama:** `feature/v0.2.0-madre-continuity`  
**Referencia de Punto Seguro:** `docs/OPERATIONAL-STATUS-2026-10-29.md` (Commit operacional rc2, 909 PASS / 0 FAIL)  
**Objetivo:** Transformar el sistema de una herramienta de nicho para ingenieros de software a una plataforma intuitiva accesible para **usuarios no técnicos**, con separación transparente entre **Modo Local** y **Modo GitHub**, guía ejecutable post-generación ("Qué hacer con tu código"), optimización de contexto y tokens inspirada en el grafo asociativo de **Neuromapa**, y **homologación editorial estricta de mayúsculas/minúsculas en títulos y textos de la interfaz**.

---

## 1. Contexto Operativo y Diagnóstico de Partida

### 1.1 Estado Actual Comprobado (29-Oct-2026)
- **Flujo E2E validado:** Ejecución real `run-b70e76e5abd6` completada con éxito (`"passed": true`, 0 errores).
- **Par de Modelos Óptimo:** 
  - `Coder`: `Qwen/Qwen2.5-Coder-32B-Instruct:nscale`
  - `Reviewer`: `openai/gpt-oss-120b:nscale` (resuelve el problema de falsos negativos de normalización trigonométrica presentes en modelos Qwen puros como revisores).
- **Normalización de Estilo:** `Ruff I001` aplicado en memoria sobre la propuesta antes de escribir a disco, registrando hashes transparentemente.
- **Suite de Pruebas:** 909 PASS, 4 SKIP, 0 FAIL. Frontend con 32 tests de estados y 14 comprobaciones de paquete portable en verde.
- **Punto Débil Detectado por el Profesor:** La interfaz y los conceptos actuales (`worktree`, `diff unified`, `HEAD`, `pytest.unit`, `Ruff I001`, `hash sha256`, `promover parche`) son **excesivamente técnicos y hostiles** para clientes, emprendedores o estudiantes que piden una aplicación sin saber programar.
- **Inconsistencia Visual y Tipográfica:** Existen disparidades en los títulos de la interfaz y encabezados: algunos están completamente en minúsculas (ej. `proyectos registrados`, `identificador`, `historial`), otros con mezclas arbitrarias o mayúsculas sostenidas.

---

## 2. Homologación Tipográfica y Editorial (Capitalización Estándar)

### 2.1 Regla de Oro Editorial (Sentence Case)
Todos los títulos de vistas, secciones, tarjetas, paneles, etiquetas de formularios y opciones de navegación deben seguir la convención estándar en español:
1. **Primera letra en mayúscula y el resto en minúsculas:**
   - ✅ Correcto: *"Agente y ejecución"*, *"Proyectos registrados"*, *"Nuevo proyecto local"*, *"Detalle del proyecto"*, *"Historial de cambios"*, *"Revisión humana"*, *"Configuración de modelos"*.
   - ❌ Incorrecto: *"agente y ejecucion"* (todo en minúsculas), *"Agente Y Ejecución"* (Title Case en inglés), *"PROYECTOS REGISTRADOS"* (mayúsculas innecesarias).
2. **Mayúsculas sostenidas ÚNICAMENTE para siglas y acrónimos reconocidos:**
   - Permitido: `E2E`, `Git`, `GitHub`, `API`, `UI`, `SSE`, `SQLite`, `CLI`, `HTML`, `CSS`, `JS`, `PAT`, `USD`.
3. **Homogeneidad entre Frontend y Notificaciones:**
   - Los mensajes de estado, alertas, modales y botones deben respetar esta misma regla de capitalización uniforme.

---

## 3. Rediseño de Experiencia de Usuario (Feedback del Profesor)

### 3.1 El Problema Fundamental de Usabilidad
El usuario no técnico no quiere "revisar un parche diff" ni sabe qué hacer cuando el sistema dice `promoted`. Quiere saber:
1. **¿Qué construyó el sistema?** (Resumen funcional en lenguaje humano).
2. **¿Dónde está mi aplicación y cómo la abro ya mismo?** (Botón de "Ejecutar / Abrir App" o comando de 1 solo paso).
3. **¿Cómo la comparto o guardo?** (Local en su computadora sin enredos, o subirla a GitHub cuando esté listo).

### 3.2 Separación Estricta: "Modo Local Simple" vs. "Modo GitHub / Nube"

```mermaid
graph TD
    A["Pantalla de Bienvenida / Asistente Inicial"] --> B{"¿Dónde quieres tu proyecto?"}
    
    B -->|Opción 1: Principiante / Rápido| C["🏠 Modo Local Simple\n(Sin Git, sin cuentas, sin comandos)"]
    B -->|Opción 2: Avanzado / Colaborativo| D["🐙 Modo GitHub / Nube\n(Control de versiones y publicación remota)"]
    
    C --> C1["Crea una carpeta en tu PC\n(ej. MisAplicaciones/MiCalculadora)"]
    C1 --> C2["Agentes generan código + ejecutable\n(index.html o app.py)"]
    C2 --> C3["Ficha Final: 'Cómo usar tu app'\nBotón 'Abrir aplicación'"]
    C3 -.->|Cuando el usuario quiera aprender| E["🎓 Botón: 'Publicar este proyecto en GitHub'"]
    
    D --> D1["Asistente guiado de Token GitHub\n(Explicación sin tecnicismos)"]
    D1 --> D2["Agentes crean repo, clonan y prueban"]
    D2 --> D3["Commit y Push automático con 1 clic"]
```

#### Reglas de Diseño del Modo Local:
- **Cero jerga Git obligatoria:** En lugar de exigir un repositorio con commit `HEAD` preexistente, el sistema inicializa internamente un Git invisible o una carpeta directa para rastreo, pero para el usuario es simplemente *"Mi carpeta de aplicación"*.
- **No mostrar diffs crudos por defecto:** Mostrar una vista de **"Archivos Creados"** con iconos amigables y un resumen de lo que hace cada archivo, con una pestaña secundaria *"Ver cambios técnicos (Diff)"* para usuarios avanzados.

#### Reglas de Diseño de la Ficha Post-Generación ("Qué hacer con tu código"):
Al terminar la promoción, en lugar de un frío estado `completed`, el sistema debe desplegar una tarjeta interactiva:
1. **Acción Principal Inmediata:**
   - Si es Web: Botón prominente **"🌐 Abrir en el navegador"** (abre `index.html` o levanta servidor local `http.server` temporal).
   - Si es Python/CLI: Botón **"▶️ Ejecutar aplicación"** o un bloque visual con el comando exacto para copiar y pegar: `python calculadora.py`.
2. **Instrucciones Claras en 3 Pasos:**
   - *"Paso 1: Tu aplicación está guardada en `C:\MisProyectos\Calculadora`"*.
   - *"Paso 2: Requiere Python 3.12 (ya incluido en este sistema)"*.
   - *"Paso 3: Para iniciarla en cualquier momento, abre el archivo `iniciar.bat` generado"*.

#### Asistente de Conexión a GitHub (Pedagógico):
- Si el usuario decide subir a GitHub:
  - Explicar en 2 oraciones qué es GitHub (*"Es como un Google Drive pero especializado en código, donde tu proyecto queda guardado en la nube de forma segura"*).
  - Campo para Personal Access Token (PAT) con botón directo a `github.com/settings/tokens` con los permisos exactos marcados.
  - Botón: **"🚀 Publicar en GitHub ahora"** -> Ejecuta `git remote add`, `git add`, `git commit -m "Mi aplicación inicial construida con AI-SWE"`, `git push`.

---

## 4. Integración de Patrones de `neuromapa` (Memoria Asociativa y Optimización de Tokens)

El repositorio `https://github.com/lumiel777/neuromapa` aporta tres principios arquitectónicos de alto valor para resolver la contención de presupuesto y la ventana de contexto del sistema:

### 4.1 Grafo de Co-ocurrencia de Archivos ("Mielina" de Archivos)
- **Problema actual:** Cuando un repositorio crece, el `Researcher` lee todos los archivos que coinciden con `_EXTENSIONES` o trunca a ciegas. Si enviamos 20 archivos al prompt del `Coder`, se disparan los tokens y el costo, o se satura el modelo.
- **Patrón Neuromapa:** Un grafo en memoria donde los nodos son archivos y las aristas son relaciones observadas:
  - Si un archivo `calculadora.py` importa `operaciones.py` y ambos son probados por `test_calculadora.py`, el peso de co-ocurrencia entre ellos aumenta.
  - **Poda Asociativa:** Al recibir una instrucción, el `Researcher` identifica el archivo semilla (por mención o búsqueda de términos) y recorre el grafo seleccionando **únicamente el vecindario de mayor peso (Top-K nodos conectados)**.
  - **Resultado:** Reducción del 50% al 70% en tokens de entrada hacia `Qwen2.5-Coder` en proyectos existentes.

### 4.2 Freno Dinámico de Tokens y Alerta de Velocidad Horaria
- **Patrón Neuromapa:** `config.json` con umbral de gasto por hora (`max_tokens_per_hour` o `max_usd_per_hour`).
- Si en una ráfaga de reintentos los agentes superan el límite horario, el sistema entra en una pausa preventiva (*"Has consumido $0.50 USD en los últimos 30 minutos. ¿Deseas autorizar la siguiente ronda de pruebas?"*).
- Esto evita drenar los créditos API por bucles inadvertidos de reintentos entre `Coder` y `Reviewer`.

### 4.3 Detección de Archivos Huérfanos y Contexto Redundante
- Limpieza previa antes de alimentar al LLM: eliminar comentarios masivos repetidos, archivos de lock (`package-lock.json`), assets binarios o temporales de cache (`.pytest_cache`, `__pycache__`) antes de calcular la evidencia.

---

## 5. Tareas Específicas de Implementación para Codex

### Tarea 1: Homologación Tipográfica de la Interfaz (Sentence Case)
- Auditar y normalizar los textos en:
  - `frontend/src/views/VistaGeneral.tsx`
  - `frontend/src/views/VistaProyectos.tsx`
  - `frontend/src/views/VistaEjecuciones.tsx`
  - `frontend/src/views/VistaActividad.tsx`
  - `frontend/src/components/Navegacion.tsx`
  - `frontend/src/components/SecuenciaAgentes.tsx`
  - `frontend/src/components/InspectorEtapa.tsx`
- Regla: *"Primera en mayúscula, resto en minúscula"* (ej. *"Agente y ejecución"*, *"Proyectos registrados"*), reservando MAYÚSCULAS solo para siglas (`API`, `E2E`, `Git`, `GitHub`, `UI`, `SSE`).

### Tarea 2: Backend — Servicio de Guía de Ejecución y Publicación GitHub
1. **Endpoint `GET /runs/{run_id}/launch-guide`:**
   - Detecta la naturaleza de los archivos promovidos:
     - Si hay `.html`: Tipo `web_static` -> URL `file:///...` o comando `python -m http.server`.
     - Si hay archivo principal Python (`main.py`, `app.py`, o archivo homónimo al proyecto): Tipo `python_app` -> comando de ejecución.
   - Genera automáticamente un archivo lanzador en Windows: `iniciar.bat` o `ejecutar.cmd` dentro del proyecto.
   - Devuelve JSON estructurado con `summary_es`, `launch_action`, `command` e `instructions`.
2. **Endpoint `POST /projects/{project_id}/publish-github`:**
   - Contrato: `GitHubPublishRequest(repo_name: str, pat_token: SecretStr, private: bool = True)`.
   - Crea el repositorio en GitHub vía API REST de GitHub (`POST /user/repos`), configura el origen remoto seguro (`origin`) con credencial temporal en memoria (redactada de logs), y ejecuta `git push -u origin HEAD`.

### Tarea 3: Backend — Gestor de Memoria Asociativa (`src/ai_swe/state/memory_graph.py`)
1. Implementar `FileMemoryGraph` en SQLite usando una tabla de adyacencia `file_cooccurrence(source TEXT, target TEXT, weight REAL, last_seen DATETIME)`.
2. Al ejecutar `researcher` o `apply_sandbox`, actualizar las aristas entre los archivos modificados/leídos juntos.
3. Filtrar la evidencia entregada al Coder priorizando los nodos de mayor peso relativo al requerimiento del usuario.

### Tarea 4: Frontend — Rediseño de Vista General y Ficha Post-Promoción
1. **Paso Inicial en `Compositor.tsx`:** Selector visual claro:
   - 🔘 **"Modo Local"** *(Recomendado para no programadores: guarda en una carpeta de tu equipo sin necesidad de cuentas ni Git)*.
   - 🔘 **"Modo GitHub"** *(Para desarrolladores o usuarios que deseen sincronizar con un repositorio remoto)*.
2. **Componente `GuiaEjecucion.tsx`:**
   - Aparece automáticamente cuando `run.status === "completed"`.
   - Tarjeta verde brillante con icono de cohete: *"¡Tu aplicación está lista para usar!"*.
   - Botón directo para abrir la app o copiar el comando.
   - Botón secundario: *"🚀 Publicar en GitHub"* que abre el modal pedagógico de publicación.
3. **Modal `PublicarGitHubModal.tsx`:**
   - Explicación sencilla paso a paso con enlace para generar el token en GitHub en 1 clic.

---

## 6. Criterios de Aceptación y Pruebas Verificables

1. **Homologación Editorial:**
   - Todos los títulos de la UI y los componentes clave siguen la convención *Sentence case* (`Agente y ejecución`).
2. **Test Automatizado de Guía de Lanzamiento (`tests/test_launch_guide.py`):**
   - Verificar que para un proyecto con `index.html` devuelva `open_browser` y cree `iniciar.bat`.
   - Verificar que para un proyecto con `calculadora.py` devuelva `run_command` y el comando de arranque correcto.
3. **Test de Memoria Asociativa (`tests/test_memory_graph.py`):**
   - Verificar que archivos que se modifican juntos aumentan su peso de adyacencia y son priorizados en la poda de contexto.
4. **Smoke Test de Frontend y Build:**
   - `tsc --noEmit && vite build` sin errores de compilación.
   - Suite `frontend/tests/estados.test.mjs` con 100% PASS.
5. **Preservación Presupuestaria:**
   - Mantener el libro mayor monotónico sin exceder los techos de gasto autorizados.

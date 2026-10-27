# Propuesta de Evolución Arquitectónica y Prompt de Contexto (Inspiración: MADRE)

## Nota de integración del 26 de octubre de 2026

La propuesta original se conserva a continuación como diseño, no como descripción
completa del runtime implementado. Prevalecen estos ajustes de integración:

- El usuario aprobó Analyst/Supervisor deterministas locales y Coder/Reviewer por
  API. El preflight no exige GGUF para los roles deterministas.
- El módulo 3.1 se prepara como diagnóstico reutilizable y CLI sin inferencia.
  Su conexión al launcher y la migración de configuración instalada siguen siendo
  trabajo de G/H; no se declara el producto empaquetado.
- La presencia de una clave no acredita su validez. Un GET opcional de identidad
  puede validar el token del Hub, pero no garantiza permisos de Inference Providers,
  saldo, modelo disponible o inferencia correcta. Nunca se realizan generaciones
  para diagnosticar el arranque.
- SQLite FTS5 consume disco, índices, caché y trabajo de consulta. Si su contexto
  se envía a modelos remotos, esos tokens pueden tener coste. No se promete coste
  de memoria cero ni ahorro garantizado.
- La promoción actual aplica cambios sin crear commits. No existe necesariamente
  un promoted_commit_sha que pueda revertirse. Antes de implementar 3.4 hay que
  diseñar snapshots/preimágenes o un modo explícito de commits y proteger cambios
  posteriores del usuario. No se habilita git revert automáticamente.
- Los módulos 3.2, 3.3, 3.4 y 3.5 son backlog v0.2.0. No se implementan ahora ni
  bloquean v0.1.0. No se añaden MCP, Graphify, TTS o integración de CLIs de agentes.

Fuentes de contexto consultadas: README y docs/REFERENCE.md de
https://github.com/jossuealcacao-exe/madre. Se adapta el concepto de diagnóstico;
no se incorpora código de ese repositorio.

Implementación y evidencia de 3.1: docs/PREFLIGHT-PROVIDERS.md.

---

- **Estado del documento:** PROPUESTA (Diseño y Backlog técnico)
- **Fecha:** 26 de octubre de 2026
- **Proyecto destino:** AI Software Engineering System (`proyecto4-ai-swe`)
- **Referencia analizada:** `jossuealcacao-exe/madre` (Multi-Agent Development Round-table Environment)
- **Regla de gobernanza:** Ninguna función descrita en este documento altera ni bloquea el cierre de las fases D a J de `productization/v0.1.0`, salvo el *Preflight Check* que se alinea nativamente con las Fases G y H.

---

## 1. Propósito de este documento

Este archivo cumple una doble función:
1. **Documento de Diseño y Trazabilidad:** Explica qué conceptos del proyecto externo `MADRE` se adaptarán a `proyecto4-ai-swe`, cómo funcionan en su origen, cómo se transforman para respetar nuestra arquitectura determinista y qué beneficio técnico aportan.
2. **Prompt de Contexto para Agentes (Codex / Claude / Cursor):** Sirve como instrucción autocontenida para que un agente de desarrollo implemente estas mejoras de forma ordenada sin violar las invariantes de seguridad, contratos Pydantic ni el aislamiento por Git worktrees.

---

## 2. Invariantes del proyecto que NUNCA deben romperse

Al adaptar cualquier idea externa, el agente implementador debe respetar estrictamente:
- **Principio rector:** *El modelo propone y el código determinista valida*.
- **Independencia de runtime:** No se envolverán CLIs externas mediante subprocesos (`codex`, `claude`, etc.). Toda inferencia pasa exclusivamente por `ModelGateway` y `OpenAICompatibleAdapter` (apuntando a servidor local GGUF o Hugging Face Router).
- **Aislamiento físico de cambios:** Toda modificación de código se prepara y verifica en un Git worktree separado (`src/ai_swe/sandbox.py`), nunca editando directamente la rama activa del usuario sin pasar por el flujo de promoción.
- **Cero dependencias pesadas nuevas:** Aprovechar SQLite, FastAPI, LangGraph y React ya existentes en el repositorio.

---

## 3. Catálogo de funcionalidades a adaptar (Origen → Adaptación → Impacto)

### 3.1. Preflight Check y Diagnóstico de Proveedores (Aplicable en Fases G–H de `v0.1.0`)
- **De dónde se toma:** Del chequeo de arranque de MADRE (`npx @jossuealcala/madre start`), que inspecciona el entorno local e informa qué motores están listos antes de abrir la sesión.
- **Cómo funciona en el origen:** Verifica binarios instalados en el `PATH` del sistema operativo y el estado de Ollama local.
- **Cómo se adapta a `proyecto4-ai-swe`:**
  - En lugar de buscar CLIs, `src/ai_swe/config.py` y `src/ai_swe/models/` exponen un diagnóstico de salud determinista (sin gastar tokens de inferencia).
  - Verifica: 1) Presencia de configuración de usuario fuera del directorio de código, 2) Disponibilidad del endpoint local GGUF para `Analyst` y `Supervisor`, y 3) Presencia de `HF_TOKEN` válido para `Coder` y `Reviewer`.
- **Cómo ayuda al proyecto actual:** Cumple directamente la condición de cierre de la **Fase G** (*"gestionar proveedor no configurado"*) y **Fase H** (*"arranque local, puertos, salud, errores"*), evitando que el usuario del ejecutable Windows inicie una corrida que falle a mitad del grafo por falta de credenciales o servidor local apagado.

### 3.2. Modos de Ejecución Progresivos con Cortocircuito en LangGraph (Backlog `v0.2.0`)
- **De dónde se toma:** De los niveles de permiso por turno de MADRE (`#0 GHOST`, `#1 EXCHANGE`, `#2 CREATE`, `#3 CONTROL`, `#4 AIRLOCK`).
- **Cómo funciona en el origen:** El usuario etiqueta cada mensaje para restringir si los agentes solo pueden conversar/leer archivos o si tienen permiso de escritura y requieren doble confirmación.
- **Cómo se adapta a `proyecto4-ai-swe`:**
  - Añadir al contrato de entrada (`src/ai_swe/contracts/`) un campo tipado `execution_mode`:
    1. `INSPECT_ONLY`: Ejecuta únicamente `Analyst` → `Supervisor` → `Researcher` (lectura determinista) y finaliza entregando un diagnóstico arquitectónico. **No crea worktree ni invoca al `Coder`**.
    2. `PLAN_ONLY`: Se detiene tras la aprobación del `RunPlan` y la investigación de contexto, exportando el plan técnico sin gastar tokens de generación de código.
    3. `FULL_PROPOSAL` (Por defecto): Flujo completo actual con worktree, `Coder`, pruebas, `Reviewer` y promoción humana.
- **Cómo ayuda al proyecto actual:** Reduce drásticamente el consumo del presupuesto de API (protegiendo el límite de 3 USD o cuotas futuras), ya que las consultas de exploración o diseño solo utilizan los modelos locales gratuitos (`Analyst`/`Supervisor`) y herramientas deterministas (`Researcher`).

### 3.3. Memoria Histórica del Proyecto mediante SQLite FTS5 (Backlog `v0.2.0`)
- **De dónde se toma:** De la memoria persistente indexada de MADRE consultada por su agente local (`@madre`).
- **Cómo funciona en el origen:** Indexa el historial de conversaciones pasadas para que un modelo local ligero responda qué se decidió antes sin volver a consumir tokens de los modelos comerciales.
- **Cómo se adapta a `proyecto4-ai-swe`:**
  - En la capa de persistencia `src/ai_swe/state/` (SQLite), crear una tabla virtual **FTS5** (Full-Text Search nativa de SQLite, sin instalar bases vectoriales externas ni Graphify).
  - Indexar automáticamente al cierre de cada corrida los artefactos validados: `TaskInterpretation`, `RunPlan`, archivos tocados y `ReviewVerdict` (especialmente las razones de rechazo o fallos de tests).
  - El nodo determinista `Researcher` consulta esta tabla FTS5 cuando planifica sobre los mismos archivos para inyectar advertencias previas (ej. *"En la corrida X un cambio en este módulo rompió el test Y"*).
- **Cómo ayuda al proyecto actual:** Otorga memoria a largo plazo entre ejecuciones con **cero costo de RAM/VRAM adicional** y **cero gasto de API**, evitando que el `Coder` repita errores pasados en el mismo repositorio.

### 3.4. Promociones Reversibles / 1-Click Rollback (Backlog `v0.2.0`)
- **De dónde se toma:** Del mecanismo de *Checkpoint / Undo* del modo `#3 CONTROL` de MADRE.
- **Cómo funciona en el origen:** Guarda una instantánea antes de permitir que el agente modifique archivos para poder deshacer la acción con un comando si el resultado no convence.
- **Cómo se adapta a `proyecto4-ai-swe`:**
  - En `src/ai_swe/tools/` y `src/ai_swe/sandbox.py`, durante el paso de promoción controlada al repositorio original, registrar en SQLite el par `(pre_promotion_head_sha, promoted_commit_sha)` asociado al `run_id`.
  - Exponer un endpoint determinista y un botón en la UI de React para **"Revertir promoción"**, el cual verifica que el árbol de trabajo del repositorio destino esté limpio y ejecuta un `git revert --no-edit <promoted_commit_sha>` (o restablecimiento seguro validado).
- **Cómo ayuda al proyecto actual:** Añade una red de seguridad post-aprobación humana, elevando la confianza del usuario al probar el producto Windows en repositorios reales.

### 3.5. Vista de Auditoría Cruzada `Coder` ↔ `Reviewer` en UI (Backlog `v0.2.0`)
- **De dónde se toma:** De la interfaz de "Mesa Redonda" de MADRE donde se visualiza el contrapunto entre agentes.
- **Cómo funciona en el origen:** Muestra en un mismo flujo cómo un agente critica o complementa la respuesta del otro.
- **Cómo se adapta a `proyecto4-ai-swe`:**
  - Aprovechando el canal SSE existente (`src/ai_swe/api/`) y los contratos `CodeProposal` y `ReviewVerdict`, presentar en el frontend una tarjeta comparativa lado a lado: *"Lo que propuso el Coder"* vs *"Observaciones deterministas de tests + Veredicto del Reviewer"* antes de los botones de decisión humana.
- **Cómo ayuda al proyecto actual:** Mejora la explicabilidad de la interfaz sin necesidad de cambiar la topología del grafo ni añadir llamadas extra a los modelos.

---

## 4. Prompt de Ejecución para Agentes (Copiar y usar según la fase)

Cuando desees que Codex implemente cualquiera de estos bloques, pásale la siguiente instrucción indicando el número de módulo (ej. `3.1` ahora durante las Fases G-H, o `3.2`–`3.5` tras liberar `v0.1.0`):

> **INSTRUCCIÓN PARA EL AGENTE:**
> 1. Lee `docs/CONTEXTO-Y-ESTADO-DEL-PROYECTO.md`, `docs/MAPA-DEL-PROYECTO.md` y `docs/PROPUESTA-MEJORAS-INSPIRADAS-EN-MADRE.md`.
> 2. Verifica la rama actual y el estado del árbol de trabajo con `git status`. No elimines documentos no rastreados ni modifiques el tag `delivery-rc1`.
> 3. Implementa exclusivamente el módulo **[INDICAR MÓDULO: ej. 3.1 Preflight Check / 3.2 Modos de Ejecución / 3.3 Memoria SQLite FTS5 / 3.4 Rollback de Promoción]** siguiendo las restricciones de la sección 2 (*Invariantes del proyecto*).
> 4. Actualiza o añade las pruebas unitarias offline correspondientes en `tests/` (y `frontend/tests/` si aplica) asegurando 0 regresiones en la suite existente.
> 5. Si se modifica algún contrato Pydantic en `src/ai_swe/contracts/`, ejecuta el exportador correspondiente para sincronizar `frontend/contracts.json` sin editarlo a mano.
> 6. Documenta la evidencia real obtenida sin sobreprometer capacidades no probadas.
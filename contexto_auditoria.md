# Contexto para auditoría — AI Software Engineering System

> Actualización posterior al corte original: la segunda entrega de la ruta 3 integra inspección del Workflow, feedback de relectura y baja de registros de proyectos. Consultar `docs/UI-WORKFLOW-VALIDATION.md` y `docs/PRODUCTIZATION-PROGRESS.md` para no tratar estos pendientes históricos como funciones aún ausentes. Sus límites y la validación remota pendiente siguen explícitos en esa acta.

**Fecha de corte:** 28 de octubre de 2026.  
**Código de referencia:** commit `0e29fe01e62816d1606a3a30bf8745a164b422b0`.  
**Rama:** `feature/v0.2.0-madre-continuity`.  
**Estado:** prototipo local evolucionado con candidatos portables para Windows; v0.2.0 todavía no está cerrada como producto de producción.

Este documento reúne el propósito, las capacidades, la evidencia, los problemas observados y las preguntas que debe resolver una auditoría técnica. No constituye una auditoría independiente ni certifica el comportamiento de cualquier modelo o equipo. Los datos históricos deben contrastarse con el commit y el paquete que se esté evaluando.

## 1. Propósito del proyecto

Construir una aplicación que transforme una idea escrita o dictada en una propuesta de software funcional sobre un repositorio autorizado. El usuario debe poder crear proyectos nuevos o modificar existentes, confirmar los requisitos, observar el trabajo, revisar la evidencia y decidir si se aplican los cambios a su repositorio.

La aplicación coordina agentes con responsabilidades distintas. El objetivo es reducir el trabajo manual de desarrollo manteniendo control humano, límites de gasto, trazabilidad y protección de archivos. Se busca un flujo generalizable: una calculadora, un calendario o un contador de calorías son casos de validación, no el alcance completo del producto.

El hardware de referencia del usuario es una GPU de 4 GB de VRAM y 16 GB de RAM. Por coste y recursos se eligió una modalidad híbrida: orquestación y roles deterministas locales, voz local y generación/revisión de código mediante API.

## 2. Experiencia que se quiere lograr

1. Abrir el portable y acceder con un perfil propio.
2. Configurar su proveedor, modelo, token y presupuesto en la bóveda.
3. Registrar un repositorio Git local o crear explícitamente un proyecto nuevo.
4. Escribir o dictar la idea; revisar el texto y confirmar requisitos concretos.
5. Recibir un plan y observar qué etapa está trabajando, qué terminó y qué está bloqueado.
6. Generar una propuesta en un worktree, ejecutar comprobaciones y revisar el resultado.
7. Aprobar o pedir cambios. Solo una aprobación válida permite la promoción.
8. Conservar historial y, como evolución pendiente de cierre, recuperar el trabajo entre equipos.

Un repositorio puede contener únicamente una base inicial: no se espera que el usuario haya construido antes el producto solicitado. Los requisitos técnicos de Git deben validarse y explicarse antes de gastar tokens. La preparación de un repositorio sin commits necesita un tratamiento explícito; no debe diagnosticarse a partir de una captura sin verificar su HEAD y su ruta.

## 3. Arquitectura y documentos para inspeccionar

| Área | Ubicación | Función |
|---|---|---|
| API y aplicación web | `src/ai_swe/api/` | FastAPI, operaciones de proyectos/ejecuciones/perfiles, eventos SSE y estáticos |
| Contratos | `src/ai_swe/contracts/` | Esquemas Pydantic de entradas, interpretación, planes, propuestas, revisión y estado |
| Orquestación | `src/ai_swe/graph/` | LangGraph, nodos, rutas, puertas humanas y selección de proveedores |
| Modelos y gasto | `src/ai_swe/models/` | Gateway, adaptadores, salida estructurada y control de presupuesto |
| Persistencia y memoria | `src/ai_swe/state/` | SQLite, checkpoints, FTS5 y componentes de continuidad |
| Seguridad | `src/ai_swe/security/` | Perfiles, autenticación, bóveda cifrada, recuperación y redacción de secretos |
| Repositorios y herramientas | `src/ai_swe/projects.py`, `sandbox.py`, `tools/` | Creación de proyectos, worktrees, aplicación de propuestas, pruebas, promoción y rollback |
| Voz | `src/ai_swe/stt/` | Transcripción local; texto editable antes de ejecutar |
| Frontend | `frontend/src/` | React/TypeScript, compositor, configuración, flujo, historial e inspectores |
| Distribución | `tools/build_windows.py`, `tools/signed_runtime.py`, `packaging/` | Construcción y antecedentes de distribución Windows |
| Pruebas | `tests/`, `frontend/tests/` | Contratos, integración, seguridad y regresiones |
| Evidencia y actas | `docs/`, `docs/evidence/` | Alcance declarado y resultados; `_tmp/` contiene evidencia local adicional no versionada |

Los directorios `mcp/` y `observability/` no acreditan integraciones operativas por existir. Revisar implementación y llamadas reales antes de declararlas disponibles.

## 4. Funcionalidades vigentes y alcance de su evidencia

### 4.1 Entrada, requisitos y ejecución

- Entrada escrita y voz con faster-whisper. Se validó español con `Systran/faster-whisper-small`, CPU e int8; el usuario confirmó una prueba física de micrófono.
- Transcripción editable y confirmación humana; transcribir o usar el texto no debe iniciar por sí solo una ejecución.
- La fidelidad de captura de texto manual se distingue de la confianza heurística con que Analyst clasifica la intención. El 100 % de fidelidad no significa que una petición amplia tenga requisitos completos.
- Analyst y Supervisor disponen de respaldo determinista local. Los modelos locales pequeños evaluados no superaron toda la evaluación y no se habilitaron como solución definitiva.
- Researcher inspecciona evidencia del repositorio, incluidos archivos web y SQL; no debe presentarse como búsqueda web si no existe tal herramienta activa.
- Modos `INSPECT_ONLY`, `PLAN_ONLY` y `FULL_PROPOSAL`, con límites en el backend. Inspeccionar o planificar no implica generar código.
- Confirmación de requisitos y aprobación de promoción como puertas humanas distintas.

### 4.2 Generación, comprobación y promoción

- Coder y Reviewer pueden operar por API con routing por perfil. Existe antecedente E2E con `Qwen/Qwen2.5-Coder-32B-Instruct:nscale`; la disponibilidad del proveedor debe comprobarse de nuevo cuando se use.
- Coder propone archivos estructurados; el sistema deriva diff y hashes. La propuesta se aplica en un Git worktree antes de probarse.
- Runner con objetivos permitidos, incluyendo pytest y Ruff reales. La suite del producto no prueba automáticamente la corrección funcional de cualquier aplicación generada.
- Reviewer revisa evidencia y puede rechazar defectos concretos aunque las pruebas pasen. No debe ser obligado a aceptar para conseguir una demostración verde.
- Promoción condicionada a aprobación y controles de integridad; la promoción no equivale necesariamente a crear un commit o hacer push.
- Conservación prioritaria de pruebas al recortar propuestas por límites. Si se recorta una propuesta, se detiene con `SCOPE_TRIMMED`; no se promociona una implementación parcial como completa.
- Implementación de rollback con controles sobre los archivos promovidos; no se debe equiparar a una recuperación transaccional integral del producto.

### 4.3 Proyectos, perfiles y distribución

- Registro de repositorios locales y creación explícita mediante «Nuevo proyecto Git», con README y primer commit en destino nuevo/vacío. Se requiere Git instalado y carpeta padre existente.
- Validación de rutas autorizadas y rechazo de rutas privadas, enlaces/reparse points, metadatos `.git`, alias ambiguos de Windows y ADS.
- Perfiles autenticados con espacios separados dentro de la cuenta de Windows, bóveda de credenciales cifrada y configuración por usuario. Esto no constituye aislamiento frente al administrador del equipo.
- Formularios con confirmación y visibilidad de contraseña. Recuperación mediante código preparado previamente, de un uso, sin preguntas de seguridad ni bypass del cifrado.
- SQLite y memoria FTS5 por perfil; los componentes de pausa, exportación/importación y continuidad existen, pero presentan pendientes de cierre descritos más abajo.
- SSE y actividad granular de nodos, llamadas a modelo y herramientas. El cronómetro representa tiempo transcurrido, no un porcentaje inventado.
- Portable con CPython oficial firmado y frontend integrado. No requiere Python/Node de desarrollo para arrancar; Git y las dependencias particulares del proyecto siguen siendo consideraciones externas.

## 5. Flujo de referencia

`Instrucción → Analyst → confirmación humana → Supervisor → Researcher → Coder → sandbox → pruebas → Reviewer → aprobación humana → promoción/informe`.

Las rutas de inspección y planificación terminan antes. Errores, límites, denegaciones y propuestas vacías deben cerrar o pausar el flujo con una causa clara; nunca deben mostrarse como una etapa completada con éxito por haber terminado el nodo.

## 6. Errores observados y lecciones para la auditoría

| Problema | Evidencia y diagnóstico | Estado / seguimiento |
|---|---|---|
| Entrada escrita mostraba 50 % | Se mezclaba fidelidad de captura con confianza de clasificación | Se separaron ambos conceptos; revisar que toda la UI use la distinción |
| Peticiones de creación quedaban como inspección | Clasificación heurística insuficiente para verbos en español | Se ampliaron reglas y se permite revisar la interpretación; evaluar ambigüedad restante |
| Flujo sin Coder/pruebas | Casos con `SANDBOX_NO_REPO`; en `run-60d2055db7c6` el fallo aparecía después de generar propuesta | Se añadió preflight antes del Coder remoto. Revisar que selección UI, `project_id`, `repo_path`, autorización y HEAD concuerden |
| Proyectos visibles pero ejecución bloqueada | Una entrada en la lista o su nombre de GitHub no acredita por sí sola la ruta usada por el run | No atribuir automáticamente el fallo al usuario. Inspeccionar el payload y el checkpoint concretos |
| Coder responde sin archivos | `run-ac3070968ca`: Qwen respondió tras unos 5,2 s, pidiendo fallos previos y correcciones para una petición de creación | Se verificó una orden de reparación incondicional en el prompt; corregida en `0e29fe0`. No se repitió todavía la inferencia remota |
| Mensaje falso «en M1… no hay modelo» | Se emitía ante cualquier propuesta vacía, incluso con respuesta acreditada | Corregido: distinguir propuesta vacía validada de ausencia de propuesta y conservar la explicación |
| Pruebas generadas en raíz no se descubrían correctamente | Interacción del runner/worker y directorio de importación | Se ajustó descubrimiento y contexto del worker; verificar proyectos con estructuras diferentes |
| Propuesta de calculadora con defectos | Antecedentes con importaciones/estilo y cálculo; devolver archivos no garantiza que funcionen | Se trasladan stdout/stderr y correcciones al reintento; pruebas reales y oráculo independiente cuando corresponda |
| Recortes que podían ocultar implementación incompleta | Límites de archivos/líneas sobre propuestas | Se priorizan pruebas y se bloquea la promoción si hubo recorte |
| Éxito condicionado artificialmente | Antecedentes de prompt que obligaba aceptación con pruebas verdes y reservas reducidas para ajustar el laboratorio | Se restauró independencia de Reviewer y reserva conservadora. El antecedente remoto exitoso no valida por sí solo el motor posterior |
| Configuración API confusa | Se confundían credencial de acceso local, usuario y token HF; casillas Coder/Reviewer desactivadas | Perfiles y bóveda explícitos; auditar errores de permisos/saldo/modelo sin exponer tokens |
| Registro sin ayuda suficiente | El texto de ayuda de contraseña se interpretaba como el error | Se mejoraron mensajes, campos, confirmación y Mostrar/Ocultar; no se acreditó la causa exacta de todo fallo en el equipo del usuario |
| WinError 4551 | Smart App Control bloqueó la distribución PyInstaller en el host validado | Se adoptó Python oficial firmado. No se desactivaron protecciones; admisión en otra PC sigue pendiente |
| «Releer del servidor» no muestra efecto | El código sí consulta estado e historial; una ejecución detenida devuelve el mismo estado | Falta feedback visible de carga, resultado, fecha y error. Releer no reejecuta Coder |
| Proyectos duplicados difíciles de gestionar | No hay operación de baja de registros en la API inspeccionada | Pendiente «Quitar de la lista» con alcance explícito; no debe borrar carpeta ni GitHub |
| Workflow poco interactivo | La vista general muestra el diagrama con acceso global al detalle | Pendiente selección de etapas y apertura de su inspector con evidencia y acciones válidas |

La causa remota exacta no debe deducirse de un panel vacío. Diferenciar: no se llamó al modelo, error HTTP/proveedor, salida inválida, propuesta vacía válida, límite de alcance, sandbox fallido, pruebas fallidas o revisión rechazada.

## 7. Estado de validación: cifras que no deben mezclarse

| Referencia | Evidencia | Límite |
|---|---|---|
| v0.1.0 local | 791 aprobadas, 3 omitidas; paquete admitido con SAC en el host | Histórico; no certifica v0.2.0 ni otro equipo |
| Builder `60edbc8` | Suite integrada: 889 aprobadas y 4 omitidas; frontend: 32 aprobadas | Resultado sobre ese checkpoint, no una nueva corrida completa después de cada cambio |
| Calendario/calorías | E2E con `FakeModelAdapter`, pytest/Ruff reales, puertas y promoción; interacción de navegador sobre fixtures | No prueba que un modelo remoto genere cualquier proyecto correctamente |
| Calculadora remota histórica | Acta registra Coder/Reviewer remotos y oráculo matemático aprobado | Revisar configuración y controles de aquella corrida; hubo correcciones posteriores de presupuesto y Reviewer |
| Motor `0e29fe0` | 91 pruebas focalizadas aprobadas; dos defectos reproducidos antes del cambio; 14 comprobaciones del portable aprobadas | Sin nueva inferencia remota y sin repetir toda la suite del producto |

No sumar estas cifras como si fueran casos únicos ni confundir respuestas simuladas con llamadas reales. Separar «la aplicación arrancó», «el grafo funcionó», «el modelo generó código» y «el producto generado cumple sus requisitos».

**Portable más reciente al corte:** `dist/windows-v0.2.0-coder-initial-rc1/AISWESystem-windows-x64.zip`. SHA256: `4e0cee9858d2cdfddd2ea49ce36fd90723895f90f71e330ad751fb2c74bfe3a6`.

La entrega canónica v0.1.0 se conserva en `dist/windows-signed-python-rc2/AISWESystem-signed-python-rc2.zip`. No confundir paquetes viejos con el servidor activo: registrar ruta del proceso, paquete, commit y puerto al reproducir.

## 8. Pendientes y límites que deben mantenerse visibles

- **Continuidad entre equipos:** se documentaron auto-backup sin integración productiva, fallos en importación UI/formato y gestión de errores, recuperación incompleta de algunos contenidos, residuos tras importaciones fallidas y validación de archivo/esquema pendiente. Confirmar cuáles siguen presentes antes de asignarles cierre.
- **Sandbox:** worktree y política de escritura no son una VM ni un aislamiento fuerte de procesos. Las pruebas ejecutan código local; la ausencia de salida de red no está garantizada.
- **Distribución:** las comprobaciones locales con destinos y perfiles temporales no sustituyen una VM independiente ni una prueba en otra PC. La firma de CPython no firma todo el código, las ruedas ni el ZIP.
- **Cancelación:** el endpoint conserva respuesta 501. Pausa cooperativa entre nodos no equivale a interrumpir una inferencia o proceso en curso.
- **Alcance del builder:** la ruta probada favorece Python y web autocontenida con HTML/CSS/JavaScript y JSON/SQLite. No se acredita construcción arbitraria de aplicaciones React/npm ni instalación libre de dependencias.
- **Modelos:** un catálogo de candidatos no equivale a diez modelos validados. Token presente no demuestra permisos, saldo, compatibilidad de salida estructurada o disponibilidad.
- **Recuperación:** el código de rescate debe prepararse antes de perder acceso y no reemplaza un respaldo de archivos/equipo. No afirmar cifrado integral de SQLite, logs o worktrees.
- **Documentación:** README y actas antiguas conservan datos obsoletos —por ejemplo «sin autenticación»—. Versionar afirmaciones y reconciliar contradicciones, sin aplicar automáticamente limitaciones de v0.1.0 a v0.2.0.
- **Integraciones futuras:** Jupyter Model Lab, MCP, Graphify/Knowledge Graph, Langfuse y TTS no están acreditados como funciones actuales del runtime.
- **Producción:** falta una aceptación integral con matriz de sistemas/hardware, actualizaciones, recuperación, seguridad operacional y criterios de calidad de los proyectos generados.

## 9. Ruta de trabajo acordada

Se eligió la **ruta 3: entregas separadas**.

1. **Motor:** corrección del contexto inicial y diagnóstico de propuesta vacía, guardada en `0e29fe0` y validada offline. Queda comprobar el comportamiento remoto bajo un nuevo presupuesto autorizado.
2. **Experiencia de uso:** feedback de actualización, inspectores desde Workflow y baja segura de registros duplicados. Todavía pendiente al corte.
3. **Cierre progresivo del producto:** resolver continuidad y riesgos encontrados, validar en otro equipo y actualizar las actas de aceptación.

Una petición como «calculadora científica a nivel universidad» necesita criterios confirmados: operaciones, grados/radianes, dominio numérico, complejos o matrices si se piden, tolerancias, manejo de errores, interfaz, persistencia y modo de arranque. El sistema debe ayudar a concretarlos y distinguir lo implementado de lo fuera de alcance.

## 10. Objetivo concreto de la auditoría

Determinar qué impide pasar del prototipo local a una herramienta confiable para crear proyectos distintos, con especial atención a los fallos reales reportados. El resultado debe priorizar cambios verificables por impacto, coste y dependencia, preservando las puertas humanas y los datos.

Preguntas prioritarias:

1. ¿La solicitud original y la interpretación confirmada llegan completas al Supervisor y al Coder? ¿Se distinguen creación, modificación y corrección sin instrucciones contradictorias?
2. ¿Se comprueba la ruta del run, identidad, autorización y base Git antes de pagar una inferencia? ¿Qué ocurre con repositorios vacíos, HEAD ausente, junctions y rutas movidas?
3. ¿Cómo se determina que una propuesta vacía es una negativa válida o una mala interpretación? ¿Cómo se informa y permite corregir sin repetir gastos a ciegas?
4. ¿Los prompts y esquemas caben en el contexto? ¿Hay truncamiento, límites de salida o fragmentos de evidencia insuficientes?
5. ¿Qué valida realmente el Reviewer? ¿Hay independencia, evidencia funcional, ciclos acotados y rechazo seguro de falsos éxitos?
6. ¿Qué garantía aporta cada prueba? ¿Cubren requisitos del producto generado, errores numéricos, persistencia e interfaz, o solo archivos/estructura?
7. ¿La UI refleja el estado de la ejecución seleccionada, gestiona SSE desconectado y hace visibles errores, espera, actualización y acciones disponibles?
8. ¿La baja de proyectos puede conservar historial, referencias y worktrees sin eliminar archivos inesperadamente?
9. ¿Se pueden restaurar sesiones cifradas, cambios no promovidos y puertas humanas sin perder datos ni reejecutar modelos?
10. ¿Qué riesgos de ejecutar código propuesto por modelos siguen sin aislamiento efectivo?

## 11. Búsquedas externas sugeridas para apoyar la auditoría

La búsqueda debe contrastar el código con documentación oficial vigente, versiones del lockfile y publicaciones primarias. Este documento no incluye una revisión web nueva. Registrar URL, fecha, versión y aplicabilidad de cada fuente; una recomendación externa no es autorización para cambiar dependencias o seguridad.

| Tema | Preguntas / términos de búsqueda | Fuentes preferentes |
|---|---|---|
| LangGraph | checkpoints, interrupts, resume, idempotencia, retries y efectos laterales | Documentación oficial de LangGraph/LangChain |
| Hugging Face | Inference Providers, routing, proveedores disponibles, structured outputs, errores, uso y precios | Documentación HF y proveedor efectivo, no solo la ficha del modelo |
| Qwen y generación | formato de mensajes, ventana real, longitud de salida, evaluación de código | Model cards oficiales y publicaciones de Qwen; evidencia propia por tarea |
| Contratos | esquemas JSON compatibles y validación de respuestas | Pydantic, JSON Schema y documentación del endpoint concreto |
| Git | worktree con HEAD ausente, repositorios iniciales, concurrencia y promoción segura | Manual oficial de Git |
| Windows | Smart App Control, Code Integrity, distribución Python y firmas | Microsoft Learn y documentación oficial de Python |
| Seguridad | ejecución de código no confiable, prompt injection, gestión de secretos y sesiones | OWASP y documentación de mecanismos realmente aplicados |
| SQLite/criptografía | FTS5, backup consistente, WAL, límites de importación y AEAD | SQLite, cryptography y especificaciones primarias |
| UI y accesibilidad | SSE, reconexión, estado de actualización, navegación por teclado y foco en diálogos | MDN y W3C/WAI |
| Calidad de calculadora | dominio, precisión, unidades angulares, errores y casos de referencia | Documentación matemática/numérica primaria y bibliotecas utilizadas |

## 12. Evidencia y restricciones de ejecución

- Priorizar lectura de código, contratos y actas; reproducir en repositorios descartables y perfiles temporales.
- No solicitar, copiar ni incluir tokens, contraseñas, bóvedas, bases de usuarios o `.env` en informes públicos, prompts externos o ZIP.
- **No realizar llamadas pagadas con el presupuesto anterior.** El ledger del laboratorio registra 2.99999104 USD reservados de los 3 USD autorizados. Reserva no equivale a consumo facturado; ese saldo no se renueva automáticamente por crear otro perfil.
- El presupuesto por ejecución del producto es distinto de la autorización acumulada del laboratorio. Una prueba remota requiere autorización y reserva suficientes.
- Preservar v0.1.0, historial y paquetes anteriores. Sin push, cambios de políticas Windows, desactivación de SAC o comandos Git destructivos como parte de una auditoría.
- Pedir cambios de código solo frente a defectos verificables y documentar qué se comprobó después. Evitar grandes refactors, nuevos frameworks o cambios visuales sin relación con los hallazgos.
- No prometer porcentaje de avance, éxito de modelo, recuperación ni producción sin evidencia que sostenga esa afirmación.

## 13. Documentos de referencia y orden recomendado

1. `docs/CODER-INITIAL-GENERATION-VALIDATION.md`: corrección más reciente y límites de su evidencia.
2. `docs/PROJECT-BUILDER-VALIDATION.md`: validación integrada y candidato previo.
3. `docs/PRODUCTIZATION-PROGRESS.md`: secuencia de decisiones; leer como historial, no asumir que cada declaración inicial quedó cerrada.
4. `docs/PROFILE-RECOVERY-VALIDATION.md`: registro y recuperación.
5. `docs/SPEC-v0.2.0-MADRE-USER-CONTINUITY.md`: diseño objetivo; no confundir especificación con aceptación.
6. `docs/REAL-MODEL-VALIDATION.md`, `docs/HYBRID-MODEL-VALIDATION.md` y `docs/REAL-STT-VALIDATION.md`: modelos y voz.
7. `docs/PACKAGING-REPORT.md`, `docs/INSTALLATION-WINDOWS.md` y `docs/KNOWN-LIMITATIONS-v0.1.0.md`: distribución y límites históricos.
8. `docs/RELEASE-MATRIX-v0.1.0.md` y `docs/PRODUCT-v0.1.0.md`: entrega local anterior.
9. `docs/evidence/`, `docs/audit/` y `_tmp/`: evidencia durable, auditorías históricas y resultados locales adicionales. Verificar disponibilidad de `_tmp/` antes de citarlo.
10. `docs/SRS/`, `docs/arquitectura/`, `diagramas/`: entregables académicos y arquitectura. Contrastar con runtime actual.

Ante contradicciones, identificar versión y reproducir sobre el código objetivo. No considerar una afirmación de un README histórico como prueba superior a una implementación y un resultado actual verificables.

## 14. Formato esperado del resultado de auditoría

Por hallazgo: identificador, severidad, síntoma, commit/paquete, evidencia, pasos mínimos de reproducción, causa confirmada o hipótesis, impacto para el usuario, propuesta acotada y criterio de aceptación. Identificar si bloquea el motor, la experiencia de uso, la continuidad o el lanzamiento.

Entregar una matriz con **confirmado / corregido y verificado / pendiente de verificar / fuera de alcance**, seguida de una ruta de trabajo ordenada. No cerrar un hallazgo por el solo hecho de añadir código o por obtener una respuesta del modelo; verificar el comportamiento esperado y declarar los límites de la comprobación.

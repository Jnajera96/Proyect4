# Evaluación: Graphify como capa de contexto

> Actualización 2026-11-02: existe un grafo AST nativo de archivos, símbolos e
> importaciones, con consulta/filtro/descarga local. No es una integración de
> Graphify. Ver [alcance vigente](LOCAL-CAPABILITIES-VALIDATION-2026-11-02.md).
> Las afirmaciones de «Knowledge Graph no implementado» siguientes corresponden
> a la propuesta histórica; la adopción de Graphify sigue siendo una evaluación.

> ⚠️ **AVISO `SUPERSEDED` (parcial) — 2026-10-06.**
> **Graphify / Knowledge Graph sigue sin implementarse.** Este documento es una
> **propuesta de diseño `[PROP]`**, no una descripción de algo que exista.
>
> El roadmap vigente (`docs/auditoria-2026-10-06/09_ROADMAP.md`, fase **`F12`**)
> lo mantiene como **fase posterior** a que el flujo
> `Requirements → Supervisor → Researcher → Coder → Tests → Reviewer` funcione
> de extremo a extremo. **No es un requisito del MVP M2.**

> **Propuesta de diseño adicional [PROP].** Este documento no modifica el alcance
> aprobado. Evalúa una tecnología concreta contra los criterios que el propio
> proyecto se impuso y concluye con un veredicto y un criterio de adopción medible.
>
> Pregunta evaluada: *¿se puede implementar Graphify para optimización de tokens y
> para que el agente entienda el contexto con mayor facilidad?*

---

## 1. Qué es Graphify, verificado

**Respuesta corta: sí, es real, y hace exactamente lo que se le atribuye.** No es
un rumor ni una promesa de marketing.

Es una herramienta que convierte un repositorio —código, documentación, PDFs,
imágenes y audio/vídeo— en un **grafo de conocimiento persistente y consultable**,
y lo expone al asistente de programación para que consulte el grafo en lugar de
leer archivos completos.

**Cómo construye el grafo** — tres pasadas, y la distinción entre ellas es lo más
importante del diseño:

| Pasada | Contenido | Método | Procedencia |
|---|---|---|---|
| 1 | Código | **Tree-sitter**, 20 lenguajes, local, determinista. Extrae clases, funciones, importaciones, grafo de llamadas, docstrings. | `EXTRACTED`, confianza **1.0** |
| 2 | Audio y vídeo | `faster-whisper` local, con caché por SHA-256. El audio no sale del equipo. | Transcripción |
| 3 | Documentación, PDFs, imágenes, transcripciones | **LLM en paralelo**, con validación estricta por esquema. | `INFERRED`, con puntuación de confianza |

Cada relación del grafo lleva etiqueta de procedencia: `EXTRACTED`, `INFERRED` o
`AMBIGUOUS`. La documentación lo presenta como "honestidad epistémica": siempre se
puede saber qué se encontró y qué se dedujo.

**Salidas:** `GRAPH_REPORT.md` (informe para personas), `graph.json` (para el
asistente), `graph.html` (visor interactivo), y opcionalmente un *vault* de Obsidian.

**Consumo:** se integra como *skill* con un *hook* `PreToolUse`. Antes de que el
asistente busque con `grep`, consulta el grafo y recibe un subgrafo. Plataformas
soportadas: Claude Code, Codex, OpenCode, Cursor, Gemini CLI, Copilot CLI, Aider,
entre otras.

**Dato relevante para nosotros:** la pasada 2 usa **`faster-whisper`**, el mismo
motor de Speech-to-Text que elegimos en `DEC-08`. Es una coincidencia que refuerza
la elección, no un argumento para adoptar la herramienta.

---

## 2. ¿Es integrable en nuestra arquitectura? Sí, y en un lugar concreto

No habría que forzar nada. El encaje es limpio y cae exactamente donde nuestro
diseño dice que MCP se justifica (`DEC-03`): **cruza un límite de proceso y expone
contratos declarados**.

```
[ Researcher ]  ──►  Policy Engine  ──►  Cliente MCP  ──►  [ Servidor MCP de grafo ]
      │                                                          │
      └── sigue teniendo list_files / read_file / search_text ────┘
                    (el grafo es una herramienta MÁS, no un sustituto)
```

Propiedades que respetaría el diseño actual:

- **Solo lectura.** `repo_map` / `query_graph` serían herramientas de riesgo `NONE`. El
  Researcher, el Coder y el Reviewer podrían usarlas; ningún permiso de escritura cambia.
- **Detrás del Policy Engine.** Toda consulta pasa por `decide()`, como cualquier otra.
- **Confinamiento de rutas.** El servidor solo indexa el directorio autorizado.
- **Sustituible.** Si el grafo se cae, las herramientas de lectura siguen funcionando.
  No hay dependencia crítica.

Es decir: **es integrable sin tocar una sola decisión de arquitectura.** Eso es un
punto a favor, y conviene decirlo antes de explicar por qué no lo adoptamos ahora.

---

## 3. La trampa: el grafo no ahorra tokens por sí solo

Aquí está el matiz que decide la respuesta, y es el que casi nunca se menciona.

**Las cifras grandes que circulan miden el grafo contra volcar archivos completos.**
La reducción citada de hasta 71,5× compara "inyectar 52 archivos" contra "inyectar
un subgrafo". Eso no es una propiedad del grafo: es una propiedad de **no volcar
archivos completos**. Nuestro sistema ya no lo hace (`01-arquitectura.md` §7.3: cada
nodo recibe una porción acotada del estado).

Y hay una medición reproducible que lo confirma. Sobre un proyecto Node.js de ~420
archivos, con `graph.json` de 3,8 MB sin comprimir:

| Configuración | Tokens de entrada | Resultado |
|---|---|---|
| Consulta al grafo **sin recortar** (nodos + relaciones + confianza + resúmenes) | **11 240** | Correcto, pero con 4 de 9 archivos citados como falsos positivos |
| Subgrafo **recortado** (6 nodos + vecinos a un salto + aristas con confianza ≥ 0,75 y no inferidas) | **1 420** | Correcto, 3 archivos citados, los 3 correctos |

**La reducción del 87 % la produce el recorte, no el grafo.** La propia fuente lo
dice: una consulta por defecto devuelve el JSON completo y puede consumir entre
8 000 y 15 000 tokens; y si el usuario repregunta, se vuelve a inyectar otra
respuesta completa. Sin política de recorte, el consumo se parece al de leer
archivos.

**Consecuencia para nosotros:** el valor que el usuario busca —optimización de
tokens— **no se obtiene instalando Graphify**. Se obtiene teniendo una política de
selección de contexto bajo presupuesto. Y esa política es exactamente la que el
sistema ya necesita por otras razones.

**Frase para la defensa:** *el grafo no es la optimización; el grafo es una fuente
más eficiente de candidatos. La optimización es el presupuesto y el criterio de
selección.*

---

## 4. Lo que esto revela sobre una decisión nuestra

`DEC-04` descartó Vector Database y RAG. Conviene ser preciso sobre qué se descartó
y qué no, porque **hay un hueco en mi razonamiento anterior que esta pregunta saca a
la luz**.

Lo que dije: *"la búsqueda por texto sobre código es exacta y superior a la búsqueda
semántica para localizar símbolos y definiciones"*. Sigue siendo cierto.

Pero eso responde a la pregunta **"¿dónde está el símbolo X?"**. No responde a
**"¿cuál es el conjunto mínimo de código que este modelo necesita para resolver esta
tarea, bajo un presupuesto de tokens?"**. Son problemas distintos, y el segundo se
vuelve real cuando el repositorio **no cabe en contexto**.

Y hay un argumento técnico fuerte a favor de los grafos para código: **el código es
un grafo de dependencias, no prosa.** La similitud semántica recupera fragmentos que
*se parecen* a la consulta; no garantiza recuperar la definición, los llamadores ni
la interfaz de la que depende una función. Un fragmento que llama a `processPayment()`
no necesariamente recupera el fragmento que la define — y un agente que no vio la
firma **la inventa**. Eso es un fallo de corrección, no de recuperación.

**Reconocimiento honesto:** `DEC-04` sigue en pie para RAG vectorial, pero su
justificación estaba escrita para un repositorio que cabe en contexto. Graphify
ataca un problema que nuestro prototipo todavía no tiene, y que sí tendría un
repositorio grande. La decisión es correcta **para el alcance actual**, y su
condición de revisión debe quedar escrita.

---

## 5. Riesgos nuevos que introduce

Adoptarlo no es gratis. Estos son reales y ninguno aparece en la documentación de
la herramienta.

### AM-13 — Lavado de inyección a través de artefactos derivados

**Es el riesgo más grave y es nuevo.** Nuestra amenaza principal ya era `AM-02`
(inyección indirecta: un comentario en el código con instrucciones maliciosas). El
grafo **agrava** ese problema en lugar de reducirlo:

- La pasada 3 es **extracción semántica con un LLM** sobre contenido no confiable
  (documentación, PDFs, imágenes). Una instrucción inyectada en un `README` puede
  terminar **destilada en un nodo del grafo**, ahora etiquetada como resumen.
- Un resumen de grafo **se lee como contexto de mayor autoridad** que un archivo
  crudo. "El grafo dice que este módulo hace X" pesa más en el *prompt* que "este
  archivo contiene X". Estamos subiendo el contenido no confiable de categoría.
- El grafo es **persistente**. Una inyección que entra en el índice sobrevive a la
  conversación que la introdujo y se reinyecta en ejecuciones futuras. Nuestro
  diseño se enorgullece de no tener memoria persistente entre ejecuciones
  (`DEC-05`) — y esto sería exactamente eso, por la puerta de atrás.

**Control propuesto, si algún día se adopta:** usar las propias etiquetas de
procedencia de Graphify como **filtro de confianza**. Solo las aristas `EXTRACTED`
(las de Tree-sitter, confianza 1.0) se tratan como hecho. Las `INFERRED` se
descartan, o se marcan explícitamente como no verificadas y nunca en posición de
instrucción. Es convertir una función de honestidad de la herramienta en un control
de seguridad nuestro. Y el grafo se reconstruye por ejecución, no se reutiliza.

### Obsolescencia del índice

Nuestro Coder **escribe en el worktree** en cada subtarea. Cada escritura invalida el
grafo. Si el Reviewer revisa contra un grafo construido antes del parche, está
revisando otro repositorio. Hay que reindexar de forma incremental, y eso añade un
paso que puede fallar en silencio — que es la peor clase de fallo.

### Reproducibilidad

Las aristas `INFERRED` llevan puntuación de confianza y provienen de un LLM. El
mismo repositorio puede producir grafos distintos en dos construcciones. Nuestro
sistema mide con `MET-13` que toda ejecución termina en un estado terminal explícito
y compara configuraciones con `EXP-01`. Introducir un componente no determinista en
la **entrada de contexto** hace que dos ejecuciones comparadas no sean comparables.
Se mitiga filtrando a `EXTRACTED`, y eso reduce el grafo a lo que Tree-sitter puede
ver — que es, otra vez, un índice estructural.

### Costo de construcción

La pasada 3 consume tokens sobre **todo** el repositorio, antes de que el sistema
haya hecho nada útil. Para un repositorio que cabe en contexto, ese costo es
**negativo**: se paga por indexar algo que se podía leer directamente. La
optimización solo empieza a pagar cuando el repositorio es grande.

### Cadena de suministro — hallazgo de esta investigación

Tres señales que obligan a extremar la verificación antes de instalar nada:

1. El paquete se instala como **`graphifyy`** — con **doble y**. Frente a `graphify`,
   es una superficie de *typosquatting* de manual: instalar el nombre "natural"
   descarga un paquete distinto.
2. Existe **`graphiffy.com`**, un producto **distinto** con nombre casi idéntico.
   La colisión de nombres es real.
3. Al intentar recuperar el sitio oficial durante esta evaluación, la respuesta fue
   una **advertencia de phishing** de Cloudflare. Puede ser un falso positivo o un
   dominio comprometido; en cualquier caso, **no es una fuente desde la que
   instalar**.

**Regla que se deriva:** cualquier adopción exige verificar el paquete contra su
repositorio de código fuente y fijar la versión con hash. Un proyecto cuya sección
de seguridad se llama "contención de capacidades" no puede instalar dependencias
desde un dominio marcado como sospechoso.

---

## 6. La alternativa mínima: un mapa del repositorio

El documento es explícito: *"una arquitectura deberá utilizar solamente los
componentes necesarios"* y *"toda complejidad adicional deberá estar justificada"*
[DOC, §13]. Si el objetivo es **selección de contexto bajo presupuesto**, hay una
versión mucho más pequeña que captura la mayor parte del beneficio.

**`repo_map`: un mapa de símbolos con presupuesto de tokens, construido con
Tree-sitter, en proceso.** Es el enfoque del *repository map* de Aider: un resumen
tokenizado del repositorio con símbolos y firmas clave, **ordenado por un PageRank
sobre el grafo de dependencias entre archivos**. Aproximadamente **1 000 tokens**
para el repositorio entero.

| | **Mapa del repositorio** | **Grafo de conocimiento completo** |
|---|---|---|
| Cómo se construye | Tree-sitter + PageRank | Tree-sitter + transcripción + LLM |
| Determinista | **Sí** | No (pasada 3) |
| Costo de construcción | Cero tokens | Tokens sobre todo el repositorio |
| Costo por consulta | ~1 000 tokens | 1 400–11 200 según el recorte |
| Riesgo de inyección | **Bajo**: solo símbolos y firmas, sin texto libre | **Alto**: resúmenes en lenguaje natural |
| Código a escribir | ~150 líneas | Integrar una dependencia externa |
| Qué resuelve | "¿Qué hay aquí y qué es importante?" | "¿Cómo se relaciona conceptualmente?" |

**Lo que el mapa no da:** relaciones semánticas entre documentación y código, ni
nodos inferidos. Para nuestro alcance —localizar código, reunir evidencia,
seleccionar el conjunto de trabajo— el mapa cubre la necesidad.

Y encaja con `DEC-03` sin excepciones: es una **herramienta en proceso**, no un
servidor MCP, porque no cruza ningún límite de proceso ni de confianza. Un mapa
determinista de símbolos no necesita un salto de proceso para aportar valor.

---

## 7. Veredicto

**No se adopta en el prototipo. Se adopta el principio, en la forma mínima, detrás
de una medición.**

Razonamiento, en orden:

1. **La optimización de tokens no viene del grafo, viene del recorte.** Y el recorte
   ya es un requisito nuestro por otras razones. Sin repositorios grandes, no hay
   nada que optimizar.
2. **El costo de construcción es negativo a nuestra escala.** Indexar con un LLM un
   repositorio que cabe en contexto es pagar por no leer.
3. **Introduce `AM-13`, un riesgo nuevo y grave**, que empeora justamente nuestra
   amenaza principal. Un control que sube la autoridad aparente de contenido no
   confiable es un mal negocio en un sistema cuya tesis de seguridad es la
   contención.
4. **Rompe la reproducibilidad** de la comparación de configuraciones, que es la
   base de `EXP-01`.
5. **El mapa del repositorio captura la mayor parte del beneficio** con ~150 líneas
   deterministas y cero riesgo de inyección semántica.
6. **El documento premia la menor complejidad necesaria**, no la herramienta más
   potente disponible [DOC, §13, §21].

**Pero no es un "no" definitivo.** Es un "todavía no, y con criterio". Un grafo de
conocimiento es la respuesta correcta para un repositorio que no cabe en contexto, y
para consultas que cruzan documentación y código. Tenemos que poder decir *cuándo*
cambiaríamos de opinión.

---

## 8. Criterio de adopción: EXP-08

La decisión se convierte en un experimento, no en una opinión.

| | |
|---|---|
| **ID** | `EXP-08` |
| **Hipótesis** | Sobre un repositorio que **no cabe en la ventana de contexto**, una capa de contexto basada en grafo mejora `MET-01` (Task Completion Rate) y `MET-07` (calidad del código) **sin aumentar** `MET-06` (costo por tarea). |
| **Configuraciones** | (a) herramientas actuales: `list_files` + `search_text` + `read_file`. (b) las anteriores **más** `repo_map`. (c) las anteriores **más** consulta a grafo con recorte a 6 nodos y aristas `EXTRACTED` únicamente. |
| **Condición de repositorio** | El repositorio de prueba debe exceder la ventana de contexto. Si cabe, el experimento **no es válido** y se declara así en lugar de reportar una mejora que no significa nada. |
| **Métricas** | `MET-01`, `MET-06`, `MET-07`, `MET-04`, y una nueva: **tokens de entrada por subtarea**. |
| **Criterio de adopción** | Se adopta la configuración (c) **solo si** mejora `MET-01` o `MET-07` de forma medible **y** no empeora `MET-06`. |
| **Criterio de descarte** | Si (b) iguala a (c), se adopta el mapa y se descarta el grafo. Es el resultado más probable y también el más útil: significaría que la complejidad del grafo no se paga. |
| **Control obligatorio** | El conjunto adversarial (`EXP-06`) se ejecuta **también** contra la configuración (c). Si el grafo introduce un vector de inyección nuevo, `EXP-08` se rechaza **aunque mejore las métricas de calidad**. Un sistema más capaz pero menos contenido no es una mejora. |

**Ese último renglón es el que importa.** Deja escrito, antes de tener los datos, que
hay un criterio que no se negocia con una mejora de rendimiento.

---

## 9. Cómo se integraría, si se adopta

Diseño preparado para no tener que rehacerlo el día que la medición lo justifique.
**No se implementa ahora.**

### 9.1 Fase

`M7 — Capa de contexto`, **después** de M6. Fuera del camino crítico del prototipo.
Si no se llega, el sistema está completo sin ella.

### 9.2 Orden de adopción

1. **`repo_map`** (herramienta en proceso, determinista, ~1 000 tokens). Se añade al
   catálogo con riesgo `NONE` y al conjunto del Researcher, del Coder y del Reviewer.
   Se mide con `EXP-08` configuración (b).
2. **Grafo consultado por MCP**, solo si (b) no basta. Servidor de solo lectura,
   confinado al directorio autorizado, con recorte obligatorio y filtro de
   procedencia.

### 9.3 Controles no negociables si se adopta el grafo

- **Solo aristas `EXTRACTED`.** Las `INFERRED` se descartan del contexto o se marcan
  como no verificadas, nunca en posición de instrucción.
- **Recorte obligatorio** en el servidor, no en el cliente: máximo de nodos
  configurables, aristas con confianza mínima, sin rutas absolutas ni rangos de
  línea completos. Un servidor que puede devolver 11 000 tokens por consulta es un
  servidor que hay que configurar antes de conectarlo.
- **Reconstrucción por ejecución**, nunca reutilización entre ejecuciones
  (`DEC-05`). El grafo es un artefacto de la ejecución, no memoria.
- **Reindexación tras cada escritura del Coder.** Si el índice no se actualiza, el
  Reviewer revisa otro repositorio.
- **Verificación de la dependencia** contra el repositorio de código fuente, con
  versión fijada y hash. Ver §5.

### 9.4 Cambios en los contratos

Ninguno. `ToolCall`, `ToolResult` y `PolicyDecision` ya cubren una herramienta más.
La capa de contexto entra por la puerta que el diseño ya tenía abierta.

---

## 10. Resumen para la defensa

| Pregunta | Respuesta |
|---|---|
| ¿Se puede implementar? | **Sí**, y encaja sin tocar ninguna decisión de arquitectura: es una herramienta de solo lectura detrás del Policy Engine. |
| ¿Lo implementamos? | **No en el prototipo.** El principio sí, en su forma mínima (`repo_map`), y detrás de `EXP-08`. |
| ¿Por qué no, si ahorra tokens? | Porque **el ahorro lo produce el recorte, no el grafo**, y el recorte ya es un requisito nuestro. El grafo solo paga cuando el repositorio no cabe en contexto. |
| ¿Aporta a "entender mejor el contexto"? | Sí, conceptualmente. Y el argumento fuerte es que **el código es un grafo de dependencias, no prosa**: la similitud semántica no garantiza recuperar la definición de lo que se llama, y un agente que no vio la firma la inventa. |
| ¿Qué nos frenó? | Un riesgo nuevo y grave (`AM-13`: el grafo **sube de categoría** el contenido no confiable, destilándolo en resúmenes persistentes), la pérdida de reproducibilidad, el costo de construcción a nuestra escala, y una cadena de suministro con señales de alarma. |
| ¿Cuándo cambiaríamos de opinión? | Cuando el repositorio objetivo no quepa en contexto, y `EXP-08` lo demuestre. El criterio está escrito y es medible. |
| ¿Qué haríamos antes? | Un mapa de símbolos determinista de ~150 líneas y ~1 000 tokens, que es la mayor parte del beneficio con una fracción del riesgo. |

**Frase de cierre:** *la pregunta no es si la herramienta es buena —lo es— sino si
resuelve un problema que tenemos. Todavía no lo tenemos. Y cuando lo tengamos, ya
sabemos cómo medirlo antes de creerlo.*

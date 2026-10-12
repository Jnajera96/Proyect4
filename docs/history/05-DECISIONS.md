# 05 — Decisions (ADR index)

> **Capa de índice.** El proyecto **no usa ficheros ADR numerados**: las decisiones
> viven como `DEC-xx` dentro de [`01-arquitectura.md`](01-arquitectura.md) §7.4.
> Este documento las **extrae y centraliza** para que sean localizables, y añade
> las decisiones de fase que no estaban en esa tabla.

## Decisiones de arquitectura (`DEC-xx`)

Extraídas de [`01-arquitectura.md`](01-arquitectura.md) §7.4. La columna «Motivo»
es la del documento original.

| ID | Decisión | Alternativa descartada | Motivo |
|---|---|---|---|
| **DEC-01** | Grafo explícito con LangGraph | Bucle de agente conversacional libre | El grafo hace visibles las transiciones, permite presupuesto por nodo, pausa real y reanudación. Un bucle libre no es defendible ni depurable |
| **DEC-02** | Tres agentes con permisos **disjuntos** | Un agente con todas las herramientas | La disyunción es lo que da valor a la revisión: el Reviewer no puede escribir, así que no puede «arreglar» lo que debería reportar |
| **DEC-03** | MCP solo en el borde exterior (archivos, Git) | MCP para todas las herramientas, incluidas las internas | Añadir un salto de proceso para una función pura es complejidad sin beneficio |
| **DEC-04** | Sin Vector Database ni RAG en el prototipo | Qdrant con índice del repositorio | No hay corpus que lo justifique: el repositorio se lee directamente y cabe en contexto |
| **DEC-05** | Sin memoria persistente de largo plazo | Memoria episódica + semántica vectorial | El valor no está demostrado y el riesgo (fuga entre ejecuciones) es real |
| **DEC-06** | Se ejecutan **pruebas**, no código arbitrario | Ejecutar el código que genera el modelo | Ejecutar código generado es *excessive agency* con superficie de ataque máxima |
| **DEC-07** | Cambios en *worktree* aislado, promoción explícita | Escritura directa sobre el repositorio del usuario | Un error del agente no debe poder destruir trabajo no confirmado |
| **DEC-08** | STT como adaptador de borde, con confirmación obligatoria | STT como componente del núcleo, o «Voice Agent» | El sistema debe estar completo sin voz |
| **DEC-09** | Estado en almacén externo, proceso de API sin estado | Estado en memoria del proceso | Requisito de reanudación (`RNF-D1`) y de escalado (`RNF-E1`) |
| **DEC-10** | Modelo detrás de una abstracción de proveedor | Acoplar los agentes a un SDK concreto | Permite sustituir nube por local y medir costo/precisión por proveedor |
| **DEC-11** | **La ejecución no ocurre dentro de la petición HTTP.** `POST /runs` responde 202 con el `run_id` y un trabajador ejecuta | Ejecutar dentro de la petición y devolver el resultado completo | El cliente **no puede suscribirse a una ejecución cuyo identificador aún no tiene**. El progreso en vivo era estructuralmente imposible, no lento |

## Decisiones de fase (M2)

Estas no estaban en la tabla `DEC-xx`; se registran aquí porque son decisiones de
arquitectura con consecuencias duraderas.

| ID | Fase | Decisión | Motivo |
|---|---|---|---|
| **DEC-12** | `F6` | **El modelo genera `CodeProposal`; el sistema deriva `CodeChange`.** El modelo nunca aporta un `sha256` | Un modelo no puede conocer el hash de un fichero que aún no ha escrito. Pedírselo solo produciría una **alucinación criptográfica** |
| **DEC-13** | `F6` | `FileOperation` (`create`/`modify`/`delete`) como campo obligatorio | Un fichero borrado con `added=0, removed=N` es indistinguible de uno modificado que borró N líneas |
| **DEC-14** | `F7` | Sandbox por ejecución como `git worktree` **detached**, bajo una raíz gitignored | No copia el historial ni duplica `.git`; `--detach` evita dejar una rama suelta en el repositorio del usuario |
| **DEC-15** | `F7` | Una ruta denegada es una **negativa**, no una avería: se registra y el resto del cambio sigue aplicándose | Abortar todo el cambio por un archivo malicioso castigaría a los archivos legítimos |
| **DEC-16** | `F7` | El teardown **no** se ejecuta dentro del grafo | Destruir el worktree antes de la aprobación humana destruiría justo lo que se está aprobando. La limpieza se hace al recrear con el mismo `run_id` |
| **DEC-17** | `F8` | Los *targets* de prueba se resuelven con una **tabla cerrada** `target → argv` en el código; nunca se acepta un comando libre | Un identificador de una lista permitida no es un comando. La tabla es la única fuente de argv y se pasa como **lista** a `subprocess` con `shell=False` |

## Cómo se relaciona con el resto

- **Por qué se decidió así** → este documento y [`01-arquitectura.md`](01-arquitectura.md).
- **Qué está implementado** → [`PROJECT_SNAPSHOT.json`](../PROJECT_SNAPSHOT.json).
- **Qué se defiende y cómo** → [`04-defensa.md`](04-defensa.md).

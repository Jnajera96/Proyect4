# Contexto y estado de AI Software Engineering System

Fecha de revisión: 26 de octubre de 2026.

Este documento reúne el objetivo, el trabajo realizado y los pendientes para
continuar el proyecto. Se basa en el repositorio y las actas disponibles; en esta
revisión no se ejecutaron nuevamente pruebas ni servicios externos. Los resultados
de validación citados pertenecen a ejecuciones anteriores documentadas.

## 1. Contexto del proyecto

AI Software Engineering System, ubicado en el repositorio `proyecto4-ai-swe`, es
un sistema de asistencia a la ingeniería de software mediante agentes. Recibe una
instrucción en lenguaje natural, estructura sus requisitos y coordina la
preparación de cambios sobre un repositorio Git autorizado.

El principio del diseño es: **el modelo propone y el código determinista valida**.
Las propuestas se preparan en un worktree separado. La promoción de cambios al
repositorio original exige una decisión humana explícita y validaciones de
alcance e integridad. Un worktree separa archivos; no constituye aislamiento
completo de procesos ni de red.

## 2. Objetivo que se quiere lograr

Permitir que una persona transforme una solicitud de desarrollo en una propuesta
de software revisable, con requisitos confirmados, planificación, cambios de
código, resultados de verificaciones y revisión humana antes de su aplicación.

El siguiente objetivo concreto es convertir el candidato local en un **producto
Windows reproducible**, con proveedores reales validados, configuración de
instalación, ejecutable, instalador e instrucciones de uso.

Un servicio público de producción es un alcance posterior. El plan actual de
productización no autoriza por sí mismo trabajo de producción o multiusuario.

## 3. Arquitectura y flujo

| Componente | Responsabilidad |
| --- | --- |
| React, TypeScript y Vite | Interfaz de proyectos, solicitudes, actividad, diferencias y decisiones |
| Python y FastAPI | API HTTP y canal de eventos SSE |
| LangGraph | Coordinación del flujo y puntos de intervención humana |
| RunEngine y RunWorker | Ejecución del trabajo fuera de la petición HTTP mediante trabajadores en hilos |
| ModelGateway y adaptadores | Acceso común a proveedores y control de respuestas, errores y presupuestos |
| SQLite | Persistencia local de proyectos, ejecuciones y checkpoints |
| Git worktrees y herramientas | Preparación de cambios, verificaciones y promoción controlada |
| Políticas y seguridad | Restricciones de rutas, operaciones, permisos y redacción de secretos |
| Adaptadores STT | Entrada opcional por transcripción de audio |

Flujo principal:

```text
Seleccionar proyecto y escribir solicitud
  → interpretar requisitos
  → confirmar, modificar o rechazar requisitos
  → planificar e investigar contexto
  → generar propuesta de código
  → aplicar en worktree y ejecutar verificaciones permitidas
  → revisar resultados y diferencias
  → aprobar, solicitar modificaciones o rechazar
  → validar y promover los cambios aprobados
```

La entrada por voz debe producir texto editable y requerir confirmación e inicio
explícitos. La existencia del adaptador no acredita validación con micrófono real.

## 4. Lo que se ha hecho

### Base funcional y candidato local

- Implementación del backend, frontend, contratos de datos y orquestación.
- Flujo de interpretación, planificación, generación, revisión y decisiones humanas.
- Preparación aislada de propuestas mediante worktrees y promoción controlada.
- Persistencia de estados, eventos y checkpoints.
- Políticas de herramientas, protección de rutas y límites por ejecución.
- Autenticación opcional mediante claves con permisos reader, operator y admin.
  Estos permisos no equivalen a cuentas multiusuario.
- Estabilización y validación de las fases A, B y C; candidato local congelado
  mediante el tag `delivery-rc1`.

El acta de Fase C registra validación del frontend en navegador y del flujo de
promoción. Su veredicto corresponde al prototipo local y al alcance offline, no a
una certificación de producción ni a proveedores externos.

### Preparación parcial del laboratorio de modelos

- Herramientas reutilizables en `tools/model_lab.py`, `tools/model_lab_cases.py`
  y `tools/model_lab_cloud.py`.
- Notebook `notebooks/01_HF_AGENT_MODEL_LAB.ipynb` preparado como interfaz externa.
- Casos de evaluación para Analyst, Supervisor, Coder y Reviewer.
- Descubrimiento público de modelos y proveedores; resultados en
  `var/model_lab_results.json` con estado `DISCOVERY_ONLY`.
- Preparación offline de límites de gasto, validación de respuestas y evaluación.
- Modalidad GPU opcional preparada, sin ejecución con pesos o hardware reales.

Según `PRODUCTIZATION-PROGRESS.md`, la última suite documentada terminó con
709 pruebas aprobadas, 3 omitidas y ningún fallo. Es evidencia histórica del
checkpoint; no una ejecución realizada para este resumen.

No se realizaron llamadas de inferencia en ese checkpoint, no se seleccionó
routing por calidad y no se comprobó todavía el token o saldo del proveedor.

### Documentación y entrega académica

- Mapa del proyecto y guía de lectura.
- Diagrama de arquitectura editable en draw.io y exportación PDF.
- Diagramas de arquitectura y actividades en PNG.
- Organización documental en SRS, arquitectura, administración y estimación.
- IEEE 830 editable en Word, adaptado a los apartados del `SRS.docx` del usuario.

El Word fue actualizado con la plantilla base; no debe suponerse que las versiones
Markdown y PDF del SRS contienen automáticamente esa misma revisión. Falta
armonizarlas si se entregarán juntas. La solicitud de omitir pruebas y métricas
correspondía a la organización documental académica; no se eliminaron las pruebas
del software.

## 5. Estado actual del repositorio

| Elemento | Estado observado |
| --- | --- |
| Rama | `productization/v0.1.0` |
| HEAD | `7419818` |
| Candidato congelado | `delivery-rc1` → `2d35a59508c3efee305cae33d74d78860471bcd2` |
| Último checkpoint de implementación | `bc5f8a2`, preparación offline del laboratorio |
| Árbol de trabajo | Con cambios documentales pendientes de commit |
| Producto Windows terminado | No disponible según las actas de continuidad |
| Productización | Pausada por solicitud del usuario; este documento no la reanuda |

Antes de crear este resumen, Git mostraba modificaciones en `README.md` y
`docs/README.md`, además de archivos sin seguimiento en `diagramas/`,
`docs/ESTRUCTURA-DE-ENTREGA.md`, `docs/SRS/`, `docs/administracion/`,
`docs/arquitectura/` y `docs/estimacion/`. Deben conservarse y revisarse antes de
consolidar una entrega. Este resumen añade otro archivo documental.

## 6. Lo que falta para el producto Windows local

| Fase | Trabajo pendiente | Condición de cierre |
| --- | --- | --- |
| D — Laboratorio | Comprobar credencial y autorización económica; ejecutar inferencia acotada, evaluar calidad y compatibilidad | Recomendaciones sustentadas en resultados reales |
| E — Modelos reales | Integrar progresivamente el routing medido y validar el flujo completo con modelos reales | Solicitud, gates, cambios, revisión y promoción verificados en repositorio descartable |
| F — Voz real | Validar hardware, transcripción de audio y micrófono con confirmación humana | Evidencia real del flujo de voz y manejo de errores |
| G — Configuración instalada | Separar configuración, datos, logs y caché del directorio de código; gestionar proveedor no configurado | Funcionamiento desde ubicaciones de usuario y secretos externos al paquete |
| H — Launcher y ejecutable | Arranque local, puertos, salud, apertura de navegador, errores y cierre; empaquetado | Ejecutable con frontend y recursos necesarios comprobado |
| I — Instalador | Validar sin intérprete ni Node de desarrollo y en entorno limpio; crear instalador | Instalación, persistencia, reinicio y uso reproducibles |
| J — Release | Completar matriz final, instrucciones, límites conocidos y versión coherente | Aprobar el producto antes de crear el tag `v0.1.0` |

La mera presencia de un token no autoriza gasto. Antes de inferencia deben quedar
claros el proveedor y el límite económico autorizado; las credenciales no deben
pegarse en el chat ni guardarse en documentos o logs.

## 7. Pendientes adicionales para producción

El candidato local y el producto Windows deben evaluarse por separado de un
servicio público. El acta de Fase C mantiene abiertos los siguientes puntos:

- Aislamiento de procesos y red para herramientas y código generado.
- Resolución de TD-02 en la autenticación del canal SSE.
- Secretos operativos, TLS cuando exista exposición por red y configuración segura.
- Auditoría persistente, retención y borrado de datos.
- Cancelación efectiva de ejecuciones: el endpoint actual está documentado como 501.
- Validación de recuperación ante interrupciones y fallos.

Para un lanzamiento de producción también habrá que definir y verificar copias
de seguridad y restauración, supervisión de fallos, actualización y recuperación
de versiones. Si se pretende un servicio multiusuario, se añaden identidad,
sesiones y separación de datos, permisos y repositorios por usuario.

Esta lista es trabajo por diseñar y validar, no una afirmación de que tales
capacidades estén implementadas. No hay una fecha de lanzamiento sustentada por
la evidencia disponible.

MCP, Graphify, Knowledge Graph, TTS y Langfuse completo permanecen fuera del plan
actual. Su incorporación no es condición necesaria para cerrar la primera
versión local.

## 8. Documentos para continuar

Las rutas siguientes son relativas a este documento, ubicado en `docs/`.

| Documento | Función |
| --- | --- |
| [PRODUCTIZATION-PROGRESS.md](PRODUCTIZATION-PROGRESS.md) | Avance más reciente y pausa del trabajo |
| [RESUME-PRODUCTIZATION-v0.1.0.md](RESUME-PRODUCTIZATION-v0.1.0.md) | Punto seguro e instrucciones de reanudación |
| [Plan de productización](superpowers/plans/2026-10-14-productization-v0.1.0.md) | Secuencia D a J y restricciones |
| [RELEASE-CANDIDATE-PHASE-C.md](RELEASE-CANDIDATE-PHASE-C.md) | Evidencia y límites del candidato local |
| [MODEL-LAB-REPORT.md](MODEL-LAB-REPORT.md) | Preparación y límites del laboratorio |
| [01-arquitectura.md](01-arquitectura.md) | Diseño y decisiones técnicas |
| [03-flujo-e-implementacion.md](03-flujo-e-implementacion.md) | Flujo y responsabilidades |
| [07-contrato-frontend-backend.md](07-contrato-frontend-backend.md) | Correspondencia entre interfaz y backend |
| [MAPA-DEL-PROYECTO.md](MAPA-DEL-PROYECTO.md) | Estructura y guía documental |
| [ESTRUCTURA-DE-ENTREGA.md](ESTRUCTURA-DE-ENTREGA.md) | Organización de la entrega académica |
| [SRS editable](SRS/IEEE-830-AI-SWE.docx) | Requisitos en Word según la plantilla proporcionada |

El plan sí existe en `docs/superpowers/plans/`; algunas referencias previas
omitían el prefijo `docs/`. Además, el brief y las casillas del plan contienen
estados históricos. Para conocer el avance debe consultarse el registro de
continuidad y contrastarlo con código y evidencia, sin interpretar una casilla
sin actualizar como prueba de que un archivo no existe.

## 9. Orden de continuación

1. Revisar y preservar los cambios documentales; decidir qué versiones integran
   la entrega y armonizar el SRS si se publican varios formatos.
2. Al autorizar la reanudación, verificar rama, HEAD, tag y estado del árbol.
3. Completar D con credenciales y presupuesto explícitos, sin atribuir resultados
   reales a adaptadores deterministas.
4. Continuar E a J con evidencias y commits locales según el plan.
5. Tratar producción como un alcance propio y cerrar sus requisitos antes de
   exponer el sistema o declararlo listo para uso público.

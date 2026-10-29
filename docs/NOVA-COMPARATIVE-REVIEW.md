# Nova Assistant: revisión comparativa para AI SWE

Fecha: 29 de octubre de 2026. Repositorio público: https://github.com/j-hernandez-dev/nova-assistant

Referencia fijada: `0bc7e8851790167c13a1be39697f4b136150f73d`. Base local de AI SWE: `06a40bb`.

## Alcance y evidencia

Se inspeccionaron el README, licencia y 13 archivos concretos de código/pruebas descargados del commit indicado. No se instaló Nova, no se ejecutó su código ni su suite y no se descargaron modelos. La revisión acredita implementación por lectura estática, no que cada función funcione en nuestro equipo.

Índice y hashes de las fuentes consultadas: `_tmp/nova-reference/source-manifest.json`. Los archivos ajenos permanecen en `_tmp/nova-reference/sources/`, fuera del código del producto. No se han copiado módulos de Nova al runtime de AI SWE.

## Diferencia de productos

Nova es un asistente de escritorio local con Ollama, conversación, proyectos, fuentes y herramientas. AI SWE se centra en ingeniería sobre Git: requisitos, plan, propuesta estructurada, pruebas, revisión y promoción tras aprobación. Comparten problemas de configuración, eventos y permisos; no conviene reemplazar nuestro grafo por su motor conversacional.

## Qué adaptar, con qué prioridad

| Prioridad | Patrón encontrado en Nova | Evidencia específica | Adaptación propuesta en AI SWE | Estado local |
|---|---|---|---|---|
| P0 | Preparación del sistema como dato del backend, con causa y acción requerida | `desktop/src/components/ReadinessNotice.tsx`; `tests/test_gui_readiness.py` | Comprobación previa por proyecto/ejecución: raíz Git, HEAD, proveedor, roles y disponibilidad conocida; mostrar causa antes de ejecutar | Tenemos preflight y error específico sin HEAD; falta una vista previa integral |
| P0 | Reconsulta visible con protección contra consultas duplicadas | `ReadinessNotice.tsx`, `recheck()` | Mantener carga/éxito/error y añadir comprobación de preparación sin iniciar inferencia | Releer del servidor ya implementa carga/error/resultado; no duplicarlo |
| P1 | Git disponible y repositorio válido como capacidades distintas | `local_cli/git_capability.py`, `tests/test_git_capability.py` | Separar Git ausente, ruta inválida, raíz diferente y commit base ausente | Nuestro requisito HEAD es más estricto y debe conservarse |
| P1 | Recuperación explícita de consumidores de eventos atrasados | `local_cli/application/events.py`, `SessionEventStream.poll()` | Detectar huecos de secuencia, releer snapshot y reconciliar SSE sin duplicar acciones ni mostrar progreso antiguo | Existen SSE/cursor/relectura; evaluar el caso de pérdida de eventos antes de ampliar |
| P1 | Estados de efectos y frontera de herramientas tipados | `local_cli/application/tool_runtime.py` | Distinguir nodo terminado, propuesta producida, prueba ejecutada y promoción comprobada | Evitar que `coder.completed` se interprete como código generado cuando hubo preflight fallido |
| P1 | Límite de espera inicial distinto del límite por inactividad de streaming | `local_cli/providers/stream_control.py`, `ResponseDeadline` | Mostrar si se espera conexión/respuesta; añadir deadlines acordes al adaptador. Reintentar solo cuando el efecto y el gasto sean conocidos | El gateway ya tiene timeout/reintentos; no añadir otro bucle automático encima |
| P2 | Observaciones de recursos conocidas o desconocidas | `local_cli/infrastructure/capabilities.py` | No afirmar RAM/VRAM disponible ni recomendar modelos si no se midieron; conservar CPU/int8 como vía validada | Hardware limitado; no volver a habilitar GGUF descartados sin evaluación |
| P2 | Cancelación cooperativa separada de confirmación de terminación | `local_cli/application/cancellation.py`, `application/process.py` | Diseñar cancelación por capas con recibo de qué se detuvo y qué pudo ocurrir | Cancelación actual 501; no habilitar un botón que prometa reversión |

## Hallazgos que impiden una copia directa

### 1. El detector Git de Nova no soluciona nuestro bloqueo sin HEAD

Su función comprueba la disponibilidad de Git y `--is-inside-work-tree`. No exige un commit inicial. Esa capacidad basta para algunas herramientas de Nova, pero no para crear nuestro worktree desde HEAD. Copiarla sin extensión reintroduciría la confusión entre «tiene .git» y «está listo para generar en sandbox».

Referencia: https://github.com/j-hernandez-dev/nova-assistant/blob/0bc7e8851790167c13a1be39697f4b136150f73d/local_cli/git_capability.py

### 2. Preparado no significa inferencia verificada

Las pruebas de readiness contemplan proveedor no verificado, cambio de identidad durante el probe y preservación del estado de sesión. El patrón útil es reportar lo que se sabe, no forzar una inferencia para pintar «listo». En AI SWE: token presente y modelo elegido son configuración; permisos, saldo y respuesta funcional requieren evidencia adicional, con gasto autorizado si hay inferencia.

Referencias:
- https://github.com/j-hernandez-dev/nova-assistant/blob/0bc7e8851790167c13a1be39697f4b136150f73d/desktop/src/components/ReadinessNotice.tsx
- https://github.com/j-hernandez-dev/nova-assistant/blob/0bc7e8851790167c13a1be39697f4b136150f73d/tests/test_gui_readiness.py

### 3. Eventos: snapshot y secuencia antes que un porcentaje inventado

El stream inspeccionado detecta pérdida de eventos retenidos y produce una señal de hueco junto con un snapshot de sesión. Podemos estudiar ese mecanismo para recuperar un panel tras reconexión. No debe reejecutar Coder, herramientas ni aprobaciones al reconstruir la vista.

Referencia: https://github.com/j-hernandez-dev/nova-assistant/blob/0bc7e8851790167c13a1be39697f4b136150f73d/local_cli/application/events.py

### 4. Nova tampoco es una solución de aislamiento fuerte

La documentación declara ejecución de shell con permisos del host y ausencia de aislamiento físico general de archivos/red. Sus permisos y grants son útiles para controlar admisión de operaciones; no convierten el proceso en contenedor ni VM. No presentar su adopción como cierre del riesgo del Runner de AI SWE.

Referencia: https://github.com/j-hernandez-dev/nova-assistant/blob/0bc7e8851790167c13a1be39697f4b136150f73d/docs/security_v12/s8_limits.md

## Qué no priorizar ahora

- Migrar a Electron o incorporar navegador/WebView2 solo para imitar Nova: aumenta empaquetado y dependencias sin demostrar que Coder genere correctamente.
- Descargar Qwen local grande, embeddings o memoria semántica por defecto. Nuestra vía híbrida y FTS5 deben mantenerse hasta medir otra alternativa.
- Incorporar herramientas de shell/navegador libremente al Coder: ampliaría autoridad respecto del contrato actual de propuesta de archivos.
- Sustituir las puertas de requisitos/promoción por aprobaciones conversacionales.
- Declarar cancelación fiable, aislamiento o recuperación completa basándose en el README o en pruebas que no hemos ejecutado.

## Licencia y atribución

La licencia publicada es MIT y conserva atribuciones de Nova Assistant (2026) y lutelute (2025). Si se reutilizan partes sustanciales de código, conservar licencia y avisos, registrar archivos/commit de origen y añadir la atribución al paquete. Esta revisión solo cita y analiza; no introduce código ajeno en el producto.

Referencia: https://github.com/j-hernandez-dev/nova-assistant/blob/0bc7e8851790167c13a1be39697f4b136150f73d/LICENSE

## Ruta recomendada, sin desviar la corrección activa

1. Completar primero el E2E de nuestra app con repositorio correcto y Coder/Reviewer reales dentro del límite acumulado de 5 USD autorizado el 29 de octubre. Registrar cada reserva y resultado. No atribuir un fallo de selección/preparación de proyecto al modelo.
2. Adaptar el patrón readiness como comprobación previa y ayuda accionable, extendido con HEAD y modo «existente» frente a «nuevo».
3. Probar y corregir huecos de eventos y estados inciertos que se reproduzcan en nuestra implementación.
4. Evaluar deadlines/cancelación y aislamiento con sus propias actas y criterios de aceptación.

El diagnóstico en la sesión actual mostró el formulario en modo «Nuevo proyecto Git» sobre un clon existente; el alta falló por carpeta no vacía. Cambiar al modo de registro existente permitió registrar el clon sin alterar sus archivos. Es una fricción de interfaz que readiness y una selección de modo más explícita pueden prevenir. No hubo inferencia para realizar esa corrección de registro.

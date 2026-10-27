# Evaluación parcial de la modalidad híbrida

Fecha: 26 de octubre de 2026, America/Mexico_City.

Esta evaluación usa casos sintéticos del laboratorio. No acredita el flujo
completo del producto, seguridad de un modelo ni capacidad de resolver proyectos
arbitrarios. La Fase D continúa abierta y el routing del runtime no se ha cambiado.

## Objetivo y método

Evaluar Analyst y Supervisor locales, y Coder y Reviewer por API. Cada rol tiene
dos casos y dos repeticiones por candidato. Una respuesta JSON válida no basta:
debe cumplir el contrato Pydantic y las comprobaciones semánticas existentes.
No se ejecuta código generado por los modelos durante esta evaluación.

Se reutilizaron ModelGateway y OpenAICompatibleAdapter. El evaluador local
reutilizable está en `tools/model_lab_local.py`; restringe destinos a loopback,
no utiliza proxies del entorno y no tiene fallback de pago. El llamante controla
el arranque y cierre del motor, la RAM y los checksums de los archivos.

## Evidencia remota

Catálogo público consultado: 269 pares modelo/proveedor. Tarifas y disponibilidad
corresponden a esa consulta; no son una promesa de precios futuros.

| Candidato y proveedor | Código | Revisión | Conclusión limitada |
| --- | --- | --- | --- |
| Qwen2.5-Coder-32B-Instruct, nscale | 4 de 4 correctos | 4 de 4 correctos | Candidato provisional para ambos roles |
| Qwen3-32B, nscale | 4 de 4 correctos | 2 de 4 correctos | No seleccionado para revisión; falló el esquema en ambos intentos del caso negativo |

Los 16 intentos de esta comparación tuvieron un coste estimado de 0.00180858 USD,
calculado con usage y tarifas del catálogo; no es una factura conciliada.
La primera prueba válida, anterior a la comparación, estimó 0.00006852 USD.

Dos comprobaciones adicionales con Qwen2.5-Coder-32B:

- JSON Schema estricto: HTTP 200 y objeto correcto en un esquema booleano mínimo.
  No se extrapola a todos los contratos del producto.
- Tool calling con selección forzada de función: HTTP 400. Esta combinación
  concreta no quedó validada. No se ejecutaron herramientas ni se añadió soporte
  de tools al contrato del runtime.

La existencia de credencial no garantizaba crédito disponible: antes de la recarga
se observó HTTP 402. Se corrigió su clasificación como `MODEL_BILLING_ERROR`, no
recuperable, y el laboratorio aborta toda la batería ante ese error o autenticación
rechazada. La regresión reprodujo 32 intentos antes de la corrección y uno después,
usando únicamente MockTransport.

## Evidencia local y recursos

Equipo observado: 15.79 GiB de RAM total y GTX 1650 Ti de 4096 MiB VRAM.
La RAM libre pasó de 0.97 a 3.87 GiB después de que el usuario cerrara aplicaciones.
Las pruebas realizadas utilizaron CPU, no aceleración CUDA. No se suman RAM y VRAM.

Se descargaron únicamente archivos públicos fijados por revisión y SHA-256:

| Modelo | Revisión | Archivo y tamaño |
| --- | --- | --- |
| Qwen2.5-1.5B-Instruct-GGUF | `91cad51170dc346986eccefdc2dd33a9da36ead9` | Q4_K_M, 1117320736 bytes |
| Qwen3-1.7B-GGUF | `90862c4b9d2787eaed51d12237eafdfe7c5f6077` | Q8_0, 1834426016 bytes |

Motor: llama.cpp b11700 CPU, SHA-256 del ZIP
`4e2af6b2b39691cd84267a02839596ed6653ea2dde5ee9cdbfeb4dd9677eecbb`.
Contexto 4096, lote 128, cuatro hilos y una ranura. Servidor oculto en loopback,
clave efímera y entorno sin variables de credenciales. El proceso propio se cierra
al terminar cada evaluación. No se modifica ni ejecuta el notebook del usuario.

Qwen2.5-1.5B Q4_K_M:

- Con solo los casos del laboratorio: 4 de 8 correctos, todos de solo lectura.
- Con prompts reales de Analyst y Supervisor: 2 de 8 correctos, ambos del caso
  de interpretación de inspección.
- No seleccionado para ninguno de los dos roles. Cambiar los prompts no produjo
  evidencia suficiente; no se relajaron los criterios de calidad.

Qwen3-1.7B Q8_0 con prompts reales obtuvo 5 de 8 casos correctos: ambos de
interpretación de inspección, uno de planificación de modificación y ambos de
planificación de inspección. Fallaron los dos de interpretación de modificación
y una planificación de modificación. No se selecciona para ninguno de los roles
porque no completó correctamente ambos casos repetidos de cada rol.
Se desactiva su modo de razonamiento en la plantilla; el límite de salida sigue
siendo 512 tokens y no se ocultan errores o truncamientos.

Como referencia adicional, Qwen2.5-Coder-32B remoto pasó 4 de 4 intentos de Analyst.
En Supervisor pasó inspección, pero los dos planes de modificación se truncaron
a 512 tokens. Se hizo configurable el límite del laboratorio y se repitió
Supervisor con 1024: desapareció el truncamiento, pero los dos planes de
modificación siguieron sin cumplir el criterio semántico. Esa referencia tampoco
se selecciona para Supervisor. No se modificaron las aserciones de calidad.

## Presupuesto y seguridad

El límite autorizado es **3 USD en total**, no por ejecución. Se mantiene un ledger
local en `_tmp/hybrid-validation/spend-ledger.json`, reservando antes de cada lote
el contexto máximo publicado más la salida máxima. Las reservas no se devuelven
por errores o ausencia de usage. Consultar su snapshot en el JSON adjunto antes
de nuevas peticiones; los experimentos locales no consumen inferencia de pago.

Reserva no equivale a gasto facturado. El coste de energía y equipo local no se
midió y permanece desconocido. Los rechazos previos sin usage tampoco se presentan
como coste cero confirmado. No se exportan credenciales ni respuestas brutas.

Al cerrar este checkpoint: reserva acumulada 0.22656320 USD; quedan 2.77343680 USD
sin reservar de la autorización original. La suma conocida estimada de intentos
con usage es 0.00299420 USD. El JSON preserva por separado estimación y reservas.

## Verificación y continuidad

- Suite offline completa tras la corrección compartida: 715 PASS, 3 SKIP, 0 FAIL,
  en 195.823 segundos; XML local `full-offline.xml`.
- Después se añadió una comprobación focalizada de reutilización de prompts:
  las seis pruebas de `test_model_lab_local.py` pasan y Ruff focalizado pasa.
- Dos regresiones adicionales cubren salida ampliada y reserva de gasto previa:
  el conjunto focalizado del laboratorio termina con 28 PASS. No se afirma haber
  repetido toda la suite después de estas dos incorporaciones y la de prompts.
- Ruff sobre toda la carpeta de modelos señaló dos E501 ya existentes en
  `gateway.py`, fuera del cambio. No se modificaron para ampliar el alcance.
- Falta escoger roles locales con evidencia suficiente, terminar la evaluación
  requerida de D y comprobar integración y promoción E2E en E.
- No hay EXE, instalador o release final nuevos. No se ha declarado producción.

La decisión pendiente del responsable del producto es mantener el respaldo
determinista local existente para Analyst/Supervisor y avanzar en integración de
Coder/Reviewer remotos, o evaluar un modelo local mayor antes de integrar. La
primera opción cambia el objetivo provisional de modelos locales, no demuestra
cumplidas todas las condiciones originales de D/E. No se cierra ninguna fase
basándose en una sustitución no aceptada.

Resultados y snapshot de reservas: [HYBRID-MODEL-LAB-EVIDENCE.json](HYBRID-MODEL-LAB-EVIDENCE.json).
Los archivos de pesos y motor están en `_tmp/local-assets/`, ignorados por Git.

## Fuentes

- https://huggingface.co/docs/inference-providers/en/hub-api
- https://huggingface.co/docs/inference-providers/en/pricing
- https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF
- https://huggingface.co/Qwen/Qwen3-1.7B-GGUF
- https://github.com/ggml-org/llama.cpp/releases/tag/b11700

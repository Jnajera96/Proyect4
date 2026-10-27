# Validación del perfil híbrido con modelos reales

Fecha: 26 de octubre de 2026. Alcance: producto local, una persona por instalación.

## Perfil aceptado y resultado

El usuario aceptó mantener Analyst y Supervisor deterministas y utilizar API
únicamente para Coder y Reviewer. Researcher, políticas, Git y pruebas siguen
locales. Esto sustituye el objetivo provisional de cargar modelos locales para
los dos primeros roles; no afirma que los GGUF descartados hayan sido validados.

Se verificaron sobre repositorios sintéticos descartables los recorridos:

| Recorrido | Evidencia |
| --- | --- |
| Confirmar requisitos → revisar → aprobar | Promueve exclusivamente `src/app.py`, con pruebas reales correctas |
| Confirmar requisitos → revisar → rechazar | Termina cancelado y conserva limpio el repositorio original |
| Confirmar requisitos → revisar → pedir cambios → aprobar | Atiende el comentario, vuelve a revisar y conserva el original hasta aprobar |

Modelo fijado para ambos roles remotos:
`Qwen/Qwen2.5-Coder-32B-Instruct:nscale`, mediante OpenAICompatibleAdapter y
ModelGateway. No se añadieron SDKs ni se invocaron CLIs externas de agentes.
El grafo ejecutó realmente las dos puertas humanas, SQLite, worktrees, pruebas
`pytest.unit`, revisión y promoción. Las decisiones del verificador son entradas
explícitas de los escenarios sintéticos autorizados; no aprobación automática
del producto en repositorios del usuario.

La primera petición sintética, menos explícita, no convergió. No se escondieron
los dos intentos fallidos ni se debilitó el veto del Reviewer. La petición usada
para la matriz exitosa declara que la prueba existente ya exige `f() == 42` y no
debe modificarse. Una batería pequeña no acredita calidad general en proyectos
arbitrarios, y el Reviewer puede exigir intervención adicional.

## Cambios y defectos verificados

- `AI_SWE_REMOTE_MODEL_ROLES` permite activar exclusivamente `coder` y `reviewer`.
  Su valor por defecto es `[]`, conservando la operación offline.
- Los nodos se vinculan a la configuración del motor; el gateway es perezoso,
  se cierra por invocación y se aísla mediante ContextVar. No se intercambian
  configuración o credenciales entre instancias concurrentes.
- Los roles no habilitados entran directamente al camino determinista. La
  selección del modelo Reviewer respeta la configuración de esa instancia.
- El Reviewer recibía la codificación de reemplazo del Coder (`/dev/null`) aunque
  el worktree modificase un archivo existente. El rechazo real permitió reproducir
  el defecto con una prueba offline. Ahora recibe `artifacts.diff`, el diff Git
  aplicado que sirve como referencia para la promoción. No se relajó el gate.
- La primera suite completa detectó una importación de modelos a nivel de módulo.
  Se conservó su aserción y se restauró la frontera de construcción perezosa ya
  existente en los nodos. La regresión focalizada quedó aprobada.

## Configuración reproducible

Este ejemplo explica el perfil; no activa ni modifica automáticamente `.env`.
Las llamadas del producto son de pago y no deben confundirse con las pruebas
offline. El token real permanece fuera de Git.

```dotenv
HF_TOKEN=valor_privado_configurado_localmente
AI_SWE_MODEL_PROVIDER=openai_compatible
AI_SWE_MODEL_BASE_URL=https://router.huggingface.co/v1
AI_SWE_MODEL_NAME=Qwen/Qwen2.5-Coder-32B-Instruct:nscale
AI_SWE_REVIEWER_MODEL=Qwen/Qwen2.5-Coder-32B-Instruct:nscale
AI_SWE_MODEL_API_KEY=${HF_TOKEN}
AI_SWE_REMOTE_MODEL_ROLES=["coder","reviewer"]
```

El proveedor devuelve `Qwen/Qwen2.5-Coder-32B-Instruct` sin el sufijo de ruta.
La tabla de precios debe declarar tanto ese identificador como el solicitado,
con las tarifas verificadas del mismo proveedor. En la consulta utilizada:
0.06 USD/millón de entrada y 0.20 USD/millón de salida, equivalentes a
0.00006 y 0.0002 por mil tokens. No son precios garantizados para futuras fechas.
Un identificador no reconocido produce coste desconocido; un acumulador de
coste conocido en cero no demuestra que las llamadas hayan sido gratuitas.

## Reproducción y controles de gasto

```powershell
.venv\Scripts\python.exe -m tools.verify_hybrid_models
# La ejecución anterior no hace inferencia.

# Solo con credencial, catálogo vigente y ledger de autorización existente:
.venv\Scripts\python.exe -m tools.verify_hybrid_models --run-real --scenario approve
.venv\Scripts\python.exe -m tools.verify_hybrid_models --run-real --scenario reject
.venv\Scripts\python.exe -m tools.verify_hybrid_models --run-real --scenario changes
```

El verificador no crea ni renueva la autorización económica. Usa el ledger local
existente y reserva 18 intentos máximos por escenario, considerando el límite de
llamadas y los reintentos del gateway. Se conservan las reservas de intentos
fallidos. Solo trabaja en repositorios creados bajo `_tmp/hybrid-e2e/`.

La evidencia consolidada, incluidas las fallas iniciales y el snapshot de reservas,
se conserva en [HYBRID-E2E-EVIDENCE.json](HYBRID-E2E-EVIDENCE.json). Los cuerpos
de respuestas y secretos no se exportan. El cargo final se verifica en la cuenta;
las estimaciones locales no sustituyen la factura.

## Límites y continuidad

Suite offline final: 725 PASS, 3 SKIP y 0 FAIL en 159.882 segundos. Ruff de los
archivos nuevos y de configuración/workflow pasa. Evidencia local:
`_tmp/hybrid-validation/routing-full-final.xml`.

Esta validación corresponde al motor y sus gates. La matriz de navegador del
perfil instalado, voz real, ejecutable e instalador pertenece a las fases
posteriores. D conserva sus límites documentados de tool calling y evaluación
de modelos. La ruta E se adaptó expresamente a roles ligeros deterministas.
No se declara producción ni se crea el tag final `v0.1.0`.

## Acta de cierre de E — perfil híbrido aceptado

Se revisaron nuevamente los informes originales y su consolidado al iniciar G.
**E cerrada para Analyst/Supervisor deterministas locales y Coder/Reviewer con
Qwen2.5-Coder-32B-Instruct:nscale**, integrado en `5849282`.

- `ade1dc89`: completado con promoción real de `src/app.py`, resultado 42,
  original intacto hasta aprobar, dos llamadas de modelo; coste estimado con
  ambos alias de precio: 0.00021114 USD.
- `bd5ca540`: rechazo completado, original limpio y sin promoción.
- `04ef6878`: pedir cambios y aprobar completado; original intacto hasta aprobar.
- Los reportes originales están bajo `_tmp/hybrid-e2e/<id>/report.json` y se
  consolidaron en `HYBRID-E2E-EVIDENCE.json`. Incluyen los intentos fallidos previos.
- No falta una corrida de promoción con modelo real; no se repitió ni se consumió
  inferencia adicional para redactar esta acta. Ledger acumulado: autorización
  3 USD, reserva conservadora 1.17225088 USD, saldo sin reservar 1.82774912 USD.

El cierre es del motor y perfil acordado: no convierte en validados los GGUF
descartados, tool calling, paquete instalado, equipo limpio ni producción.

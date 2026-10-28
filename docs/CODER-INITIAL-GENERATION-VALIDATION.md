# Ruta 3, entrega 1: contexto inicial del Coder

Fecha: 28 de octubre de 2026. Base: `dc5c194`. Esta entrega corrige el motor; las mejoras de interfaz se mantienen como siguiente entrega.

## Observación y causa verificada

Las capturas de `run-ac3070968ca` muestran petición y respuesta de Qwen2.5-Coder-32B-Instruct vía nscale. El modelo respondió sin archivos y justificó que faltaban fallos previos o correcciones del Reviewer. No era ausencia de llamada al modelo.

El contexto construido en `_coder_del_modelo` incluía incondicionalmente una orden de corregir fallos de la última ejecución, incluso al implementar una petición por primera vez. Además, `escalate_no_changes` atribuía toda propuesta vacía a una fase antigua sin modelo. Dos regresiones reprodujeron ambos defectos antes de modificar el motor. La influencia del prompt sobre esta respuesta remota es una hipótesis coherente con las capturas; no se volvió a consultar al proveedor para comprobarla.

## Corrección

- Sin pruebas, revisión o comentarios previos: Coder recibe instrucciones de implementación inicial. Puede crear archivos y pruebas en un repositorio con solo README; una modificación inicial sigue usando la evidencia del código existente.
- Con pruebas, revisión o comentarios del usuario: recibe instrucciones de corrección apoyadas en esa evidencia real. Se conserva la evidencia vigente, la redacción de secretos y los límites del alcance.
- Se añaden al contexto la interpretación humana confirmada y el alcance autorizado. No se modifican las puertas humanas ni se autoriza salida del sandbox.
- Una propuesta vacía validada informa que el modelo respondió sin archivos y conserva su explicación. Si falta una propuesta validada, el mensaje remite a la configuración y a los errores reales sin atribuir falsamente la causa a M1.
- No se añaden reintentos pagados automáticos ni se convierten propuestas vacías en éxito.

## Verificación

Suite focalizada: **91 PASS, 0 omitidas, 0 fallos, 0 errores**, 104.834 segundos. Archivos: `test_f6_real_coder.py`, `test_calculator_pipeline.py`, `test_project_builder_pipeline.py`, `test_f9_reviewer.py` y `test_f12_promotion.py`. XML local: `_tmp/coder-first-generation-suite.xml`.

Se verifican creación y modificación en primera petición, corrección con stdout/stderr y Reviewer, respuesta vacía sin inventar ausencia de modelo, E2E con adaptadores simulados y herramientas pytest/Ruff reales, y controles de promoción. No se repitió toda la suite del producto: la base anterior ya tenía 889 aprobadas y 4 omitidas; esos resultados no se suman a los 91 de esta entrega.

TypeScript y Vite compilaron durante la construcción. El hash del `nodes.py` empaquetado coincide con el de la fuente. Evidencia de smoke portable: `_tmp/coder-initial-portable-smoke/report.json`.

Smoke portable completo aprobado: 14 comprobaciones, manifiesto, ausencia de secretos/estado de desarrollo, autenticación por perfil, frontend integrado, ejecución determinista con confirmación humana, cierres y persistencia tras reinicio. Informe durable: `docs/evidence/coder-initial/portable-smoke.json`. Este smoke no llama a Qwen ni prueba generación remota.

## Entrega y uso

Nuevo candidato: `dist/windows-v0.2.0-coder-initial-rc1/AISWESystem-windows-x64.zip`. Extraer completo y ejecutar `AISWESystem/AISWESystem.cmd`. Cerrar previamente el servidor antiguo para evitar seguir usando otro backend en el mismo puerto. Iniciar una ejecución nueva; las ejecuciones históricas conservan sus resultados originales.

SHA256: `4e0cee9858d2cdfddd2ea49ce36fd90723895f90f71e330ad751fb2c74bfe3a6`. Integridad ZIP verificada: 4745 entradas, ninguna dañada. Ruff de los dos archivos de pruebas modificados aprobado.

No se tocaron bóvedas ni credenciales de usuarios. El proveedor sigue configurándose por perfil. No hubo llamadas pagadas: el ledger anterior permanece en 2.99999104 USD reservados de 3 USD. Una nueva prueba remota requiere una nueva autorización de gasto; no se certifica que el modelo siempre genere una calculadora universitaria a partir de una petición amplia.

## Próxima entrega de la ruta 3

Actualización del servidor con resultado visible, inspección de etapas desde Workflow y eliminación de registros duplicados sin borrar carpetas o repositorios remotos. La ampliación del alcance de la calculadora debe confirmarse en requisitos antes de implementar funciones adicionales.

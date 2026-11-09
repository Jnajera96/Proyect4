# Auditoría de configuración de modelos y presupuesto

Fecha de revisión 9 de noviembre de 2026. Árbol principal de proyecto4-ai-swe.

## Diagnóstico y cambios

| Comportamiento anterior | Comportamiento implementado |
| --- | --- |
| Un token persistido podía viajar al proxy local en la primera petición. | El adaptador omite Authorization en loopback y la bóveda elimina la credencial al guardar una configuración local. |
| Cambiar el endpoint conservaba la clave anterior. | La conservación de credencial exige el mismo endpoint. El formulario limpia el token pendiente cuando cambia el endpoint. |
| Los controles de presencia y gateway exigían clave incluso en local. | Ambos aceptan localhost, 127.0.0.1 y ::1 sin clave. |
| Las tarifas locales podían conservar importes heredados o JSON inválido. | Se reconstruyen automáticamente a cero para los modelos elegidos. El JSON local es de solo lectura. |
| La disponibilidad del modelo se descubría al ejecutar Coder. | El botón Probar conexión consulta GET /models y ofrece los identificadores recibidos en el selector. |
| Un error 400 podía provocar sustitución por cualquier modelo del catálogo. | Se reconocen alias con prefijos y tags. omniroute-combo permite seleccionar el primer modelo viable si el combo literal falta. Las coincidencias ambiguas se dejan para elección del usuario. |
| Token y eliminación competían mediante un checkbox visible. | La interfaz ofrece estados de credencial y acciones Reemplazar token y Eliminar token. |
| Un resultado de conexión podía quedar desfasado respecto al formulario. | Se verifica la revisión del formulario antes de aplicar el autocompletado. El guardado es independiente del resultado del catálogo. |

Los presets conservan límites editados y roles seleccionados, siguiendo la nueva indicación adjunta. Esto reemplaza para esta intervención la preferencia anterior de reiniciar los presupuestos al cambiar de proveedor.

## Fronteras de seguridad y alcance

- El endpoint POST /auth/vault/test-connection exige sesión y CSRF. La consulta corre fuera del bucle ASGI.
- El cliente de catálogo tiene timeout, límite de tamaño, límite de modelos y redirecciones desactivadas. Las credenciales solo se reutilizan para el mismo endpoint.
- Las pruebas remotas de catálogo admiten Gemini, Hugging Face Router, OpenRouter y OpenAI. Esta lista evita que el nuevo endpoint consulte destinos remotos arbitrarios. Los endpoints loopback son compatibles con OmniRoute, Ollama, LM Studio y vLLM que expongan /models.
- El modo loopback implementado usa conexión sin Authorization. Un proxy local que exija autenticación devolverá un diagnóstico de credencial rechazada.
- Consultar /models acredita acceso al catálogo y coincidencia del identificador. La capacidad de inferencia, las cuotas y el contrato de generación se verifican durante la ejecución.
- Las tarifas locales a cero son una política de contabilidad de AI-SWE. Un proxy local puede utilizar cuentas externas facturadas.
- El cifrado existente AES-GCM y el ledger conservan sus controles. Los límites acumulados, horarios y por ejecución siguen siendo explícitos. La comprobación del catálogo no altera reservas.
- El guardado HTTP conserva la validación de contratos existente. La comprobación de conexión es informativa y permite autocompletar los modelos. Se pueden guardar identificadores personalizados sin consultar el catálogo.
- La intervención se realizó sobre el checkout principal, cuya base es anterior al RC33 del worktree secundario. Los cambios requieren integración y empaquetado antes de distribuirse en un portable.

## Verificación

Frontend con Node.js 24.22.1. La suite estados.test.mjs aprobó 51 pruebas y npm run build compiló TypeScript y Vite.

La suite nueva test_vault_connection.py usa MockTransport y pruebas de sesión y CSRF. Cubre exclusión de credenciales residuales, ausencia de sustitución arbitraria de modelos, URLs inválidas, errores de catálogo y configuración local sin token.

Las pruebas de inferencia real estuvieron desactivadas. Tras corregir el bloqueo de guardado, la regresión completa terminó con 1.322 aprobadas, 29 omitidas y 2 pruebas reales excluidas en 494,31 segundos. La verificación focalizada final de conexión, perfiles y regresiones RC30 terminó con 65 aprobadas. Incluye guardado sin consulta de catálogo en los cuatro proveedores, alias, tags, combo local, catálogos extensos y Ollama vacío. La suite de frontend final aprobó 51 pruebas y npm run build terminó sin errores con Node.js 24.22.1 y Vite 5.4.21.

El gasto de inferencia de esta intervención fue 0,00 USD. Las respuestas HTTP de las nuevas pruebas proceden de MockTransport. La validación de fuentes no sustituye la comprobación posterior del portable actualizado ni una generación real con las credenciales del usuario.

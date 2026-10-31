# Pruebas reales de rutas de modelos — 31 de octubre de 2026

Base: `37e029d`. Se mantienen en pausa el piloto entre PC y la publicación real GitHub por instrucción del usuario.

## Resultado

Las diez rutas del selector respondieron a las sondas asignadas: **36/36 casos aprobados**. No se ejecutó código generado ni se alteraron repositorios de usuario. Esto verifica compatibilidad JSON/Pydantic y comportamientos pequeños por rol, no una aplicación completa ni calidad universal.

| Modelo / proveedor | Coder | Reviewer | Esquema nativo declarado |
| --- | ---: | ---: | --- |
| Qwen/Qwen2.5-Coder-32B-Instruct:nscale | 2/2 | 2/2 | Sí |
| Qwen/Qwen2.5-Coder-7B-Instruct:nscale | 2/2 | 2/2 | Sí |
| Qwen/Qwen3-32B:nscale | 2/2 | 2/2 | Sí |
| Qwen/Qwen3-235B-A22B-Instruct-2507:nscale | 2/2 | 2/2 | Sí |
| deepseek-ai/DeepSeek-V3.2:deepinfra | 1/1 | 1/1 | No; modo JSON probado |
| zai-org/GLM-4.7:deepinfra | 2/2 | 2/2 | Sí |
| moonshotai/Kimi-K2-Instruct-0905:novita | 2/2 | 2/2 | Sí |
| openai/gpt-oss-120b:nscale | 2/2 | 2/2 | Sí |
| Qwen/Qwen3-Next-80B-A3B-Instruct:deepinfra | 1/1 | 1/1 | No; modo JSON probado |
| moonshotai/Kimi-K2.7-Code:deepinfra | 2/2 | 2/2 | Sí |

## Método y límites

- Catálogo público HF consultado sin credencial: 282 rutas modelo/proveedor. Se contrastaron las diez seleccionadas, todas live.
- Ocho rutas: crear sumar(a,b), modificar f() para devolver 42, aceptar una corrección válida y solicitar cambios ante pruebas fallidas. Dos casos Coder y dos Reviewer por ruta.
- DeepSeek V3.2 y Qwen3 Next no declaran esquema nativo. Se probaron explícitamente code-return y review-bad en modo JSON; ambas aprobaron. No se deben descartar sólo por ese metadato: el adaptador valida Pydantic localmente.
- Una repetición por caso, temperatura 0, máximo 1024 tokens de salida, timeout 30 s y cero reintentos. No se activa fallback de modelo.
- Oráculos deterministas independientes en tools/model_lab_cases.py: AST de las funciones y decisiones/fixes requeridos del Reviewer. No se confía en la autoevaluación del modelo.
- La evidencia no prueba estabilidad entre repeticiones, resistencia general a inyección, tool calling, generación web interactiva ni promoción E2E. El recomendador del laboratorio requiere dos repeticiones; no se usó para declarar ganadores.
- Sólo Qwen2.5 Coder 32B conserva la evidencia histórica de aplicación E2E. No se asignó projectValidated=true a los otros nueve.

## Presupuesto y conciliación

El usuario autorizó hasta 2 USD en esta evaluación, sin superar 5 USD acumulados. Su captura mostró créditos 4,96 USD y uso de inferencia 0,04 USD. El ledger histórico tenía 4,99999104 USD reservados; reservas no equivalen a cargos. Se conservó idéntico, comprobando su SHA-256, y se abrió una autorización de sesión separada respaldada por esa captura.

Reserva conservadora de sesión: **1.9678412799999998951424 USD**, por debajo de 2 USD; sumada al uso previo de 0,04 USD queda por debajo de 5 USD. Considera todo el contexto declarado y el máximo de salida por intento. No se liberaron reservas por estimaciones de uso menores.

Coste calculado con los tokens reportados y tarifas del catálogo: **0,01962210 USD**. Las 36 respuestas incluyeron uso. Es estimación, no factura ni saldo consultado después del experimento. La reserva sigue retenida para no permitir un gasto adicional basado sólo en esa estimación.

Los únicos accesos externos fueron catálogo público, consulta gratuita de identidad y las 36 inferencias autorizadas. No se copiaron tokens a informes, SQLite, URL ni argumentos del proceso. Los resultados contienen métricas y clases de error, no cuerpos de respuesta.

## Implementación y reproducción

- tools/audit_model_catalog.py contrasta metadatos con el selector y muestra límites históricos sin credenciales ni inferencia.
- tools/validate_model_routes.py reutiliza el laboratorio y requiere --run-real, snapshot y ledger de sesión existentes, con evidencia y límites válidos. Por defecto no hace llamadas. Conserva resultados parciales y reservas ante fallo.
- El selector muestra fecha y conteos Coder/Reviewer; distingue las sondas de la evidencia E2E. Las dos rutas sin esquema nativo siguen disponibles con explicación de la compatibilidad observada en modo JSON.

Comandos seguros sin inferencia:

```powershell
uv run python -m tools.validate_model_routes
uv run pytest tests/test_model_route_audit.py tests/test_model_lab.py
```

No repetir --run-real con otro ledger nuevo para eludir reservas. Antes de una nueva evaluación hay que conciliar otra vez saldo, gasto y llamadas pendientes. No se incluye ningún token ni ledger de usuario en la distribución.

Evidencia durable: MODEL-ROUTE-PROBES-2026-10-31.json. Datos locales de autorización y reportes parciales: _tmp/model-route-validation-2026-10-31/.

## Próxima etapa

Comparar propuestas completas sobre productos nuevos con oráculos funcionales, usando primero las rutas económicas que aprobaron estas sondas. Esto requiere una nueva conciliación de reservas. Continúan pendientes optimización global 40–70%, tokenizer propio del proveedor y aislamiento fuerte de ejecución.

No se reconstruye el portable en esta tarea: rc11 sigue siendo el paquete verificado anterior. Los resultados y el selector actualizado pertenecen al código fuente de este cierre.


## Regresión y cierre

- Backend completo: **1.059 PASS, 4 SKIP, 0 fallos**, 566,64 s.
  `_tmp/model-route-full.xml`. Se conservan las 1.050 pruebas previas.
- Auditoría y laboratorio offline: **31 PASS**, `_tmp/model-route-offline-final.xml`.
- Frontend: **39 PASS**, TypeScript/Vite aprobado.
- Ruff focalizado y git diff --check aprobados.
- Sin push, sin cambios a v0.1.0 y sin operaciones sobre proyectos reales.
- Ambos worktrees se sincronizan en el commit de cierre; los únicos resultados
  de pago nuevos son las 36 sondas explícitamente autorizadas.

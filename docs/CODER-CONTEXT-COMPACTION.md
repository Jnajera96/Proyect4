# Compactación del contexto del Coder

Fecha: 31 de octubre de 2026. Base: `7e0aa4e`.
Se mantienen pausados los pilotos entre PC y GitHub, por instrucción del usuario.
Este cambio no hace inferencias remotas ni altera el presupuesto autorizado.

## Defecto y corrección

El Coder cortaba los últimos 20 hallazgos antes de eliminar repeticiones. En una
secuencia con una advertencia distinta seguida de 25 copias del mismo hallazgo,
se enviaban 20 copias y se perdía la advertencia. Ahora se eligen hasta 20 hallazgos
distintos, conservando la recencia de la última copia y el orden relativo. La
identidad incluye severidad, ruta, explicación y evidencia: hallazgos distintos
sobre el mismo archivo no se fusionan.

El resumen también repetía los primeros 120 caracteres de los bloques de código.
Cuando ese prefijo ya está presente en el bloque enviado, sólo se sustituye el
extracto duplicado por una referencia. Se conserva la ruta, severidad y explicación.
No se elimina contenido del bloque de código ni del historial de auditoría.

La redacción de secretos se realiza antes del recorte a 120 caracteres. Se verifica
un token sintético que comienza cerca del borde: no debe quedar un prefijo visible
por haber cortado el valor antes de aplicar el redactor.

No cambian el prompt de sistema, contratos, alcance, puertas humanas, reglas de
pruebas, historial FTS5, temperatura ni límite de salida del modelo. Los datos del
repositorio siguen dentro de bloques no confiables. La auditoría completa se
conserva en el estado; sólo se compacta su representación para el Coder.

## Medición antes/después

Benchmark offline con FakeModelAdapter y vocabularios exactos locales. Se capturó
la línea base inmediatamente antes del cambio, conservando los prompts vigentes
de 7e0aa4e. No se compara con un prompt histórico anterior a las reglas nuevas de
pruebas web. Mismos 15 archivos, consultas, historial y hashes de fixtures.

| Referencia | Tokens con memoria antes | Después | Ahorro adicional |
| --- | ---: | ---: | ---: |
| cl100k_base | 10.717 | 10.359 | 3,340487% |
| o200k_base | 10.161 | 9.832 | 3,237870% |

Es el total ponderado de las tres consultas del benchmark. No es una reducción de
factura. La selección de archivos y el conteo del bloque de código se mantienen;
las rutas y funciones críticas siguen presentes: cobertura 100% en este fixture.
La comparación simultánea contra naive también ejecuta el Coder nuevo en ambos
brazos: ahorro total actual 28,127385% / 29,916601%. **La meta global 40–70% no se
alcanza ni se declara cerrada.**

Escenario adicional de repetición: una advertencia distinta y 25 copias de un
hallazgo de inventario. Se ejecutaron las fuentes anterior y actual con el mismo
adaptador y prompt de sistema, verificando su SHA-256 idéntico.

| Referencia | Antes | Después | Reducción |
| --- | ---: | ---: | ---: |
| cl100k_base | 2.487 | 2.112 | 15,078408% |
| o200k_base | 2.299 | 1.941 | 15,571988% |

Antes: advertencia perdida y 20 copias. Después: advertencia conservada y una copia.
En ambos estados siguen los 26 hallazgos originales; no se borra evidencia. Este
caso mide repeticiones, no representa todas las tareas ni demuestra calidad remota.

## Verificación y reproducción

- Pruebas focalizadas: 14 PASS; histórico, redacción, límites y benchmark exacto.
- Redacción y compactación finales: 6 PASS antes de lanzar la regresión completa.
- Frontend: 39 PASS y build TypeScript/Vite aprobado.
- Ruff del test nuevo: aprobado. nodes.py tiene 22 diagnósticos Ruff preexistentes;
  se compararon código y mensaje contra 7e0aa4e: idénticos, cero nuevos. No se
  aplicó un formateo/refactor global ajeno al cambio. Incluyen estilo, un import
  sin uso y referencias a state en una rama inalcanzable; su limpieza queda pendiente.
- Evidencia durable: CODER-CONTEXT-COMPACTION-EVIDENCE.json.
- Informes locales: _tmp/context-compaction-before.json,
  _tmp/context-compaction-final.json, _tmp/repeated-context-before.json,
  _tmp/repeated-context-after.json y _tmp/context-compaction-lint/report.json.

```powershell
uv run pytest tests/test_coder_context_compaction.py tests/test_coder_historical_context.py tests/test_token_benchmarks.py
uv run python -m tools.benchmark_memory_tokens
```

Se usa el extra token-metrics ya instalado para conteo exacto. No se modifican
modelos, tokens de acceso, ledgers ni runtimes. No se reconstruye un portable:
rc11 sigue siendo el paquete anterior aprobado. Quedan optimización de selección
con calidad independiente, tokenizer del modelo servido, E2E de otras aplicaciones,
aislamiento fuerte y los pilotos expresamente pausados.


## Cierre de regresión

Backend final: **1.062 PASS, 4 SKIP, 0 fallos**, 485,47 s,
`_tmp/context-compaction-full.xml`. Se conservan las 1.059 pruebas previas.
Frontend: **39 PASS**, TypeScript/Vite aprobado. git diff --check sin errores;
Ruff del test nuevo aprobado y 22 diagnósticos previos idénticos en nodes.py.
El cierre se guarda en Git y sincroniza ambos worktrees, sin push ni alterar tags.

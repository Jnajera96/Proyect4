# Suficiencia de la ventana de código relevante

Fecha: 1 de noviembre de 2026. Base: `c7a77e8`. Validación offline sin gasto de API.

## Defecto reproducido

El selector encontraba correctamente una función, pero incluía cinco líneas
anteriores sin considerar sus longitudes. Esas líneas podían consumir los 1.800
caracteres del fragmento y dejar fuera la función solicitada. Dos casos sintéticos,
Python y JavaScript, reprodujeron la pérdida: `_tmp/context-window-before.xml`.

La corrección desplaza el inicio de la ventana cuando el contexto anterior impide
incluir la línea relevante y su implementación cercana. Conserva contexto previo
si cabe. No aumenta los límites de 32 KiB de lectura, 100 líneas de cuerpo ni 1.800
caracteres por bloque. Se mantienen delimitadores, marca de fragmento parcial,
redacción antes del recorte y tratamiento del contenido como datos no confiables.
Una línea o función que exceda por sí sola el presupuesto sigue siendo parcial;
esta corrección no promete enviar archivos completos ni resolver toda ambigüedad.

## Evidencia y alcance

- Dos pruebas fallaron antes y pasan después, conservando firma y cuerpo breve.
- Focalizadas de memoria, historial, compactación y tokenizer: **26 PASS**;
  `_tmp/context-window-final-focused.xml`.
- Regresión completa: **1.097 PASS / 4 SKIP**, 0 fallos/errores, 639,619 s;
  `_tmp/context-window-full.xml`, salida de pytest 0.
- Frontend: **39 PASS** y build TypeScript/Vite aprobado.
- ZIP rc16: **35 PASS**, `_tmp/context-window-rc16-tests.xml`, cargando sólo
  módulos y CPython de la extracción; incluye la corrección y protecciones del runner.
- Smoke estándar: **14/14 PASS**, ambos cierres código 0 y SQLite/checkpoint
  persistentes; `_tmp/context-window-rc16-smoke/report.json`.
- Ruff de pruebas nuevas aprobado; nodes conserva 22 avisos anteriores, cero nuevos.
- La primera corrida en el puente restringido falló en dos limpiezas de temporales
  por permisos; se conserva como fallida y se repitió fuera del puente.

El benchmark de los mismos 15 archivos conserva suficiencia crítica 100% y los
mismos tokens; ese fixture no contenía el caso de las líneas largas. Referencias
exactas locales, no tokenizer certificado de Qwen ni facturación del proveedor:

| Referencia | Sin memoria | Con memoria | Reducción del prompt completo |
| --- | ---: | ---: | ---: |
| cl100k_base | 14.413 | 10.359 | 28,127385% |
| o200k_base | 14.029 | 9.832 | 29,916601% |

Evidencia local: `_tmp/context-window-benchmark.json`. Se usó FakeModelAdapter y
vocabularios locales; no se alteraron fixtures ni reglas para aumentar el ahorro.
**La meta global de 40–70% sigue pendiente.**

## Entrega

Portable: `dist/windows-v0.2.0-rc16-context-window/AISWESystem-windows-x64.zip`.
SHA-256: `43a2616ab0256edcd66ebfe0635af0b2ccc8ff7d9bd7bec3965bd9bf4bf316a8`.
121.290.667 bytes; CRC, 4.736 hashes y correspondencia de módulos con fuente
verificados. CPython conserva firmas válidas de Python Software Foundation.
Rc15 y anteriores se conservan. Avance estimado: 85/100, sin cambio de ponderación.

Docker Desktop local e imagen de validación se prepararon aparte; no se integró
un backend Docker en el flujo de la aplicación. Ver `DOCKER-ISOLATION-PREPARATION.md`.

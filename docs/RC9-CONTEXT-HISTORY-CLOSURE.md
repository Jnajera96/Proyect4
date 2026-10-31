# RC9 — Contexto por contenido y medición del historial

Fuente: `8b1ff87`, que incluye la mejora del Coder de `3100e3c`.
Directorio nuevo: `dist/windows-v0.2.0-operational-rc9/`.
Se preservan rc8 corregido y todos los candidatos anteriores.

**RC9 aprobado para el host local validado**, con el alcance y límites indicados
en esta acta; no constituye aprobación de producción pública.

## Contenido

- Selección por contenido hasta 32 KiB/archivo y semillas asociativas sin depender
  exclusivamente del nombre de ruta.
- Hasta cinco bloques útiles de código existente para el Coder, redactados,
  parciales y tratados como datos no confiables.
- Las capacidades de perfiles, voz, puertas humanas, cancelación y recuperación
  permanecen en la misma arquitectura. No se añaden modelos ni dependencias.
- La medición multilenguaje FTS5 se conserva como herramienta de desarrollo;
  no es una nueva opción de usuario ni una promesa de ahorro.

## Artefacto

ZIP: `dist/windows-v0.2.0-operational-rc9/AISWESystem-windows-x64.zip`.

SHA-256:
`56f1fd866d079eb5d29714c6cea739aa5ceaf3e3f7c8e9f64f65946391d25c99`.

Tamaño: **118.798.364 bytes**. Manifiesto de **4.726 archivos** verificado;
comparación binaria de todo `src/ai_swe` con su copia empaquetada y CRC del ZIP
aprobados. Extracción nueva: `_tmp/rc9-zip-extracted/AISWESystem`.
Informe: `dist/windows-v0.2.0-operational-rc9/zip-report.json`.

CPython oficial 3.13.14 con firmas Authenticode válidas de Python Software
Foundation en python.exe y pythonw.exe. Se verifican versiones del lockfile y
hashes RECORD de las ruedas instaladas. No se generan ejecutables PE nuevos ni
se desactivan protecciones. Esto no significa que todas las DLL de terceros tengan
firma Authenticode ni garantiza aceptación por todas las políticas de otros equipos.

## Verificación

- 30 pruebas focalizadas de memoria/continuidad PASS:
  `_tmp/history-context-regression-final.xml`.
- 11 pruebas de memoria e historial PASS con el intérprete y módulos del ZIP,
  comprobando que ai_swe se importa desde la extracción, no desde src:
  `_tmp/rc9-packaged-memory.xml`.
- Frontend: 34 PASS; TypeScript/Vite aprobado durante la construcción de rc9.
- Regresión completa rc9: **994 PASS, 4 SKIP, 0 fallos**, 434.285 s;
  `_tmp/rc9-source-full.xml`.
- Smoke estándar de perfiles/reinicio: **14/14 PASS**, ambos cierres código 0,
  cero llamadas pagadas y logs sin WinError/traceback. Informe:
  `_tmp/rc9-standard-smoke/report.json`.

El verificador usa LOCALAPPDATA temporal y PATH limitado a System32, sin Python
ni Node de desarrollo. Comprueba autorización, frontend, registro y login cifrados,
ausencia de credencial global, puerta humana, checkpoint, SQLite y ambos cierres.
Mantiene los plazos estándar de 90 s/105 s; no usa instrumentación para aprobar.
Es un entorno aislado en este host, no una VM ni un segundo equipo independiente.
Ese smoke tampoco acredita generación remota ni promoción de un producto nuevo.

## Pendientes y avance

Se mantiene la estimación global **81/100** hacia Windows local confiable y
recuperable. El número de pruebas no sustituye la validación de calidad o destino.

Implementación pendiente: actualización/migraciones con respaldo y retorno seguro;
aislamiento fuerte de procesos, red y recursos antes de producción pública, más
los controles operativos de esa modalidad.

Validación pendiente: recuperación completa por UI entre dos equipos, matriz
Windows/SAC/voz, tokenizer exacto, utilidad del historial y calidad de más productos
con modelos reales, y publicación real en una cuenta/repositorio expresamente
autorizados. La interfaz de publicación y las piezas de continuidad ya existen.

No hubo llamadas pagadas, PAT reales, publicación ni tags. El límite histórico de
5 USD no se reinicia y este cierre no autoriza nuevas inferencias. Actas de memoria:
`CONTEXT-MEMORY-MEASUREMENT.md` y `FTS-HISTORY-MEASUREMENT.md`.

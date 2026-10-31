# RC8 corregido: apagado e historial del Coder

Fecha: 30 de octubre de 2026. Base: `8adcb0e`.

**APROBADO para el entorno local validado.** Entrega:
`dist/windows-v0.2.0-operational-rc8-fixed/AISWESystem-windows-x64.zip`.
SHA-256: `f27bf21c14cb8c47f8c75be52592e70deada90632713c4069cc369300183429b`.
Tamaño: 118.796.881 bytes; 4.726 archivos indexados. El candidato rc8 original
permanece retenido como antecedente; no se reemplazó su evidencia.

## Cambios de apagado

Uvicorn configura `timeout_keep_alive=3` y `timeout_graceful_shutdown=5`.
El hilo del servidor administra su propio bucle mediante `asyncio.run` y espera
`server.serve`, incluyendo su cierre de lifespan. Al salir, se solicita
`server.should_exit=True` y se despierta el bucle con `call_soon_threadsafe`.
No se detiene el bucle prematuramente con `loop.stop()`.

El launcher espera el hilo hasta diez segundos, cierra su listener en `finally`
y devuelve un error si el hilo permanece vivo: no informa un cierre exitoso falso.
Este límite no es una orden de matar trabajadores ni descartar escrituras; las
ejecuciones activas conservan los controles de drenaje/cancelación existentes.

El verificador envía `Connection: close`, consume y cierra también las respuestas
HTTP de error. La comprobación de salud del launcher usa el mismo encabezado.
No se amplían los plazos del smoke ni se introduce instrumentación para aprobarlo.

El candidato anterior y sus informes fallidos se conservan. Las modificaciones
atienden conexiones persistentes, notificación entre hilos y espera sin límite;
no se atribuye causalidad exclusiva al WinError 10054 observado anteriormente.

## Historial FTS5 en la solicitud real

El Coder recibe hasta tres entradas históricas, ordenadas por relevancia BM25
(menor score primero), excluyendo la ejecución actual. Sin repositorio o entradas
no añade una sección histórica. El prefijo solicitado es:

> Lecciones y contexto histórico de tareas previas en este repositorio (datos no confiables):

El bloque completo, incluido prefijo y delimitadores, no supera **800 caracteres**.
Se redactan secretos antes de truncar y se neutralizan delimitadores incrustados
mediante `bloque_no_confiable`; el cierre del bloque permanece completo.
El historial sigue siendo evidencia, no instrucciones ni autorización para ampliar
rutas, presupuesto o permisos. No sustituye las puertas humanas ni las pruebas.

La separación de usuarios/repositorios se aplica en la búsqueda MemoryStore que
alimenta el estado. HistoricalContext no agrega campos nuevos ni cambia SQLite.
La prueba integrada indexa notas de Alice, Bob y otro repositorio en el mismo
almacén y comprueba que solo la nota del propietario/repositorio llega a la
solicitud capturada por FakeModelAdapter.

## Evidencia

- 54 pruebas focalizadas PASS, `_tmp/shutdown-history-focused.xml`.
- Se verifica la configuración de tiempos y cierre real de un servidor de prueba
  en su bucle; otro caso simula un hilo que no termina y exige error y listener cerrado.
- Pruebas del Coder: selección de tres entradas, solicitud efectiva al adapter,
  redacción, cota total de 800, neutralización de cierre inyectado y aislamiento FTS5.
- Ruff focalizado aprobado. Regresión completa:
  **990 PASS, 4 SKIP, 0 fallos**, 741,654 s,
  `_tmp/rc8-shutdown-history-full.xml`.
- Frontend: 34 PASS y compilación TypeScript/Vite aprobada.
- CPython y módulos empaquetados: **18 pruebas launcher/historial PASS**,
  `_tmp/rc8-fixed-packaged.xml`.
- Dos smokes estándar independientes sobre el ZIP extraído: **14/14 PASS cada
  uno**, `_tmp/rc8-fixed-standard-1/report.json` y
  `_tmp/rc8-fixed-standard-2/report.json`. Plazos originales: procesos con
  `--exit-after 90`, espera de 105 s; sin instrumentación ni wrappers. Los cuatro
  cierres terminaron con código 0. SQLite, checkpoint, registro y login tras
  reinicio aprobados. Los logs no muestran WinError 10054 ni traceback.

## Distribución y límites

El código corregido se empaqueta y verifica en un directorio nuevo
`dist/windows-v0.2.0-operational-rc8-fixed/`. Se preservan el rc8 original retenido
y rc7. La aprobación y hash se registran tras completar el smoke
estándar sobre la extracción de ese ZIP, sin wrappers, faulthandler ni temporizadores
acortados. Se ejecutan dos repeticiones aisladas por la intermitencia anterior.

Sin inferencias pagadas, PAT reales ni publicaciones externas. No se mide ahorro
de tokens facturados: agregar historial tiene un coste de contexto acotado y
los resultados anteriores de bytes sin historial no certifican ese ahorro.
La recuperación entre equipos y la calidad de propuestas con historial real
requieren el piloto correspondiente. La aprobación local no es producción pública.

# Productización v0.1.0 — registro de continuidad

## RC8 corregido: cierre e historial FTS5 — 30 de octubre de 2026

Aprobado el ZIP `windows-v0.2.0-operational-rc8-fixed`: dos smokes estándar de
14/14 controles, sin instrumentación, tiempos originales y cuatro cierres código 0.
Uvicorn keep-alive 3 s, graceful 5 s y join 10 s con error si no termina; cliente
consume/cierra respuestas. Coder recibe historial redactado como datos no confiables,
3 entradas y 800 caracteres totales. Regresión 990 PASS/4 SKIP, frontend34 PASS,
build y Ruff focalizado aprobados; 18 pruebas desde runtime empaquetado PASS.
Hash, evidencia y límites en `RC8-SHUTDOWN-FTS-CLOSURE.md`. Sin llamadas pagadas.

## Contexto medido y límites de recuperación — 30 de octubre de 2026

Benchmark reproducible con solicitudes reales y FakeModelAdapter: ~16 % menos
bytes de mensajes en tres fixtures con archivos identificables, cobertura 100 %
de su oráculo sintético; sin coincidencias, 0 % de reducción y cobertura insuficiente.
No es ahorro de tokens facturados. Corregidos recorte arbitrario sin anclas,
descarte de archivos explícitos que excedían 20 y conexiones SQLite no cerradas
(WinError 32 reproducido). 48 pruebas focalizadas PASS; suite completa 986 PASS/4 SKIP,
0 fallos; Ruff aprobado. rc8 NO aprobado: dos timeouts del smoke estándar al cerrar;
dos repeticiones instrumentadas aprobadas, sin causa raíz confirmada. rc7 sigue
como portable verificado; no se sustituye ni se publica el candidato.
Pendiente confirmado: conectar historical_context FTS5 al prompt Coder con límites
y redacción. Acta: `CONTEXT-MEMORY-MEASUREMENT.md`. Sin llamadas pagadas.

## Flujo accionable y progreso visible — 30 de octubre de 2026

Ejecución navega/enfoca Flujo; ambas puertas humanas operan directamente allí.
Banner compartido para continuar y mensajes de actividad comprensibles, con éxito
de construcción condicionado a promoción real. Backend completo 982 PASS/4 SKIP,
34 pruebas frontend y 34 controles de navegador PASS; build aprobado.
Portable rc7 aprobado con 14 controles de integridad, arranque, perfiles y reinicio/SQLite.
Acta: `HUMAN-GATES-INTUITIVE-UX-VALIDATION.md`. Sin llamadas pagadas.

## Restauración multirrepositorio — 30 de octubre de 2026

Lectura previa del respaldo sin mutaciones y autorización de una ruta por proyecto.
Mapeos incompletos/solapados se rechazan antes de reconstruir repositorios. Se
corrige la reserva de nombre que quedaba tras una importación fallida, permitiendo
reintentar sin afectar otras identidades. 7 controles de navegador y 32 pruebas
frontend aprobados; build aprobado. Regresión API/continuidad y portable rc6 en
`MULTI-REPOSITORY-RESTORE-VALIDATION.md` y acta operativa. Sin consumo de API.

## Restauración desde acceso — 30 de octubre de 2026

Usuario confirma funcionamiento en otra PC, sin matriz detallada ni versión
identificada. Se expone recuperación de perfil sin registro previo en la UI,
con asignación sencilla de un repositorio y sin ejecución automática al importar.
36 pruebas backend focalizadas, 32 frontend, 5 controles de navegador y build
aprobados. Nuevo rc5 incorpora además el lanzador de `33fc64c`, preservando rc4.
Sin inferencias pagadas. Acta y límites: `PROFILE-IMPORT-UI-VALIDATION.md`.

## Prueba local y decisión posterior — 30 de octubre de 2026

Lanzador interactivo para bibliotecas Python, pausa y UTF-8 en todos los BAT
nuevos, y acceso honesto a carpeta para formatos sin entrada reconocida. Coder
recibe la regla de punto de entrada. Ficha con probar, pedir cambios (proyecto
y foco preservados, sin ejecutar) y publicación guiada. 49 pruebas backend
focalizadas, 32 frontend y 12 controles de navegador PASS; build y Ruff aprobados.
Sin inferencias/publicaciones reales ni modificación de rc4. Evidencia y límites:
`UNIVERSAL-LOCAL-LAUNCH-VALIDATION.md`. Pendiente próximo portable.

## Continuidad y restauración rc4 — 30 de octubre de 2026

Detectada y reproducida incompatibilidad Base64 de la subida de respaldos desde
la UI frente al contrato estricto de importación. Corrección mínima del emisor,
sin relajar validación o cifrado. 4 controles de navegador y 32 pruebas frontend
aprobados, build aprobado. Las 17 pruebas de continuidad/memoria pasan tanto
en desarrollo como con el runtime y módulos del portable rc3. Recuperación
simulada de perfil/repo nuevos sin repetir agentes; no equivale a otra PC real.
Nuevo rc4 conserva candidatos anteriores. Evidencia: `CONTINUITY-FOLLOWUP-2026-10-30.md`;
hash en `OPERATIONAL-STATUS-2026-10-30.md`. Sin inferencias pagadas.

## Portable operativo rc3 — 30 de octubre de 2026

Código `4703934` empaquetado en
`dist/windows-v0.2.0-operational-rc3/AISWESystem-windows-x64.zip`, conservando rc2.
Compilación TypeScript/Vite aprobada, CPython oficial firmado, manifiesto de
4.726 archivos y comparación de 74 módulos fuente con la extracción del ZIP.
Verificador portable sobre esa extracción: 14 controles PASS, salida 0,
perfiles/reinicio/SQLite aprobados con PATH reducido y datos aislados.
Regresión fuente vigente: 973 PASS/4 SKIP, frontend32 PASS y navegador30 PASS.
Hash, comando del verificador, evidencia y límites de esta entrega en
`OPERATIONAL-STATUS-2026-10-30.md`. Sin nuevas inferencias pagadas ni sustitución
del servidor abierto. El piloto en otra PC y continuidad integral siguen pendientes.

## Adaptación operativa selectiva de Nova — 30 de octubre de 2026

Sobre `9fe10cb`: preparación autenticada por proyecto y commit base vacío explícito,
SSE con detección de huecos/snapshot y cancelación cooperativa por ejecución con
recibo solicitado/confirmado/demasiado tarde. Ledger libera solo reservas no
despachadas y conserva incertidumbre; limpieza acotada y verificada de worktrees.
Regresión backend final: 973 PASS/4 SKIP, frontend32 PASS, build aprobado y
30 controles de navegador aprobados. La prueba obsoleta de 501 se actualizó al
contrato real; la compatibilidad del rechazo 409 se conservó sin relajar su prueba.
Se preservan las puertas humanas, HEAD y la promoción atómica. Acta y resultados:
`NOVA-OPERATIONAL-VALIDATION.md`. La cancelación no fuerza corte HTTP/facturación.
Sin inferencia pagada, nuevo ZIP ni actualización del servidor abierto.

## Síntesis generalizada y estado de adopción — 30 de octubre de 2026

Sobre `d3b144c` se retira el catálogo cerrado de productos del Analyst local,
sustituyéndolo por familias funcionales y núcleo nominal. El prompt remoto exige
cuatro dimensiones para cualquier creación/modificación de software, manteniendo
alcance, exclusiones y puerta humana. Acta: `UNIVERSAL-REQUIREMENTS-VALIDATION.md`.
Validación final offline: backend962 PASS/4 SKIP (0 fallos), 34 casos de requisitos,
frontend32 PASS y build TypeScript/Vite aprobado. Sin llamadas de pago.
Estimación ponderada actual: 77/100 hacia entrega Windows confiable y recuperable,
con método y adopción real de MADRE/Nova en `PROJECT-STATUS-2026-10-30.md`.
No acredita producción pública, nuevo paquete ni cierre de continuidad entre equipos.

## Requisitos de producto para instrucciones breves — 30 de octubre de 2026

Prioridad incorporada al flujo de pendientes y al plan maestro de `ROADMAP.md`.
Sobre `4b4c242` (descendiente de `ab079d3`) se implementan el rol Product Manager,
propuestas base locales, confianza alta de intención clara, confirmación/edición
visual y tres chips de inicio rápido. Se preserva la puerta humana y el alcance.
Validación offline: backend940 PASS/4 SKIP, frontend32 PASS, build TypeScript/Vite
y 23 controles de navegador aprobados. Las suites previas permanecen intactas.
Evidencia y límites: `PRODUCT-REQUIREMENTS-VALIDATION.md`.
Empaquetado actualizado, piloto en otra PC y despliegue siguen como pendientes
separados; esta mejora no autoriza inferencia pagada ni publicación remota real.

## UX intuitiva y memoria asociativa — 30 de octubre de 2026

Implementación fuente de los cinco puntos autorizados sobre `ab079d3`: capitalización
tipo oración, modo local/GitHub, guía posterior a promoción con `iniciar.bat`, asistente
de primera publicación privada, memoria de co-ocurrencias y freno horario por perfil.
Se corrige CSS que ocultaba crear carpetas y se verifican los hashes de todos los
archivos aprobados antes del inicio. Regresión completa 926 PASS/4 SKIP; después,
19 pruebas focalizadas finales, frontend32 PASS, build TypeScript/Vite y 10 controles
de navegador aprobados. Iniciador CLI probado en Windows. Sin llamadas pagadas,
sin publicación real y sin nuevo ZIP/actualización del servidor abierto.
Acta y límites: `INTUITIVE-UX-NEUROMAPA-VALIDATION.md`. No constituye cierre de
producción ni prueba de ahorro de 50–70 % de tokens.

## Punto seguro operativo — 29 de octubre de 2026

Acta vigente: `OPERATIONAL-STATUS-2026-10-29.md`. Suite final 909 PASS/4 SKIP,
32 pruebas frontend y E2E real `run-b70e76e5abd6` completado con Coder Qwen2.5-Coder
y Reviewer GPT OSS 120B, pruebas reales, aprobación y promoción al repositorio
descartable. 29 casos independientes aprobados antes/después de promover.
Portable nuevo `windows-v0.2.0-operational-rc2`; entregas previas conservadas.
Avance estimado 75/100 hacia v0.2.0 portable y recuperable. Continuidad, otra PC
y aislamiento fuerte siguen pendientes; no es cierre de producción ni tag v0.2.0.

## Baseline

- Rama de partida main, HEAD 2d35a59, árbol limpio y sin remotos, verificados.
- delivery-rc1 ya existía y apunta a 2d35a59; se mantiene intacto.
- Rama de trabajo creada: productization/v0.1.0. Sin push ni configuración remota.

## D — laboratorio (en progreso)

- Fuentes oficiales actuales consultadas y registradas en MODEL-LAB-REPORT.md.
- Notebook + implementación reutilizable + modalidad cloud GPU perezosa preparados.
- Se reutiliza el adapter OpenAI-compatible; no hay un adapter HF nuevo.
- Catálogo dinámico real: 268 pares, sin inferencia, resultados DISCOVERY_ONLY.
- 19 pruebas focalizadas offline y Ruff aprobados. No se instaló Jupyter en runtime.
- Suite completa nueva: **709 PASS, 3 SKIP, 0 FAIL**, 205.49 s; evidencia
  `_tmp/productization-d-offline.xml` y log del mismo prefijo.
- Pendiente: gate de token/cuota/dinero, inferencia real acotada, probe de tools,
  benchmark y recomendación basada en calidad; no se atribuyen mediciones ficticias.
- El commit final solicitado para D se reservará al cierre real del laboratorio;
  este checkpoint parcial usa un mensaje que no promete integración validada.

## Continuación autorizada

Tras resolver gates humanos: completar D, luego E/F/G/H/I/J sin pedir decisiones
técnicas ordinarias. Plan detallado en
`superpowers/plans/2026-10-14-productization-v0.1.0.md`.
No activar funciones excluidas ni mover delivery-rc1. No crear v0.1.0 hasta que
la matriz de producto/paquete/entorno limpio esté verificada.

## Pausa explícita del usuario

Trabajo detenido en un checkpoint local por límite de uso de Work. Reanudar solo
cuando el usuario lo pida. Resumen operativo en `RESUME-PRODUCTIZATION-v0.1.0.md`.
No hay procesos de prueba pendientes; la suite completa terminó correctamente.
No se comprobó todavía el token ni se consumió inferencia o dinero.

## Reanudación solicitada el 26 de octubre de 2026

- Rama y HEAD confirmados: `productization/v0.1.0`, `7419818`.
- Los cambios pendientes son la entrega documental realizada en este chat;
  se preservaron sin restaurar archivos ni mezclarlos con cambios del runtime.
- `delivery-rc1` existe; no se modificó. No hay remotos configurados.
- El plan está en `docs/superpowers/plans/2026-10-14-productization-v0.1.0.md`.
- Se ejecutó el chequeo local `python -m tools.model_lab check-gate` con el
  intérprete del proyecto: `GATE_REQUIRED: HF_TOKEN is not configured`.
- No se mostraron secretos ni se realizaron llamadas de inferencia, descargas
  o gastos. La siguiente acción depende de configurar la credencial y autorizar
  un límite económico antes de las pruebas reales. No se avanzó a E–J.
- La pausa anterior por uso fue revocada por la solicitud de continuar. El
  trabajo queda ahora pendiente de la credencial; no se declara cerrada D.

## Ruta híbrida aceptada por el usuario

- Evaluar Analyst y Supervisor con modelos locales cuantizados; Coder y Reviewer
  mediante API. Mantener LangGraph, políticas, Git y verificaciones locales.
- La asignación es una hipótesis que debe superar evaluación semántica, de
  memoria y latencia; no garantiza eficiencia ni calidad por el nombre del modelo.
- Jupyter será laboratorio externo; no dependencia obligatoria del ejecutable.
- Presupuesto autorizado por el usuario: hasta 3 USD para pruebas reales.
  Es un techo total de esta autorización, no un importe renovable por comando.
- Hardware consultado: GTX 1650 Ti, 4096 MiB VRAM total y 3773 MiB libre en
  ese instante. La consulta de RAM mediante CIM fue denegada por el entorno;
  las cifras del notebook siguen siendo históricas hasta nueva medición.
- Chequeo con `--max-usd 3`: `GATE_REQUIRED: HF_TOKEN is not configured`.
  No hubo inferencia ni gasto. No se descargaron pesos ni se cambiaron contratos
  o routing del runtime. El siguiente paso sigue siendo la credencial.
- El código del repositorio enviado a un proveedor remoto deja el equipo local;
  las pruebas iniciales deben usar únicamente casos sintéticos o descartables.

## Credencial disponible y bloqueo de facturación

- Tras confirmar el usuario la configuración, `check-gate --max-usd 3` pasó.
  Esto comprueba presencia de credencial, no saldo ni validez ante el proveedor.
- Catálogo público actualizado: 269 pares modelo/proveedor, sin inferencia.
- Prueba sintética de Coder: `Qwen/Qwen2.5-Coder-32B-Instruct:nscale`.
  El arnés registró `INVALID_RESPONSE` sin usage. Un diagnóstico mínimo posterior
  confirmó HTTP 402 y contenido relacionado con facturación/créditos.
- No se guardaron cuerpos del servidor ni secretos. No hay evidencia de calidad
  del modelo y no se modificó el routing del producto.
- Dos intentos, cero reintentos automáticos. Reserva acumulada conservadora:
  0.01583424 USD sobre los 3 USD autorizados. Usage y cargo real desconocidos;
  no se reembolsa la reserva por falta de usage. No renovar presupuesto por comando.
- Evidencia local ignorada por Git: `_tmp/hybrid-validation/spend-ledger.json`,
  `remote-probe-01.json` y `http-diagnostic-01.json`; catálogo en
  `_tmp/hybrid-catalog.json`. Consultar el ledger antes de nuevas llamadas.
- Se detuvieron las llamadas remotas al encontrar el gate humano de facturación.
  El usuario debe comprobar créditos/acceso a Inference Providers en su cuenta.
- Mejora pendiente demostrada: distinguir HTTP 402 de respuesta inválida genérica
  en la clasificación del adapter y abortar baterías ante errores de facturación.
  No se declara corregido todavía.

## Evaluación híbrida tras la recarga de créditos

- El bloqueo HTTP 402 quedó resuelto para las peticiones posteriores. Corrección
  del manejo de 402 y aborto de baterías guardada en commit local `95ddf64`.
- Suite offline completa: 715 PASS, 3 SKIP, 0 FAIL. Después, 28 pruebas focalizadas
  del laboratorio PASS y Ruff focalizado PASS; no confundir ambas ejecuciones.
- Coder/Reviewer remotos: Qwen2.5-Coder-32B-Instruct:nscale pasó 8/8; candidato
  provisional para integración, no validación E2E del producto.
- Qwen3-32B:nscale pasó 6/8. Prueba mínima de JSON Schema estricto pasó con el
  primer modelo; tool calling forzado recibió HTTP 400, sin ejecutar herramientas.
- GGUF locales públicos con revisión y checksum verificados: Qwen2.5-1.5B Q4_K_M
  y Qwen3-1.7B Q8_0, ejecutados con llama.cpp b11700 CPU y apagado al finalizar.
  Ninguno pasó todos los casos de Analyst/Supervisor; no se activó routing local.
- Los planes remotos a 512 tokens se truncaban; se añadió un límite configurable
  con reserva previa. A 1024 se completaron, pero no superaron el criterio semántico
  de modificación. No se debilitaron aserciones ni se ocultaron esos resultados.
- Presupuesto total sigue siendo 3 USD. Reserva acumulada 0.22656320 USD;
  estimación conocida con usage 0.00299420 USD, no factura conciliada.
- Resultados y métodos en `HYBRID-MODEL-VALIDATION.md` y evidencia consolidada en
  `HYBRID-MODEL-LAB-EVIDENCE.json`, sin secretos ni respuestas brutas.
- Pendiente decisión del usuario: respaldo determinista local para los roles
  ligeros e integración de Coder/Reviewer remotos, o evaluar un modelo local mayor.
  D/E permanecen abiertos. Sin cambios al routing ni al tag `delivery-rc1`.

## Integración E adaptada al perfil aceptado

- El usuario aceptó Analyst/Supervisor deterministas y Coder/Reviewer por API.
- `AI_SWE_REMOTE_MODEL_ROLES` es opt-in, vacío por defecto. La configuración se
  vincula al motor y los gateways se aíslan y cierran por invocación del nodo.
- El Reviewer recibía un diff de reemplazo como creación incluso al modificar
  archivos existentes. Se reprodujo el defecto y se corrigió para usar el diff
  aplicado del worktree, sin debilitar gates o aserciones.
- Pruebas reales en repositorios descartables: aprobar, rechazar y pedir cambios
  antes de aprobar, todas verificadas. Hubo dos ejecuciones iniciales sin converger;
  sus informes se conservan. La solicitud exitosa explicita la prueba ya existente.
- Contabilidad verificada con los alias routed y reportado del modelo. La última
  corrida con tarifas reconocidas estimó 0.00021114 USD; los ceros anteriores en el
  acumulador no se interpretan como inferencia gratuita.
- Suite final: 725 PASS, 3 SKIP, 0 FAIL, 159.882 s. La primera pasada detectó una
  importación no perezosa; se corrigió sin modificar su aserción arquitectónica.
- Reserva acumulada de la autorización de 3 USD: 1.17225088 USD; quedan
  1.82774912 USD sin reservar. No se libera reserva por fallos o falta de usage.
- Método y límites: `REAL-MODEL-VALIDATION.md`; evidencia consolidada en
  `HYBRID-E2E-EVIDENCE.json`; verificador opt-in `tools/verify_hybrid_models.py`.
- No se activó automáticamente el perfil remoto en `.env`. No hay inferencia por
  defecto ni claims de producto instalado o producción. Voz y empaquetado pendientes.
- Próximo encargo recibido: propuesta inspirada en MADRE. Solo el preflight se
  considera para v0.1.0 (G/H); los módulos 3.2–3.5 quedan en backlog v0.2.0.

## Propuesta MADRE y preflight sin inferencia

- Propuesta conservada en `PROPUESTA-MEJORAS-INSPIRADAS-EN-MADRE.md`, con ajustes
  explícitos: roles ligeros deterministas, costes reales de FTS5 y ausencia de
  commits implícitos de promoción. Módulos 3.2–3.5 siguen en backlog v0.2.0.
- Diagnóstico reutilizable en `models/providers/diagnostics.py` y CLI
  `python -m ai_swe.preflight`. No requiere GGUF para el perfil aceptado y no
  genera tokens, descarga modelos ni invoca CLIs de agentes.
- GET real de identidad del Hub aceptó la credencial; saldo e inferencia se
  mantuvieron como no verificados. Sin exportar token ni identidad de cuenta.
- Se conserva la frontera HTTP en providers. La primera suite detectó su
  ubicación incorrecta y se corrigió sin alterar la aserción arquitectónica.
- 20 pruebas nuevas de diagnóstico aprobadas. Suite final: 745 PASS, 3 SKIP,
  0 FAIL, 161.201 s. Ruff focalizado aprobado. XML preservado en
  `_tmp/provider-preflight/preflight-final.xml` del checkout principal.
- G/H siguen parciales: falta cargar configuración instalada, launcher y paquete.
  No se añadió un bloqueo de arranque a la API actual.

## F — voz real cerrada para Windows CPU/int8

- Entorno principal sincronizado con el lockfile corregido: PyAV 18.1.0 (`av<19`).
- Settings expone dispositivo y cómputo. Windows usa CPU/int8 por defecto; CUDA
  explícito conserva errores sin fallback. En este equipo falta `cublas64_12.dll`.
- small local con revisión/checksum verificados transcribió la muestra española
  sintética completa: 8.74 s de audio en 5.122 s por la factoría real CPU/int8.
- Chromium + getUserMedia + MediaRecorder + FastAPI + STT real y carga de archivo
  verificados. Captura alimentada por WAV sintético, no micrófono físico.
- Texto editable; vacío bloquea confirmación; transcribir/confirmar no crea runs.
  Solo «Ejecutar» crea la ejecución de voz, que espera confirmación de requisitos.
  Repo descartable intacto y sin llamadas de inferencia remota.
- Seis pruebas nuevas. Suite completa: 751 PASS, 3 SKIP, 0 FAIL (183.107 s).
  TypeScript/build y Ruff focalizado aprobados.
- Método/evidencia: `REAL-STT-VALIDATION.md`, `REAL-STT-EVIDENCE.json` y verificador
  opt-in `tools/verify_real_voice.cjs`. No se implementó TTS ni se rediseñó UI.
- Prueba física y confirmación humana completadas (detalle debajo): F cerrada
  para small local y CPU/int8. CUDA sigue opcional y no validado.
  G/H y lanzamiento siguen pendientes; no se movió ningún tag ni se hizo push.

### F — confirmación humana recibida

- El usuario confirmó que el reconocimiento del micrófono reprodujo lo dictado.
- La sesión física contiene tres runs de origen `text`, todos esperando la puerta
  de requisitos. No se atribuyen automáticamente a voz ni se declara cero runs.
- El usuario confirmó la revisión/edición y aclaró: «Sí, pulsé Ejecutar; el dictado
  no lanzó nada solo». Las tres ejecuciones fueron manuales según su reporte.
- Cierre basado en E2E automatizado y prueba física reportada por el usuario;
  no se inventaron mediciones de exactitud/latencia del micrófono ni se guardó audio.

## Acta E revisada antes de G

- E cerrada para el perfil aceptado: Analyst/Supervisor deterministas locales y
  Coder/Reviewer Qwen2.5-Coder-32B-Instruct:nscale por API, integrado en `5849282`.
- Se contrastaron nuevamente los reportes reales de aprobar/promover (`ade1dc89`),
  rechazar (`bd5ca540`) y pedir cambios/aprobar (`04ef6878`). Todos pasaron y el
  original se conservó hasta la aprobación humana del escenario.
- Acta explícita añadida a `REAL-MODEL-VALIDATION.md`; no faltaba la promoción real.
  No se repitió inferencia. Reserva acumulada intacta: 1.17225088 de 3 USD.

## G — configuración instalada Windows completada

- Modo installed explícito o automático en proceso frozen; development conserva
  su `.env` y rutas actuales. Sin migrar, copiar o borrar datos/credenciales.
- Installed carga `%LOCALAPPDATA%/AISWESystem/config/.env`, sin leer el `.env`
  del código. Entorno/argumentos explícitos tienen prioridad. Datos SQLite,
  logs rotados, worktrees y caché STT quedan en subdirectorios del perfil de usuario.
- Rutas relativas instaladas se rechazan. Crear Settings no escribe ni descarga;
  load_settings prepara directorios sin fabricar un archivo de secretos.
- HF_TOKEN externo se usa solo para el router HF si no hay clave explícita; se
  redacta en logs. No se copió el token real ni se habilitaron roles de pago.
- `/health` añade diagnóstico de presencia, sin red ni claims de validez/saldo.
  La UI explica qué falta. Lectura local y ejecuciones deterministas siguen disponibles.
- Con roles remotos habilitados y configuración incompleta, `/runs` devuelve 503
  antes de crear/encolar. El gateway también bloquea el router HF sin credencial.
- El navegador detectó la divergencia entre diagnóstico y alias genérico del
  gateway. Se reprodujo con prueba, se alinearon requisitos y se verificó que
  `ollama` local conserva operación sin clave. No se debilitó ninguna aserción.
- Pruebas nuevas de configuración, integración de API y navegador real. Detalles
  y evidencia: `INSTALLED-CONFIGURATION-WINDOWS.md` y
  `INSTALLED-CONFIGURATION-EVIDENCE.json`.
- H (launcher/ejecutable), I (instalador/equipo limpio) y J (release final) siguen
  pendientes. Sin tag final, push ni cambios a documentos académicos preexistentes.
- Verificación final: 769 PASS, 3 SKIP, 0 FAIL, 168.190 s; 18 pruebas nuevas.
  TypeScript/build, 24 pruebas de estado del frontend y Ruff focalizado aprobados.
  La sincronización del contrato exportado se corrigió en el generador y volvió
  a pasar sin alterar su prueba. Evidencia XML: `_tmp/phase-g-release-check.xml`
  del worktree aislado, preservada también en `_tmp/phase-g-validation/` del principal.

## H — launcher y ejecutable completados; I preparada

- PyInstaller 6.22.3 fijado en extra packaging/uv.lock; construcción onedir mediante
  `tools/build_windows.py` y `packaging/ai-swe.spec`, con frontend recién construido.
- Launcher: socket reservado de loopback, puerto alternativo, espera de salud,
  apertura de URL efectiva y cierre ordenado. Errores sin eco de secretos.
- Runtime congelado activa installed de forma nativa. Assets en bundle y datos
  en LOCALAPPDATA. Sin copiar `.env`, SQLite, caché o pesos del desarrollador.
- Smoke real del EXE con PATH sin Python/Node, directorio ajeno y perfil temporal:
  API/UI, Git de prueba, LangGraph hasta puerta humana, autenticación, persistencia,
  reinicio, voz española CPU/int8 y trabajadores incluidos de pytest/Ruff aprobados.
- Suite: 780 PASS, 3 SKIP, 0 FAIL, 169.816 s. Once pruebas nuevas; Ruff aprobado.
- Entrega: `dist/windows-h-rc1/AISWESystem/` y ZIP de la misma carpeta. Hash,
  reproducción y límites en `PACKAGING-REPORT.md` / `PACKAGING-EVIDENCE.json`.
- I pendiente: WindowsSandbox.exe e Inno Setup no encontrados; vmcompute activo
  no acredita una VM limpia. Sin instalaciones del sistema, reinicio, UAC ni firma.
  No se declara producción o release final; presupuesto remoto intacto, sin push.

## I — checkpoint pausado por límite diario solicitado por el usuario

- Instalador per-user compilado con Inno Setup 6.7.3 oficial firmado, sin UAC ni
  reinicio. Candidato en `dist/windows-i-rc1/`; todavía no apto para entrega.
- Cuatro pruebas unitarias nuevas aprobadas. La validación instalada pasó copia
  del runtime pero falló al comprobar el grupo de accesos directos: arnés esperaba
  grupo único y Setup usó el predeterminado. Cleanup desinstaló con exit 0.
- Promoción instalada, conservación de datos al desinstalar y suite final pendientes.
  Cuatro avisos Ruff nuevos pendientes. I no cerrada; J no iniciada; sin tag final.
- Instrucciones y rutas exactas en `RESUME-PHASE-I.md`. Reanudar solo a solicitud.

## Reanudación del 27 de octubre de 2026 — I validada y J preparada

- El usuario revocó la pausa con «continua». Baseline `bfc5273`, rama
  `productization/v0.1.0`; cambios académicos previos preservados.
- Causa de accesos confirmada con documentación de Inno: `/GROUP` se ignora si
  `DisableProgramGroupPage=yes`. Se cambió a `no` y se protege también el grupo
  predeterminado preexistente. Los cuatro avisos Ruff del checkpoint se resolvieron.
- I pasó 23 controles sobre el instalador final: instalación sin elevación,
  accesos/registro, prueba inicialmente fallida, worktree/tests/revisión, reinicio
  en puerta de aprobación, promoción exacta tras aprobar y desinstalación conservando
  todos los archivos de datos byte por byte. Se retiró la instalación de prueba.
- El servidor de modelos de esa prueba es un fixture HTTP local determinista;
  gateway, grafo, pruebas, puertas y promoción son reales. No se presenta como
  inferencia real ni se gastó presupuesto remoto.
- J: API/OpenAPI y frontend/lock alineados con Python/instalador a 0.1.0; regresión
  nueva de coherencia. EXE e instalador se reconstruyeron y revalidaron después.
- Suite final: **785 PASS, 3 SKIP, 0 FAIL**, 226.982 s. Frontend: TypeScript/build,
  24 pruebas de estado y 114 comprobaciones reales de navegador aprobadas.
  EXE final: 19 controles, incluida voz española CPU/int8, sin Python/Node externos.
- Documentos: `INSTALLATION-WINDOWS.md`, `PRODUCT-v0.1.0.md`,
  `KNOWN-LIMITATIONS-v0.1.0.md`, `INSTALLER-VALIDATION.md` y
  `RELEASE-MATRIX-v0.1.0.md`; consolidado `RELEASE-EVIDENCE-v0.1.0.json`.
- Artefactos y hashes: `dist/windows-v0.1.0-rc1/`. Sigue sin VM independiente ni
  firma de producto. I se cierra solo en el alcance aislado solicitado de este host.
- J queda lista para revisión del alcance/omisiones y aprobación de etiqueta;
  **no se creó `v0.1.0`, no se hizo push ni se declara producción**.
  Reserva del laboratorio intacta: 1.17225088 de 3 USD. README/documentos académicos
  pendientes del usuario no se mezclaron con este candidato.

## Interfaz premium — revisión posterior de I/J, 27 de octubre de 2026

- Rediseño solicitado por el usuario: materiales nativos claros/oscuros, cabecera
  de proveedor, sidebar de proyectos/corridas, compositor voz/audio, transcripción
  editable, pipeline, decisiones humanas y visor de evidencia. HTTP/SSE intactos.
- 24 pruebas frontend, TypeScript/build y 114 controles de navegador aprobados.
  Configuración instalada: 8; voz real CPU/int8: 16; EXE: 19; instalador: 23;
  smoke adicional del navegador sobre EXE: 13 controles aprobados.
- Entrega nueva en `dist/windows-premium-rc1/`, con instalador, carpeta completa y
  ZIP. Acta `UI-PREMIUM-VALIDATION.md` y hashes `UI-PREMIUM-EVIDENCE.json`.
- La suite Python completa del baseline no se repitió por este cambio visual.
  Sin inferencia pagada, VM nueva, firma, tag final o push. Actas anteriores
  conservadas como evidencia histórica; documentos académicos preservados.

## J — regresión final del candidato premium

- Continuación solicitada por el usuario; baseline `4accb8e` verificado. Suite
  Python completa nueva: **785 PASS, 3 SKIP, 0 FAIL**, 214.96 s. XML/log en
  `_tmp/release-premium-final-suite.*`. Sin llamadas de pago.
- Hashes de instalador/EXE/ZIP contrastados contra el acta premium; ZIP íntegro,
  incluido `_internal`. Contratos y pruebas frontend conservados byte por byte
  respecto al baseline previo al rediseño.
- Guías de producto/instalación actualizadas a `dist/windows-premium-rc1/`.
  Matriz vigente y `FINAL-RELEASE-EVIDENCE-v0.1.0.json` distinguen la suite nueva
  de las validaciones del paquete ya aprobadas, reutilizadas sin inventar reruns.
- `CLEAN-WINDOWS-VALIDATION.md` prepara la prueba externa, aún NO ejecutada.
  No hay VM independiente, firma, aprobación de tag final ni push. El próximo
  gate es validar otro Windows o decidir expresamente el alcance local del release.

## Adaptación funcional del frontend de Antigravity

- Código externo localizado en la ruta proporcionada por el usuario y revisado.
  Pipeline secuencial, inspector contextual, actividad SSE, historial con búsqueda/
  orden y sidebar contraíble adaptados a los contratos actuales; sin tocar backend.
- 24 pruebas frontend, TypeScript/build, 134 controles de navegador, 8 de
  configuración y 16 de voz CPU/int8 aprobados. Foco y selector de promoción
  corregidos tras fallos reproducibles. Acta `ANTIGRAVITY-INTEGRATION.md`.
- EXE e instalador nuevos construidos. El EXE fue bloqueado por Windows con
  WinError 4551 antes del smoke. No se eludió la directiva; paquete nuevo no
  validado, instalación no ejecutada. Reporte y hashes en `ANTIGRAVITY-EVIDENCE.json`.
- La entrega premium anterior permanece intacta, sin estas nuevas vistas. La
  integración está disponible desde fuente/build principal. No hay tag ni push.

## Distribución admitida por Smart App Control — cierre de pasos 1 y 2

- Diagnóstico confirmado: SAC=1; evento 3077/3033 y política 3099
  `VerifiedAndReputableDesktop`, GUID `0283ac0f-fff1-49ae-ada1-8a933130cad6`.
  Signtool encontrado. No certificados nuevos ni cambios de almacén/política.
- Distribución vigente: CPython embeddable 3.13.14 firmado, ruedas del lock con
  verificación RECORD, app/frontend externos y CMD. Installed con marcador
  interno, `sys.frozen=false` real. No nuevo bootloader ni instalador EXE sin firma.
- Entrega `dist/windows-signed-python-rc2/`. ZIP/manifiesto verificados: 4538
  archivos, sin secretos/estado/pesos. Los binarios de ruedas conservan procedencia;
  no todos están firmados (Ruff NotSigned, admitido por SAC en los controles).
- 791 PASS, 3 SKIP, 0 FAIL en suite completa; 21 controles focalizados finales,
  24 de frontend/build, 19 smoke, 21 E2E portable y 14 navegador del paquete.
  Promoción exacta tras aprobación, reinicio/SQLite y datos preservados al retirar
  la copia de prueba. Fixture de modelo local; ninguna llamada de pago nueva.
- CMD probado sin Python/Node en PATH; SAC sigue en 1, cero eventos de bloqueo
  coincidentes con la distribución nueva. Sin VM independiente ni tag/push.
  Acta vigente en `PACKAGING-REPORT.md`; consolidado `SAC-DISTRIBUTION-EVIDENCE.json`.

## Cierre formal v0.1.0 autorizado por el usuario

- Documentación académica y contexto conservados en commit documental, con sus
  formatos editables, PDF, draw.io e imágenes. Sin borrar ni reubicar código.
- Entrega canónica aprobada para el entorno local validado:
  `dist/windows-signed-python-rc2/AISWESystem-signed-python-rc2.zip`.
  SHA256 `790964a4aeb4e91cb54974017fa6b81fd34703689a4fdea75c7004de57133c88`.
- 791 PASS, 3 SKIP, cero FAIL y bloqueos SAC; no se afirma una VM independiente.
  Se autoriza tag local `v0.1.0` sobre el cierre documental limpio, sin push.
- La evolución K/L/M se abre después en `feature/v0.2.0-madre-continuity`;
  ningún cambio funcional v0.2.0 pertenece al tag v0.1.0.

## Evolución v0.2.0 (`feature/v0.2.0-madre-continuity`) — Fases K, L, M y UI Espacial Premium

- **Fase K (Perfiles autenticados y bóveda cifrada):** aislamiento estricto por usuario (`users/<id>/state.sqlite3`, `logs/`, `worktrees/`), bóveda Scrypt + AES-256-GCM con HKDF/AAD por perfil, sesiones HTTP-only + CSRF y libro mayor de presupuesto atómico (`BudgetLedger`). 13 pruebas de aislamiento en `tests/test_continuity_k.py` aprobadas.
- **Fase L (Memoria contextual MADRE FTS5, modos de ejecución y rollback):** índice local SQLite FTS5 (`MemoryStore`) aislado por usuario y repositorio con escape seguro de consultas; modos `FULL_PROPOSAL`, `PLAN_ONLY` e `INSPECT_ONLY` impuestos en el grafo y nodos; recibos de promoción acotados a las rutas promovidas (`RollbackStore` con objetos Git en `.git/refs/ai-swe/promotions/<receipt_id>`) y reversión en 1 clic sin `git reset --hard`; auditoría cruzada Coder (`CodeProposal`) vs Reviewer (`ReviewVerdict`) en la interfaz. 11 pruebas en `tests/test_continuity_l.py` y 26 en `tests/test_contracts.py` aprobadas.
- **Fase M (Portabilidad de checkpoints, pausa cooperativa y recuperación `.aiswe-vault`):** estado `PAUSED` en `RunStatus`, pausa cooperativa entre nodos (`request_pause` / `resume_paused`), capturas de worktree (modificados, binarios, no rastreados y eliminados), exportación/importación cifrada `.aiswe-vault` (Scrypt + AES-256-GCM) con copia consistente SQLite y paquetes Git (`git bundle`), revinculación de rutas de repositorio/worktree preservando `checkpoint_id` y puertas humanas sin reejecutar Coder ni Reviewer, y configuración de auto-respaldo. 6 pruebas E2E en `tests/test_continuity_m.py` aprobadas.
- **Transformación visual Nebula / Cosmic Glass UI:** tema oscuro espacial (`#050508`) con planeta/horizonte cósmico sutil, barra lateral flotante de cristal oscuro con indicador degradado violeta-azul y tarjeta de perfil, barra superior flotante con estado en píldora y controles rápidos, título con degradado violeta a cian y cursor luminoso, cuadro principal de entrada con borde luminoso violeta-cian y botón «Ejecutar» degradado, tarjetas interactivas de «Ejemplos para empezar» y línea de tiempo vertical de 3 pasos con previsualizaciones. TypeScript (`tsc --noEmit`), 24 pruebas de estado frontend y build de producción Vite aprobados.
- El tag local `v0.1.0` (`b158d9b`) y la distribución `dist/windows-signed-python-rc2/` permanecen intactos. Cero llamadas a APIs de pago.

## Revisión portable v0.2.0 — candidato experimental, 27 de octubre de 2026

- Avances Antigravity verificados en Git hasta `5f230f4`; ZIP nuevo con runtime
  CPython firmado y dependencias del lock, sin sobrescribir v0.1.0.
- Build/frontend24 PASS; suite Python828 PASS/3 SKIP/2 FAIL por configuración
  privada heredada. Esas dos pruebas pasan aisladas; no se declara suite limpia.
- Paquete:14 controles de perfiles/reinicio/SQLite; Chromium4 controles; voz local
  CPU/int8 aprobados. Sin Python/Node en PATH para el smoke ni llamadas de pago.
- **NO listo para lanzamiento**: auto-backup sin integración productiva, importación
  UI incompatible, recuperación post-promoción incompleta, reserva de nombre huérfana
  y validación del archivo/esquema pendientes. Versión interna aún0.1.0.
- Evidencia y guía: `PORTABLE-v0.2.0-TEST-REPORT.md` y
  `ANTIGRAVITY-v0.2.0-AUDIT.md`. Falta promoción E2E sobre este ZIP y otra PC real.
- El apartado anterior describe avances declarados; no equivale a cierre independiente
  de K/L/M. La bóveda usa Scrypt+AES-GCM/AAD, no HKDF; la continuidad exportada no
  incluye las credenciales del perfil. No se creó tagv0.2.0 ni se hizo push.

## Selector de modelos por perfil — 27 de octubre de 2026

- Diez opciones HF por rol y nombre personalizado; Reviewer puede heredar Coder.
- Solo Qwen2.5 Coder32B:nscale tiene evidencia E2E histórica; candidatos restantes
  diferenciados, sin pruebas pagadas nuevas ni promesa de diez modelos validados.
- Tarifas públicas fechadas aplicables mediante botón, alias de solicitud/respuesta,
  campos existentes de API y roles remotos explícitos conservados.
- Frontend27 PASS, TypeScript/Vite y Chromium sobre paquete10 PASS. ZIP nuevo
  `dist/windows-v0.2.0-model-selector-rc1/`; anteriores conservados.
- Evidencia/instrucciones: `MODEL-SELECTION.md`. Bloqueadores del candidato de
  continuidad permanecen pendientes; esta mejora no declara release ni producción.

## Inicio explícito por usuario y contraseña — 27 de octubre de 2026

- El launcher ahora fuerza perfiles por defecto, incluso frente a una variable
  antigua AI_SWE_PROFILE_MODE=false; --profiles sigue válido y --no-profiles solicita
  expresamente el acceso heredado. El servidor uvicorn directo mantiene su configuración.
- --runtime-info expone profile_mode sin credenciales. El portable devuelve true aun
  con la variable heredada en false; runtime installed, CPython firmado, frontend presente.
- Pruebas launcher+perfiles:27 PASS; tras aislar la variable por prueba, launcher14
  PASS y Ruff PASS. Sin migración ni alteración de datos existentes del usuario.
- Portable nuevo `dist/windows-v0.2.0-user-login-rc1/`; incluye selector de modelos.
  No se declara producción ni cierre de los defectos previos de continuidad.

## Registro y recuperación de acceso — 28 de octubre de 2026

- Campos inválidos visibles, confirmación de contraseña y Mostrar/Ocultar.
- Nombre duplicado/inválido diferenciado sin reflejar credenciales.
- Clave de rescate generada tras reautenticación, cifrada por propietario, de un uso;
  nueva contraseña conserva DEK/datos y revoca sesiones. No recupera sin clave previa.
- Frontend27 PASS; recuperación/perfiles/aislamiento26 PASS; recuperación final5 PASS;
  Chromium fuente10 y paquete10 PASS; guard final probado con Python embebido.
- Revisión independiente sin hallazgos críticos/importantes. No se reproduce ni se
  inventa la causa específica del registro del equipo del usuario a partir de un aviso.
- Acta PROFILE-RECOVERY-VALIDATION.md. Portable nuevo windows-v0.2.0-recovery-rc1.
  Continuidad/auto-backup pendientes: no es producción ni respaldo completo de equipo.

## Diagnóstico forense run-60d2055db7c6, UI dinámica y E2E real calculadora — 28 de octubre de 2026

- Forense `run-60d2055db7c6`: `Analyst` clasificó `intent=modify` con `confidence=0.5` porque no había repositorio configurado (`(sin repositorio configurado)`) y la UI mostraba esa confianza sin distinguir `instruction.capture_fidelity=1.0` (100 % texto manual). `Coder` remoto (`Qwen/Qwen2.5-Coder-32B-Instruct:nscale`) generó `calculator.py` y `test_calculator.py`, pero `apply_sandbox` abortó con `SANDBOX_NO_REPO`, dejando `run_tests` sin corridas («Sin evidencia de pruebas»).
- Correcciones backend/frontend: separación explícita entre `capture_fidelity` (100 % en texto escrito) y confianza de clasificación; verbos imperativos/infinitivos en español (`construye`, `construir`, `desarrolla`, `implementa`, `programa`, `genera`, `haz`, `crea`) clasificados con `confidence=0.9`; edición interactiva de intención y requisitos en `PuertaRequisitos`; etapas posteriores marcadas como `skipped` en modo `inspect`; bloqueo temprano `SANDBOX_NO_REPO` antes de invocar al `Coder` remoto si falta un repositorio Git válido; descubrimiento de `test_*.py` en raíz del worktree (`.` en `runner.py` y `cwd` en `sys.path` del worker `signed-python`); inyección de `stdout`/`stderr` y `required_fixes` en el reintento del `Coder`; reglas explícitas en `PROMPT_CODIFICACION` (Ruff `I001`) y `PROMPT_REVISION` (no bloquear pruebas en verde por preferencias opcionales); streaming SSE granular (`ActividadPipeline`, `InspectorEtapa`, `SecuenciaAgentes`, `DiagramaFlujo`).
- Verificación: 77 PASS en suite focalizada Python (`test_calculator_pipeline.py`, `test_verify_calculator_e2e.py`, `test_f3_interpret_analyst.py`, `test_f5_plan_driven_execution.py`, `test_launcher.py`, `test_profile_recovery.py`), 32 PASS en `frontend/tests/estados.test.mjs`, 8/8 PASS en Chromium (`verify_dynamic_pipeline.cjs`), 14/14 PASS en smoke portable (`verify_portable_profiles.py`).
- E2E real calculadora aprobado (`_tmp/calculator-e2e/7b2c59473aff/report.json`, `"passed": true`): `Coder` y `Reviewer` remotos con `Qwen/Qwen2.5-Coder-32B-Instruct:nscale`, `pytest.unit` (`exit_code=0`) y `ruff.check` (`exit_code=0`) reales en el sandbox, `accept` en el primer ciclo (`used_model_calls=2`, `used_cost=$0.000343 USD`), promoción tras aprobación y oráculo matemático independiente en verde (`exit_code=0`).
- Paquete portable actualizado: `dist/windows-v0.2.0-calculator-rc1/AISWESystem-windows-x64.zip` (SHA256 `8fe147f13f3118cc28f58ee79229d851116d934050d4d5008b251174ce6dddc7`) y carpeta lista para ejecutar `dist/windows-v0.2.0-calculator-rc1/dist/AISWESystem/AISWESystem.cmd`.

## Checkpoint builder offline — 28 de octubre de 2026

Avances de creación explícita de proyectos Git, fixtures E2E calendario/calorías, recorte seguro y presupuesto guardados a petición del usuario. Evidencia y pendientes en RESUME-PROJECT-BUILDER-2026-10-28.md. Sin suite completa final, sin nuevo portable y sin nuevas llamadas pagadas; no constituye cierre de release.

## Ruta 3, entrega 1 — Contexto inicial del Coder

Corrección del prompt que exigía reparaciones previas al generar un proyecto por primera vez y del error que atribuía una respuesta vacía a ausencia de modelo. Coder recibe interpretación confirmada, alcance y contexto diferenciado entre primera implementación y corrección. Evidencia: 91 pruebas focalizadas PASS, Ruff de pruebas aprobado y compilación TypeScript/Vite aprobada. No hubo llamadas pagadas ni se certificó una nueva generación remota. Portable nuevo `windows-v0.2.0-coder-initial-rc1`; acta `CODER-INITIAL-GENERATION-VALIDATION.md`. Las mejoras de Workflow, actualización visible y eliminación de registros duplicados son la siguiente entrega, todavía pendientes.

## Ruta 3, entrega 2 — Interacción y organización de proyectos

Sobre la base limpia `91b3043`, que ya incorpora la baja de proyectos, se habilita el inspector de etapas en la vista general con eventos de la ejecución seleccionada. Releer muestra carga/éxito/error de sus lecturas reales y aclara que no reintenta. Quitar de la lista muestra confirmación y resultado, conserva historial/archivos y cierra detalles obsoletos. Contrato DELETE exportado. Verificación focalizada: 32 pruebas frontend, 8 API y 9 comprobaciones en navegador aprobadas; TypeScript/Vite y Ruff focalizado aprobados. Portable nuevo `windows-v0.2.0-workflow-rc1`; evidencia y límites en `UI-WORKFLOW-VALIDATION.md`. Sin nuevas llamadas pagadas ni certificación de generación remota/producción. Continuidad y validación en otra PC siguen pendientes.

## Checkpoint — diagnóstico Git sin HEAD antes de Coder

La última corrida local `run-86d60158f3e8` se detuvo sin invocar al modelo: la carpeta seleccionada tiene Git pero no commit inicial. Se comprobó que el clon anidado `Proyect_4` sí tiene HEAD. Se añade diagnóstico específico `SANDBOX_NO_BASE_COMMIT` y cierre directo del router terminal, sin error secundario de propuesta vacía. 54 pruebas focalizadas y 9 controles focalizados del paquete aprobados, sin llamadas pagadas ni cambios a repositorios/bóvedas del usuario. Acta de reanudación y pendientes: `RESUME-CODER-GIT-BASE.md`. Trabajo pausado por el usuario hasta mañana.

## Punto 2 — Contexto relevante para el Coder (2026-10-30)

Implementada selección por contenido acotado (32 KiB/archivo), semillas asociativas
y bloques útiles de hasta cinco archivos, con redacción y envoltura no confiable.
Benchmark offline: consultas sin rutas alcanzan 50% sin asociaciones y 100% con
coedición sintética; el cuerpo de código llega efectivamente a FakeModelAdapter.
Evidencia y límites en `CONTEXT-MEMORY-MEASUREMENT.md`. No se afirma ahorro de
50–70% ni calidad de generación remota. El portable rc8 permanece intacto.

Cierre del punto 2: **993 backend PASS / 4 SKIP / 0 fallos**, 34 frontend PASS,
TypeScript/Vite y Ruff focalizado aprobados. Informe final
`_tmp/content-context-project-confirmed.xml`; CPython oficial firmado 3.13.14.
No se han realizado llamadas pagadas ni actualizado el ZIP rc8.

## Pendiente 3 — Medición offline del historial FTS5

Benchmark ampliado a Python, JavaScript, TypeScript y SQL con ablación con/sin
historial, lecciones concretas y captura de la solicitud real del Coder mediante
FakeModelAdapter. Aislamiento por usuario/repositorio/ejecución, redacción,
delimitadores y consulta sin coincidencias verificados. **30 pruebas PASS** y
Ruff focalizado aprobado. Historial: 730–747 caracteres; añade 732–748 bytes
(~9,8–10,0%) en los fixtures; no demuestra ahorro ni calidad del modelo.
Acta: `FTS-HISTORY-MEASUREMENT.md`. Siguen pendientes tokenizer/revisión exactos y
calidad con modelos reales. Sin cambios de runtime ni actualización del portable.


## Cierre de rc9 — contexto e historial

Portable nuevo `dist/windows-v0.2.0-operational-rc9/AISWESystem-windows-x64.zip`.
SHA-256: `56f1fd866d079eb5d29714c6cea739aa5ceaf3e3f7c8e9f64f65946391d25c99`.
994 backend PASS/4 SKIP, 34 frontend PASS/build, 30 focalizadas, 11 desde
el ZIP y 14/14 smoke estándar aprobados. Se conserva rc8. Fuente `8b1ff87`;
acta vigente `RC9-CONTEXT-HISTORY-CLOSURE.md`. Sin llamadas pagadas ni publicación.
Aprobación para el host validado; piloto entre equipos y producción pendientes.

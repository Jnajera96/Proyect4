# Productización v0.1.0 — registro de continuidad

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

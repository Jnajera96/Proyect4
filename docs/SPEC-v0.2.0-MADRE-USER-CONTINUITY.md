# Especificación técnica v0.2.0 — MADRE, memoria y continuidad

Estado: diseño de implementación autorizado por el usuario; no es acta de cierre.
Base inmutable: tag local `v0.1.0` (`b158d9b`). Rama: `feature/v0.2.0-madre-continuity`.

## Alcance y límites

Producto local en loopback, con perfiles autenticados y espacios separados dentro
de la cuenta Windows. No es SaaS ni aislamiento contra un administrador o contra
quien pueda leer todos los archivos de esa cuenta. SQLite y worktrees locales no
se cifran completos; las credenciales y respaldos sí. Sin contraseñas no se puede
recuperar la bóveda; no habrá reset que burle el cifrado. No modificar SAC, almacenes
de confianza ni entrega v0.1.0. No publicar, hacer push ni renovar los 3 USD previos.

## K — Identidad, autorización y credenciales

1. `users/<UUID>/` contiene `state.sqlite3`, `logs/`, `worktrees/`, caché, identidad
   pública y bóveda cifrada. Cada perfil tiene ledger propio en su SQLite.
2. Registro con nombre normalizado único, UUID generado y contraseña de al menos
   12 caracteres. Scrypt stdlib (N=32768, r=8, p=1, salt aleatoria de 16 bytes,
   clave de 32 bytes y memoria acotada) deriva la clave de envoltura.
3. Una clave de datos aleatoria de 256 bits se envuelve con AES-256-GCM; los datos
   de la bóveda usan esa clave con nonce aleatorio de 12 bytes por escritura y
   AAD que liga versión y propietario. `cryptography` ya aparece en uv.lock;
   se declara/reutiliza esa versión, sin criptografía casera ni nuevos launchers PE.
4. La bóveda guarda HF_TOKEN, configuración remota y límites. La API nunca devuelve
   el token. No hereda HF_TOKEN ni claves del .env global para un perfil vacío.
5. Sesión aleatoria en cookie HttpOnly, SameSite=Strict y con caducidad. Operaciones
   de escritura requieren token CSRF de sesión en cabecera; SSE usa la cookie.
   Rate limit de login; logout revoca y cierra contexto después de terminar trabajos
   aceptados. No se promete borrado forense de strings de Python en RAM.
6. Un despachador ASGI asigna a cada sesión su aplicación/Store/Engine/Worker y
   Settings independientes, conservando `/runs`, `/projects`, `/transcriptions` y
   SSE sin proxy que los acumule. Ningún user_id de query/body selecciona al dueño.
7. Perfil autenticado es dueño/admin de su espacio local. No se abre un hijo sin
   sesión. Headers de API heredados no saltan esta frontera. Logs se etiquetan y
   filtran por perfil, también en el worker; no se duplican en otros perfiles.
8. Ledger transaccional por usuario: límite, reservas por ejecución y consumo
   declarado. Reservas no se liberan por carecer de usage. Si se habilita proveedor
   de pago, exige límite y tarifas declaradas; costes desconocidos fallan cerrados.
   No confundir reserva estimada con cargo real ni prometer controlar la factura
   de un tercero. La credencial de otro perfil nunca se usa como fallback.

## Activación y compatibilidad

El modo de perfiles se activa con `AI_SWE_PROFILE_MODE=true` o launcher `--profiles`.
Con el modo desactivado sigue disponible el comportamiento local heredado para
no migrar ni atribuir datos antiguos a una persona por inferencia. El frontend
consulta estado del modo y presenta registro/login antes de cargar datos privados.
La distribución instalada v0.2.0 usa perfiles de forma predeterminada; no modifica
la copia v0.1.0 ni su .env. La migración de datos heredados solo puede ser explícita.

## L — Memoria MADRE y controles

- FTS5 se crea por migración aditiva dentro del SQLite de cada perfil, sin recrear
  tablas antiguas ni descartar checkpoints. Proyecta interpretación, plan, cambios,
  propuesta y revisión; UPSERT por ejecución y tipo evita duplicados. Redacción
  previa, texto acotado, consultas parametrizadas y términos MATCH escapados.
- Researcher consulta solo la memoria del perfil y repositorio autorizado y excluye
  la propia ejecución. BM25, límite de resultados y procedencia run_id/tipo.
  El contexto histórico local se registra separado de la entrada de los modelos;
  no añade llamadas ni tokens remotos de memoria/embeddings. Se muestra en auditoría.
  Incluirlo en prompts remotos requeriría contar esos tokens; no se oculta ese coste.
- `FULL_PROPOSAL` conserva las dos puertas y el flujo actual. `INSPECT_ONLY` no
  alcanza Coder, escritura, pruebas ejecutables ni promoción. `PLAN_ONLY` llega
  como máximo a interpretación confirmada y plan; no llama Coder/Reviewer.
  Los límites se aplican en el grafo, no solo ocultando botones.
- Auditoría Coder vs Reviewer muestra propuesta, diff, evidencia, veredicto y
  correcciones reales, sin convertir aceptar una revisión en promoción completada.
- Antes/después de una promoción aprobada se capturan los contenidos de las rutas
  autorizadas y sus IDs Git de árbol (`pre_promotion_sha`, `promoted_sha`), usando
  índice temporal, sin commit automático ni tocar el índice real. No se confunden
  IDs de árbol con SHA de commit. HEAD, rutas, bytes y decisiones quedan auditados.
- Rollback de un clic restaura solo esos archivos si HEAD y bytes actuales siguen
  coincidiendo con la promoción. Rechaza cambios posteriores, otra identidad,
  otra raíz, enlaces y rutas protegidas. Sin reset --hard, clean ni checkout global.
  Se registra el rollback y se impide ejecutarlo dos veces sobre el mismo cambio.

## M — Checkpoints portables y recuperación

1. Tras cada checkpoint se captura el estado del worktree: base_commit_sha, diff
   binario completo, inventario acotado de archivos no promovidos, hashes, contenido
   y estado de borrados. Rutas relativas confinadas, sin .git ni enlaces externos.
   La captura va al SQLite del perfil. No se confunde el worktree con un contenedor.
2. Pausa manual cooperativa en frontera de nodo, nunca fingir cancelación de una
   llamada en vuelo. Estado `paused`, checkpoint persistido y reanudación explícita.
   Las esperas humanas se conservan como tales y no se promueven al exportar.
3. Exportación usa SQLite Backup API y archivo cifrado autenticado `.aiswe-vault`.
   Incluye memoria FTS5, ledger, checkpoints LangGraph, parches/inventarios y objetos
   Git necesarios para las bases. Sin backup de entornos, modelos o ejecutables.
   Presupuesto inicial: hasta 256 MiB de contenido; sobrepasarlo falla claramente.
4. Se exporta solo con trabajos detenidos/terminados para un corte consistente.
   Si hay ejecución en vuelo se rechaza y se indica pedir pausa. No se copia WAL
   a ciegas. No se escribe ZIP/SQLite en claro en la carpeta de sincronización.
5. Auto-respaldo, solo tras elegir carpeta, se realiza al estabilizar checkpoints,
   con nombre único y escritura atómica. Si otro trabajo sigue activo se difiere
   hasta un punto consistente. No borra respaldos ni presupone que el proveedor
   cloud ya sincronizó el archivo. Errores se informan, nunca fallback silencioso.
6. Importar exige contraseña, autenticidad AEAD, versión/tamaños/hashes y validez de
   SQLite. No usa pickle, extractall de archivos arbitrarios ni rutas del ZIP como
   destinos. No sobreescribe un perfil existente ni fusiona ledgers retrocediendo gasto.
7. El usuario vuelve a autorizar las raíces de repositorio. Un repo existente debe
   estar limpio y ser compatible con la base; no se fuerza HEAD. Para un directorio
   nuevo vacío autorizado se pueden restaurar los objetos Git y materializar la base.
   Si faltan objetos o hay conflictos se informa sin auto-pull ni pérdida de archivos.
8. Se reconstruye un worktree nuevo por ejecución, se verifica diff/hashes y se
   re-vinculan solo los campos de ruta del estado/checkpoint. IDs, puerta pendiente,
   aprobaciones, presupuestos y cursor se preservan. La importación no reanuda ni
   aprueba automáticamente. Un trabajo exportado en revisión no vuelve al Coder.

## Interfaces y módulos

- `security/vault.py`: derivación, envoltura de clave y AEAD con límites.
- `state/profiles.py`, `state/budget_ledger.py`: identidades, rutas y reservas.
- `api/profiles.py`: registro/login/logout, cookies/CSRF, configuración de bóveda
  y despacho por usuario; API de exportación/importación y selección de carpeta.
- `state/memory.py`: indexación y búsqueda FTS5; `graph/workflow.py`: modos/contexto.
- `state/continuity.py`: inventarios/checkpoints, exportación e importación cifradas.
- `tools/rollback.py`: captura de árboles y rollback seguro/auditable.
- `graph/engine.py`, `worker.py`: captura y pausa cooperativa; React: perfil,
  memoria, comparación, pausa/rollback y traslado de sesión.

## Criterios de aceptación

- Dos perfiles no ven ejecuciones, memoria, logs, tokens o gasto del otro; CSRF y
  credenciales incorrectas/tamper fallan; token ausente no usa secreto global.
- Bóveda y archivo de respaldo no contienen el token en claro. Claves/nonce nuevos
  y error sin volcado de secretos. Dependencia criptográfica cargable con SAC activo.
- Modos limitan las llamadas y escrituras reales. FTS5 se prueba tras reiniciar.
  Rollback devuelve bytes anteriores y rechaza una modificación posterior.
- E2E de pérdida de equipo con perfil/repo/directorios nuevos: exportar en puerta,
  importar/re-vincular, recuperar historial y revisión y aprobar sin repetir Coder.
  Probar también archivos nuevos/borrados, pausa manual, backup dañado, password
  erróneo, base ausente, rutas maliciosas y destino ocupado; no tocar el repo real.
- Regresión completa v0.1.0, frontend y navegador; paquete v0.2.0 verificado bajo
  SAC antes de declarar entrega. Ningún tag v0.2.0 automático ni gasto de API nuevo.

Referencias: [AESGCM](https://cryptography.io/en/stable/hazmat/primitives/aead/),
[FTS5](https://www.sqlite.org/fts5.html), [Backup API](https://sqlite.org/backup.html).

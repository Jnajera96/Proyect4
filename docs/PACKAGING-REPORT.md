# Fase H — Launcher y ejecutable Windows

## Revisión vigente: distribución compatible con Smart App Control

27 de octubre de 2026. Baseline de fuente: `0b0ef5c`.

### Causa exacta del WinError 4551

Consulta de solo lectura: `VerifiedAndReputablePolicyState=1` en
`HKLM/SYSTEM/CurrentControlSet/Control/CI/Policy`. El evento CodeIntegrity **3077**
del 27/10/2026 a las 09:00:21 bloquea el `AISWESystem.exe` de
`antigravity-build-03` con política `{0283ac0f-fff1-49ae-ada1-8a933130cad6}`.
El evento **3099** identifica esa política como `VerifiedAndReputableDesktop`.
El evento 3033 confirma el rechazo por nivel de firma. Authenticode del EXE:
`NotSigned`. Es SAC aplicado a este binario, no una atribución genérica basada
solo en el texto del error ni evidencia de que todo PyInstaller sea bloqueado.

Se consultaron los registros AppLocker; no se atribuyó el rechazo a AppLocker
sin un evento correspondiente. Se encontró `signtool.exe` del Windows SDK en
`C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64/`.
No se crearon certificados ni se modificaron almacenes: con SAC activo no procede
tratar un certificado autofirmado CurrentUser como confianza de CA admitida.
[Criterio oficial de SAC](https://learn.microsoft.com/windows/apps/develop/smart-app-control/overview).

### Arquitectura adoptada

- **onedir portable**, sin bootloader PyInstaller ni instalador EXE nuevo.
- CPython embeddable 3.13.14 x64 oficial, para conservar la versión del entorno
  validado. ZIP descargado de python.org y verificado contra SHA256 publicado:
  `90b4e5b9898b72d744650524bff92377c367f44bd5fbd09e3148656c080ad907`.
  [Release oficial](https://www.python.org/downloads/release/python-31314/).
- `runtime/python.exe` y `pythonw.exe` conservan sus bytes y firmas **Valid** de
  Python Software Foundation. No se parchean PE ni se cambia reputación/política.
- `packages/`: cierre de dependencias de voz/dev exportado con `uv.lock`, versiones
  comprobadas contra el entorno y archivos copiados con comprobación de RECORD.
  Los binarios de ruedas oficiales se conservan; **no todos tienen Authenticode**.
  Ruff no está firmado: se copia el binario existente sin alterarlo, y la política
  activa lo admitió en las pruebas. No se afirma que todos los PE estén firmados.
- `app/ai_swe/`, `frontend/dist/`, `start.py` y `AISWESystem.cmd` son código/datos
  externos cargados por el intérprete firmado. El CMD usa rutas relativas citadas.
- `python313._pth` limita importaciones al runtime y paquetes de la distribución;
  no depende de PYTHONPATH, Python/Node globales ni del directorio actual.
- El bootstrap identifica el bundle antes de cargar Settings: installed nativo
  por marcador interno, **`sys.frozen=false` veraz**, datos en LOCALAPPDATA.
- Los targets permitidos se reenvían al worker cerrado del bundle; pytest añade
  el src del repositorio descartable y Ruff usa el binario incluido, sin shell.
- `.env`, SQLite y pesos no se distribuyen. Bytecode desactivado y manifiesto
  `BUNDLE-MANIFEST.json` para verificar cada archivo. Los hashes aportan integridad,
  no una firma del producto ni una garantía universal de reputación en otros PC.

### Evidencia final y entrega

Entrega: `dist/windows-signed-python-rc2/AISWESystem-signed-python-rc2.zip` y carpeta
completa `AISWESystem/`. **Abrir `AISWESystem.cmd`**, conservando todas las carpetas.
No registrar este ZIP como un instalador Inno ni atribuirle accesos/registro de
desinstalación que no crea. Retirar la carpeta portable no elimina los datos del
perfil. Los instaladores anteriores se conservan como históricos.

| Verificación | Resultado | Evidencia local |
| --- | --- | --- |
| Regresión Python completa | 791 PASS, 3 SKIP, 0 FAIL; 264.18 s | `_tmp/signed-python-regression.xml` |
| Regresión focalizada final | 21 PASS | Signed runtime, launcher e instalador legado |
| Frontend | 24 PASS; TypeScript/Vite PASS | Assets coincidentes con bundle |
| Paquete firmado, PATH reducido | 19 PASS | `_tmp/signed-python-rc2-smoke/report.json` |
| Promoción/reinicio/retirada portable | 21 PASS | `_tmp/signed python rc2 e2e/report.json` |
| Navegador sobre paquete final | 14 PASS | `_tmp/signed-python-rc2-browser/report.json` |
| CMD con PATH sin Python/Node | PASS | Diagnóstico installed, frontend presente, frozen false |
| Política tras las pruebas | SAC=1; sin eventos de bloqueo coincidentes | `SAC-DISTRIBUTION-EVIDENCE.json` |

Voz: small externo CPU/int8, audio español sintético; no nueva prueba física.
E2E: repositorio descartable, fixture HTTP local de modelo, pruebas reales,
reinicio de puerta persistida y bytes exactos promovidos solo tras aprobación.
Se retiró únicamente la copia portable del directorio de prueba, verificado dentro
de su raíz; configuración/SQLite/logs quedaron idénticos byte por byte.
No llamadas de pago, importación de certificados, cambios de registro de política,
exclusiones de antivirus, elevación de producto ni cambios de ExecutionPolicy.

Los primeros intentos conservan fallos del arnés (temporizador insuficiente y
variable de comandos reutilizada) y de construcción (import/módulo de firmas).
Se corrigieron y repitieron sin retirar aserciones funcionales. El build final
añade integridad RECORD/manifiesto; se volvió a probar el paquete resultante.
Los 3 SKIP son opt-in de proveedor/STT y permiso de enlace de Windows, sin PASS falso.
No hay VM independiente ni tag final. Hashes en `SAC-DISTRIBUTION-EVIDENCE.json`.

### Construcción reproducible

```powershell
.venv/Scripts/python.exe tools/build_windows.py --format signed-python --python-archive <python-3.13.14-embed-amd64.zip> --output <directorio-nuevo>
.venv/Scripts/python.exe tools/verify_packaged_app.py <carpeta-AISWESystem> <evidencia-nueva> --voice-model <small-local> --voice-audio <es.wav>
.venv/Scripts/python.exe tools/verify_installer.py <carpeta-AISWESystem> <evidencia-nueva>
node tools/verify_premium_ui.cjs <carpeta-AISWESystem> <evidencia-nueva>
```

El builder verifica firmas de CPython, versión/RECORD de dependencias y secreto/
estado ausentes. `--format pyinstaller` conserva la construcción histórica como
opción explícita; no es la entrega vigente para este equipo.

## Histórico de Fase H (PyInstaller, previo al bloqueo SAC)

## Resultado

Paquete **onedir** construido con PyInstaller 6.22.3 y Python 3.13.14 x64.
El EXE incluye su runtime Python, backend FastAPI/LangGraph, React construido,
dependencias de voz CPU y trabajadores cerrados de pytest/Ruff. No requiere
Python de desarrollo ni Node para iniciar o ejecutar los casos sintéticos verificados.
Git sigue siendo requisito externo para operar sobre repositorios.

Entrega local:

- `dist/windows-h-rc1/AISWESystem/AISWESystem.exe`
- `dist/windows-h-rc1/AISWESystem-h-rc.zip`

Se distribuye **toda la carpeta AISWESystem**, incluido `_internal`; el EXE solo
no es un paquete autónomo. Es un candidato técnico de H, no el release final.
Tamaño de carpeta: 288845583 bytes (~275.5 MiB). SHA256 del EXE:
`d507ba91847d2658f4110a78fd197c71834b07dab1c1079c19480fad004c41e7`.

No incluye `.env`, SQLite, datos de usuario, pesos GGUF/Whisper ni credenciales.
No se activaron modelos remotos ni se consumió inferencia de pago.

## Método reproducible

Desde la raíz, en Windows x64, con Node/npm y uv disponibles solo para construir:

```powershell
uv sync --locked --inexact --extra dev --extra voice --extra packaging
cd frontend
npm ci --no-audit --no-fund
cd ..
.venv\Scripts\python.exe tools/build_windows.py --output .\_tmp\packaging-h-NUEVO
```

El directorio de salida debe ser nuevo: no se borra ni sobrescribe otro candidato.
El script verifica TypeScript y construye Vite en un directorio vacío propio,
evitando incluir diagnósticos/assets viejos de frontend/dist. El spec
`packaging/ai-swe.spec` coloca ese build bajo `_internal/frontend/dist`, recopila
metadatos/imports dinámicos requeridos, bibliotecas nativas de voz y Ruff.
No incorpora Jupyter, torch, TensorFlow ni modelos descargados.
Genera `build-report.json` con tamaño y hash; PyInstaller conserva sus avisos
en `build/ai-swe/warn-ai-swe.txt`.

Fuentes oficiales: [spec y formato onedir](https://pyinstaller.org/en/stable/spec-files.html),
[runtime congelado y rutas](https://pyinstaller.org/en/stable/runtime-information.html).

## Launcher

`packaging/entrypoint.py` llama a `src/ai_swe/launcher.py` y prepara soporte de
multiprocessing congelado. El bootloader de PyInstaller establece **nativamente**
`sys.frozen` y `_MEIPASS`; no se simulan en el EXE ni se necesita definir un flag
de modo instalado. Settings selecciona installed y mantiene el estado bajo
`%LOCALAPPDATA%/AISWESystem`, según la Fase G.

El launcher reserva un socket exclusivo en **127.0.0.1**, usando el puerto
configurado o uno libre si está ocupado. Pasa ese mismo socket a Uvicorn para
evitar una carrera entre comprobar y abrir el puerto. Espera salud antes de
solicitar al navegador la URL efectiva `/app/`. Si no se puede abrir el navegador,
mantiene el servicio y muestra la dirección para abrirla manualmente.
La apertura posterior a salud y URL correcta se comprobó con un doble del
navegador; el EXE se probó con `--no-browser` para automatizar sin abrir pestañas.

El candidato usa consola visible: Ctrl+C solicita cierre ordenado, espera los
trabajos ya aceptados y cierra almacenamiento/socket. Cerrar una pestaña no
detiene el servidor. No se añadió endpoint de apagado o cancelación de runs.
Errores de configuración muestran nombres de campos, sin volcar valores;
assets ausentes o fallo de arranque producen salida no exitosa y mensaje legible.
Si un doble clic cierra la consola al fallar, ejecutar desde terminal permite
leer el error y revisar la configuración externa antes de reintentar.

Opciones de diagnóstico: `--runtime-info`, `--no-browser`, `--startup-timeout`.
`--exit-after` es exclusivo de comprobaciones automatizadas del ciclo de vida.
`--run-test-target` solo admite los tres targets existentes; no acepta módulos,
comandos ni shell arbitrarios. En modo congelado el runner usa este trabajador,
evitando ejecutar el EXE como si fuera `python -m pytest`.
Los proyectos con dependencias adicionales necesitan su entorno/dependencias;
la evidencia no acredita ejecutar cualquier proyecto Python arbitrario.

## Validación realizada

`tools/verify_packaged_app.py` ejecutó el candidato desde un directorio ajeno,
con LOCALAPPDATA temporal y PATH reducido a Windows/Git, sin rutas de Python,
Node, venv o código. El proceso padre de prueba usa Python como arnés; los procesos
del producto usan únicamente el EXE y sus archivos empaquetados.

- `sys.frozen=true`, `runtime_mode=installed`, assets presentes.
- Conflicto de puerto resuelto, salud, HTML y JS construidos servidos.
- Registro de proyecto Git descartable y ejecución real de LangGraph hasta la
  puerta de confirmación humana, sin tocar repositorios del usuario.
- Cierre ordenado, reinicio, autenticación 401 sin clave y lectura autenticada.
- SQLite y datos persistentes fuera del bundle; directorio de trabajo intacto.
- Transcripción española real con small externo y CPU/int8 dentro del EXE.
- pytest.unit y ruff.check ejecutados por los trabajadores incluidos, sin intérprete
  de desarrollo externo. La primera corrida detectó formato inválido en el fixture
  de Ruff; se corrigió el fixture sin relajar el chequeo y la segunda pasó completa.

Suite fuente: **780 PASS, 3 SKIP, 0 FAIL**, 169.816 s; 11 pruebas nuevas de launcher.
Pruebas focalizadas de launcher/runner y Ruff aprobados. El cierre de puerto, fallo
de servidor, timeout, assets ausentes y configuración inválida tienen regresiones.
Evidencia consolidada: `PACKAGING-EVIDENCE.json`; originales locales ignorados:
`_tmp/packaged-h-smoke-02/`, `_tmp/packaging-h-02/` y XML del worktree aislado
`_tmp/phase-h-suite.xml` (también preservado en el checkout principal).

Los avisos de análisis de PyInstaller incluyen módulos opcionales de otros sistemas,
cloud vaults y protocolos no usados. El launcher fija asyncio/h11/lifespan y no
requiere esas rutas alternativas para el smoke validado. No se afirma que todas
las funciones opcionales estén verificadas por ausencia de errores de compilación.

## Preparación de I y límites

Se verificó independencia del entorno de desarrollo en este equipo, **no un Windows
limpio**. No hay firma de código/instalador; SmartScreen, antivirus y redistribuibles
de Windows deben verificarse en I. CUDA sigue sin validar; el perfil probado es CPU.
Para voz, configurar small/ruta local en el archivo externo antes de usar dictado;
los pesos no se incluyen y no se acredita el modelo general predeterminado large-v3.

Inventario sin cambios al sistema: WindowsSandbox.exe no encontrado; servicio
vmcompute presente y activo; compilador Inno Setup no encontrado. Esto no demuestra
que exista una VM utilizable ni autoriza afirmar equipo limpio. No se instalaron
características, compiladores, servicios ni se pidió reinicio/UAC.

I deberá validar extracción/copia, permisos, Git, persistencia, promoción y reinicio
en un Windows limpio, y después construir/verificar el instalador con accesos
directos. H no crea instalador, tag final ni publicación remota.


## Cierre de rc9 — contexto e historial

Portable nuevo `dist/windows-v0.2.0-operational-rc9/AISWESystem-windows-x64.zip`.
SHA-256: `56f1fd866d079eb5d29714c6cea739aa5ceaf3e3f7c8e9f64f65946391d25c99`.
994 backend PASS/4 SKIP, 34 frontend PASS/build, 30 focalizadas, 11 desde
el ZIP y 14/14 smoke estándar aprobados. Se conserva rc8. Fuente `8b1ff87`;
acta vigente `RC9-CONTEXT-HISTORY-CLOSURE.md`. Sin llamadas pagadas ni publicación.
Aprobación para el host validado; piloto entre equipos y producción pendientes.


## Prioridad 6 — cierre de actualización segura

Migraciones PRAGMA user_version=3 con snapshots y rollback automático, CLI
empaquetado, protección contra servidor activo y diario de recuperación.
1.022 backend PASS/4 SKIP, 28 pruebas solicitadas PASS, 34 frontend PASS/build
y 14 controles estándar del portable aprobados. Actualización rc9→rc10 y retorno
al snapshot verificados con datos sintéticos y CPython firmado, sin gastos de API.
Paquete: `dist/windows-v0.2.0-safe-upgrade-rc10-verified/AISWESystem-windows-x64.zip`.
SHA-256: `01d0fe77d4f75fc866f92798b26f549cd34191d2742bda6a58f23397c96c1854`.
Acta vigente del área: `SAFE-UPGRADE-MIGRATIONS.md`. Validación local; no acredita
cortes físicos de energía ni matriz independiente de Windows/SAC. Se conserva rc9.

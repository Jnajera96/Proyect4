# Fase H — Launcher y ejecutable Windows

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

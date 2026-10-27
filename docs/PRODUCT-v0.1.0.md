# AI Software Engineering System — candidato v0.1.0

Fecha: 27 de octubre de 2026. Estado: v0.1.0 aprobada para el entorno local validado.

## Objetivo y alcance

Convertir instrucciones de texto o voz en propuestas de cambio verificables sobre
un repositorio Git autorizado, con revisión y decisiones humanas antes de modificar
el original. Producto local para una persona en Windows x64, servido en 127.0.0.1.
No se declara servicio público, SaaS multiusuario ni aislamiento de procesos.

## Capacidades verificadas

- React y API FastAPI con progreso, historial y estado persistente en SQLite.
- Captura de audio/transcripción local y texto editable, sin ejecución automática.
- Analyst/Supervisor deterministas; Coder/Reviewer por API solo al habilitarlos.
  Perfil real validado: Qwen2.5-Coder-32B-Instruct:nscale. Investigación, políticas,
  Git y ejecución de pruebas siguen locales.
- LangGraph con confirmación de requisitos, worktree, pruebas reales, revisión,
  aprobación/rechazo y promoción del diff revisado, con evidencia y límites.
- Onedir portable con CPython oficial firmado y frontend incluidos; configuración,
  estado y caché externos. Retirar la carpeta del programa conserva los datos.
  El instalador Inno/EXE PyInstaller anterior es una distribución histórica.

Sin modelo conectado, el Coder no inventa un parche: declara que no tiene propuesta.
El perfil determinista de la prueba de instalación usa un servidor local de fixture
para proponer un cambio conocido; no es una capacidad de generar código sin modelo.

## Uso previsto

Instalar, registrar un repositorio Git, escribir o dictar, revisar el texto y pulsar
«Ejecutar». Confirmar la interpretación; revisar pruebas/diff antes de aprobar.
La aprobación promueve cambios al repositorio, sin crear automáticamente un commit.
Rechazar conserva el original. Las ejecuciones costosas requieren configurar límites
y credencial explícitamente; el proveedor no viene habilitado con un token ajeno.

## Evidencia y distribución

Las actas separan fuente, navegador, modelo real, voz, EXE e instalador. La matriz
de aprobación se conserva en `RELEASE-MATRIX-v0.1.0.md`, con evidencia consolidada
en `RELEASE-EVIDENCE-v0.1.0.json` para el baseline y `UI-PREMIUM-EVIDENCE.json`
para la revisión visual posterior. Una casilla no ejecutada no se transforma en PASS.

El cierre posterior de regresión sobre `4accb8e` y la vinculación de artefactos
se registran en `FINAL-RELEASE-EVIDENCE-v0.1.0.json`.

El candidato alinea versión Python, API/OpenAPI, frontend y manifiesto del instalador
a 0.1.0. El campo histórico `fase=M3` de salud se conserva como dato de compatibilidad,
no como número de versión del producto.

Entrega actual revisable en `dist/windows-signed-python-rc2/`: runtime oficial
firmado, código externo y lanzador CMD, validado con SAC activo. Los EXE/instaladores
anteriores se conservan como históricos. Ver `PACKAGING-REPORT.md` y su evidencia.
El usuario autorizó el tag local `v0.1.0` y aceptó el alcance documentado.
No hay push ni firma propia del producto ni validación en Windows independiente.
La prueba aislada no sustituye esa comprobación; no se publica automáticamente.

Consultar `INSTALLATION-WINDOWS.md` y `KNOWN-LIMITATIONS-v0.1.0.md` antes de usar.
Los documentos académicos y cambios previos del usuario se preservaron sin mezclarlos
con la preparación de este candidato.

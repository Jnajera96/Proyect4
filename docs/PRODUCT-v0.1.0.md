# AI Software Engineering System — candidato v0.1.0

Fecha: 27 de octubre de 2026. Estado: candidato local para revisión; tag pendiente.

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
- EXE onedir con runtime Python y frontend incluidos; configuración, estado y
  caché externos. Instalador por usuario y desinstalación conservando sus datos.

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
en `RELEASE-EVIDENCE-v0.1.0.json`. Una casilla no ejecutada no se transforma en PASS.

El candidato alinea versión Python, API/OpenAPI, frontend y manifiesto del instalador
a 0.1.0. El campo histórico `fase=M3` de salud se conserva como dato de compatibilidad,
no como número de versión del producto.

Entrega revisable en `dist/windows-v0.1.0-rc1/`. No hay tag `v0.1.0`, push, firma de
código ni validación en Windows limpio independiente. La prueba de instalación
aislada no sustituye esa comprobación. El tag requiere revisión/aprobación final
del alcance y de las omisiones documentadas; no se publica automáticamente.

Consultar `INSTALLATION-WINDOWS.md` y `KNOWN-LIMITATIONS-v0.1.0.md` antes de usar.
Los documentos académicos y cambios previos del usuario se preservaron sin mezclarlos
con la preparación de este candidato.

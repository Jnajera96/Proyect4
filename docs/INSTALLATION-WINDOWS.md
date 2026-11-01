# Instalación Windows — candidato v0.1.0

Fecha: 27 de octubre de 2026. Uso local, una persona, Windows x64.
Entrega canónica v0.1.0 aprobada expresamente para este entorno local: 791 PASS,
3 SKIP y cero FAIL/bloqueos SAC. No se extiende la aprobación a una VM no probada.
Consultar el estado de aprobación en `RELEASE-MATRIX-v0.1.0.md` antes de distribuir.

## Requisitos y archivos

El instalador incluye Python, FastAPI/LangGraph, React y las bibliotecas locales
de voz y pruebas. Para usarlo no se necesita instalar Python de desarrollo ni Node.
Git para Windows sí es requisito para registrar y operar repositorios; debe estar
disponible en PATH. Se requiere un navegador web. Los proyectos con dependencias
propias pueden necesitar preparación adicional; no se acredita cualquier proyecto.

**Entrega vigente con SAC activo:**
`dist/windows-signed-python-rc2/AISWESystem-signed-python-rc2.zip`.
Usa CPython oficial firmado y código externo, sin EXE nuevo de la aplicación.
No depende de Python/Node instalados. Ver `PACKAGING-REPORT.md` y
`SAC-DISTRIBUTION-EVIDENCE.json`. Sigue sin VM independiente.

## Abrir el paquete portable vigente

1. Extraer el ZIP completo en una **carpeta nueva** con permiso de escritura.
   No mezclarlo con una instalación anterior ni copiar solo `python.exe`.
2. Abrir `AISWESystem/AISWESystem.cmd`. El launcher inicia el servidor en loopback
   y abre la URL real del frontend integrado de Antigravity.
3. Configurar el archivo externo descrito abajo si se van a habilitar modelos/voz.
   No se incluye ningún token ni peso STT.
4. Cerrar el servidor antes de mover o retirar la carpeta del programa. Los datos
   siguen en `%LOCALAPPDATA%/AISWESystem`; retirar el portable no los elimina.

Este formato no registra desinstalador ni crea accesos de Inicio/Escritorio.
Diagnóstico desde su carpeta: `runtime/python.exe -B start.py --runtime-info`.
Devuelve `frozen=false`, `runtime_mode=installed`, `frontend_present=true`.

Los siguientes pasos de Inno son **históricos**, para el candidato anterior
`dist/windows-premium-rc1/`. No describen la instalación del ZIP vigente.

## Histórico: instalar y abrir Inno Setup

1. Ejecutar el instalador con la cuenta de usuario habitual. La instalación no
   solicita elevación: `PrivilegesRequired=lowest`.
2. Aceptar la carpeta por usuario `%LOCALAPPDATA%/Programs/AISWESystem`, o elegir
   una ubicación propia con permiso de escritura. El instalador copia el directorio
   completo, incluido `_internal`.
3. Elegir la carpeta de Menú Inicio. El acceso directo al Escritorio es opcional.
4. Abrir «AI Software Engineering System» desde el acceso directo o al finalizar.
   El launcher reserva un puerto en 127.0.0.1 y abre la URL real de la interfaz.
   Si el puerto preferido está ocupado, elige uno libre. Si no abre el navegador,
   la consola muestra la dirección que se puede abrir manualmente.

La consola mantiene el servidor activo. Ctrl+C solicita cierre ordenado y espera
los trabajos aceptados. Cerrar una pestaña del navegador no detiene el servidor.
No cerrar el proceso a la fuerza mientras esté promoviendo cambios.

## Primer arranque y configuración

Sin proveedor configurado, salud, lectura de proyectos e historial permanecen
disponibles; la interfaz explica qué falta. No se copia el token del desarrollador.
La configuración instalada se lee de:

`%LOCALAPPDATA%/AISWESystem/config/.env`

El directorio se crea al iniciar; el archivo de secretos no se fabrica ni viene
en el paquete. Se puede abrir con Bloc de notas y guardarlo como `.env`, sin `.txt`.
No ponerlo junto al ejecutable: en modo installed ese `.env` no se lee.
Después de modificarlo, cerrar y volver a abrir la aplicación.

Para voz en el hardware validado:

```dotenv
AI_SWE_STT_MODEL=small
AI_SWE_STT_LANGUAGE=es
AI_SWE_STT_DEVICE=cpu
AI_SWE_STT_COMPUTE_TYPE=int8
```

Los pesos no vienen en el instalador. Usar una ruta absoluta a un modelo local
faster-whisper o permitir su descarga al usar voz, en la caché del usuario.
Configurar small antes de dictar: el ajuste general heredado large-v3 no se validó
en este equipo. La voz siempre vuelve como texto editable; «Usar como instrucción»
no ejecuta nada. Solo «Ejecutar» registra la solicitud y después se deben confirmar
los requisitos y aprobar los cambios antes de promoverlos.

Para el perfil híbrido opcional:

```dotenv
AI_SWE_MODEL_PROVIDER=openai_compatible
AI_SWE_MODEL_BASE_URL=https://router.huggingface.co/v1
AI_SWE_MODEL_NAME=Qwen/Qwen2.5-Coder-32B-Instruct:nscale
AI_SWE_REVIEWER_MODEL=Qwen/Qwen2.5-Coder-32B-Instruct:nscale
AI_SWE_REMOTE_MODEL_ROLES=["coder","reviewer"]
HF_TOKEN=PEGAR_TOKEN_PRIVADO_AQUI
```

Esto habilita llamadas de pago. Revisar tarifas y límites por ejecución antes
de activarlo, según `REAL-MODEL-VALIDATION.md`. El permiso de 3 USD fue para las
pruebas del proyecto, no un saldo ni un límite global automático del instalador.
Con `AI_SWE_REMOTE_MODEL_ROLES=[]` los roles remotos permanecen desactivados;
el respaldo local no inventa parches si falta el modelo del Coder.

## Datos y desinstalación

| Elemento | Ruta bajo `%LOCALAPPDATA%/AISWESystem` |
| --- | --- |
| Configuración privada | `config/.env` |
| SQLite | `data/state.sqlite3` |
| Logs rotados y redactados | `logs/` |
| Worktrees | `worktrees/` |
| Caché y pesos STT | `cache/` |

La aplicación escucha solo en loopback. La autenticación por claves es opcional;
no constituye un producto multiusuario. Más detalles en `INSTALLED-CONFIGURATION-WINDOWS.md`.

Para desinstalar, cerrar primero el servidor y usar Aplicaciones de Windows o
«Desinstalar» en su grupo de Menú Inicio. Se retiran archivos de programa, accesos
directos y registro propio del desinstalador. Se conservan configuración, SQLite,
logs, worktrees y caché del usuario; los repositorios externos no se eliminan.
Respaldar los datos antes de actualizar o trasladar el equipo. Este instalador
no implementa borrado/retención ni una migración de datos.

## Diagnóstico

Desde la carpeta portable, `runtime/python.exe -B start.py --runtime-info` informa installed
y presencia del frontend sin mostrar secretos. `--no-browser` permite iniciar
sin abrir una pestaña; se imprime la URL efectiva. En el portable se añade el
argumento después de `start.py`. Ante errores de configuración,
ejecutar desde terminal para leer el campo señalado y revisar el archivo externo.
Los logs están en el directorio del usuario. Conservarlos sin publicar tokens ni
contenido privado de los repositorios.


## Portable vigente rc12

Usa `dist/windows-v0.2.0-rc12-security/AISWESystem-windows-x64.zip`
y verifica SHA-256 `0b6c1e2d77eefa79c6d39f26f896a5989db03c13184aa044df62127a65e837cd`.
Cierra la instancia anterior, extrae la carpeta completa en un destino nuevo y
abre AISWESystem.cmd. Conserva runtime, app, packages y frontend juntos. No copies
ni borres los datos de LOCALAPPDATA para esta actualización; conserva respaldos.
Rc11 no recibe la corrección de entorno por actualizar sólo el código fuente.
Acta y límites: `RUNNER-ENVIRONMENT-HARDENING.md`. Validación en este host local,
no en otro equipo ni como servicio público.


## Portable vigente rc13

Usa `dist/windows-v0.2.0-rc13-output-limits/AISWESystem-windows-x64.zip`,
SHA-256 `865c67e27d45a1d7d93f7cf79cec1ca29ecf6e919febc6cc2327ffcff79e36ad`.
Cierra la instancia anterior, extrae la carpeta completa en un destino nuevo y
abre AISWESystem.cmd. No borres ni mezcles los datos de LOCALAPPDATA. Rc13 añade
la captura acotada del runner; rc12 y anteriores se conservan. Acta y límites:
`RUNNER-OUTPUT-BOUNDS.md`. Validación en el host local, no producción pública.


## Portable vigente rc14

Usa `dist/windows-v0.2.0-rc14-process-tree-final/AISWESystem-windows-x64.zip`,
SHA-256 `28d53cfdff4ff915f44261cdee61207e5f182f38c7cc11516d11f6923ec75feb`. Extrae el ZIP completo y abre `AISWESystem.cmd`.
Incluye CPython firmado; no necesita Python/Node de desarrollo. Smoke estándar
14/14 y 16 pruebas de runner desde la extracción aprobados en este host. Conserva
rc13 para retorno. El alias de Microsoft Store no se admite como intérprete del
runner de desarrollo. Alcance y límites: `RUNNER-WINDOWS-PROCESS-TREE.md`.


## Portable vigente rc15

Usa `dist/windows-v0.2.0-rc15-resource-limits/AISWESystem-windows-x64.zip`,
SHA-256 `d16dfd57986f1fd8618da99033b52efb68b6c104915138465f6b8df1cc31bc30`. Extrae todo el ZIP y abre `AISWESystem.cmd`.
Incluye las cuotas nativas de ejecución Windows y CPython firmado; no requiere
Python/Node de desarrollo. 33 pruebas sobre el ZIP y smoke 14/14 aprobados en este
host. Rc14 se conserva para retorno. Configuración avanzada y alcance de las cuotas:
`RUNNER-WINDOWS-RESOURCE-LIMITS.md`. No hay aislamiento fuerte de archivos/red.

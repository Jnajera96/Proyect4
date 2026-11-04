# Resultados del piloto de segunda PC — entorno limpio simulado

**Fecha real: 3 de noviembre de 2026 (America/Mexico_City).** Base del verificador: `5b71986`, rama `codex/day4-second-pc-pilot`, worktree `provider-preflight`.

## Dictamen

**Aprobado el arranque autónomo, perfiles, persistencia y reinicio de RC26 en una sesión con entorno saneado del mismo host.** Hay **6/6 controles del runtime, 14/14 del smoke portable y 12/12 pruebas unitarias** aprobados. Firmas Authenticode de `python.exe` y `pythonw.exe`: **Valid**, Python Software Foundation.

**El piloto físico en una segunda PC permanece pendiente.** Esta simulación no elimina DLLs, drivers ni políticas instaladas en el equipo de desarrollo y no acredita una VM independiente. No se certifica el recorrido completo de construcción en una máquina sin Git, ni transcripción offline sin pesos disponibles. El nombre del documento refleja el piloto objetivo; no afirma que se haya usado otro dispositivo.

Gasto **$0.00**; sin llamadas a modelos remotos, comandos de descarga, instalaciones, pushes ni cambios de protección de Windows. El verificador usa solo biblioteca estándar; los procesos de aplicación y las pruebas de Job usan el CPython del paquete mediante ruta absoluta. Se registran por separado el arranque de aplicación y la preparación del entorno.

## Artefacto y autonomía

Se auditó la extracción `dist/windows-v0.2.0-rc26/extracted/AISWESystem`. El verificador acepta una extracción, no procesa ZIP arbitrarios ni modifica el ZIP original. SHA-256 del manifiesto fijado: `74ed0c478889084899b2ac084c00eaac80453fcf161b7f72aa5789f134cdf754`. Se comprobaron **4862 archivos** y el inventario exacto antes y después; ambos resultados son idénticos. Carga útil inventariada: **362656933 bytes** sin contar el manifiesto ni sobrecarga del sistema de archivos. No se reconstruyó RC26 ni se incorporaron a él los cambios posteriores del core.

PATH del proceso objetivo: únicamente `%SYSTEMROOT%/System32`. `shutil.which('python')`, `shutil.which('node')` y `shutil.which('git')` devolvieron **None**. El intérprete ejecutado fue **CPython 3.13.14 AMD64** de `runtime/python.exe`, y ai_swe se importó desde `app/ai_swe` del paquete. No se emplearon aliases Microsoft Store ni intérpretes descubiertos en PATH como sustitutos del runtime.

El entorno se construye con lista blanca de variables del sistema; excluye credenciales, proxies, PYTHONPATH, configuración AI_SWE heredada y variables de entornos virtuales. Se asigna LOCALAPPDATA temporal y HF_HOME vacío con `HF_HUB_OFFLINE=1` y telemetría desactivada. No se usaron cuentas o bases de datos reales.

## Matriz de compatibilidad y requisitos

| Componente | Requisito / resultado |
| --- | --- |
| Windows 11 x64 | Validado en `Windows-11-10.0.26300-SP0` del host actual |
| Windows 10 x64 | Destino previsto; sin ejecución física verificada en esta sesión |
| x86 / ARM64 nativo | No certificados por este bundle AMD64 |
| Python y Node de desarrollo | No necesarios para el arranque probado; no descubiertos en PATH |
| Git | No incluido en RC26. Es necesario para repositorios/worktrees y el flujo de construcción; el arranque/perfiles no lo ejercita |
| Permisos | Escritura en LOCALAPPDATA y en carpeta temporal; APIs Job Object permitidas para los procesos propios |
| Disco | Al menos la carga inventariada (~346 MiB), más manifiesto, metadatos, datos/logs y modelos si se habilita voz real |
| RAM / CPU | CPU x64 compatible con los módulos nativos. Se confirmó soporte CPU int8 en este host; no se midió un mínimo de RAM universal |
| GPU / CUDA | No necesarios para la configuración CPU/int8 probada |
| Modelo de voz | Pesos y audio no incluidos en este ensayo. Para voz realmente offline deben transferirse/verificarse previamente por un canal autorizado |
| Modelos remotos | No configurados ni invocados; un perfil vacío inicia y señala que no tiene credencial |
| SAC / SmartScreen | No se desactivaron ni eludieron. El runtime firmado arrancó aquí; la política del equipo destino debe comprobarse allí |

Las firmas PSF no implican firma de todas las ruedas/DLLs de terceros ni aprobación por cualquier política WDAC de una organización. Los requisitos de Windows 10 son un objetivo de compatibilidad pendiente, no un pase deducido de Windows 11.

## Job Object y terminación de procesos

Se creó un Job Object con cuotas de procesos, memoria y CPU. El hijo se inició suspendido, se asignó al Job y después se reanudó. El nieto confirmó su propio arranque mediante escritura atómica de un marcador. **IsProcessInJob** confirmó la pertenencia explícita de ambos, y **QueryFullProcessImageNameW** confirmó que ambos ejecutaban el `python.exe` del bundle.

El grupo tenía **4 miembros activos**; no se presupuso que el conteo agregado fuera exactamente dos. `terminate_and_wait()` del producto congeló la creación de nuevos descendientes, terminó el Job y verificó todos sus miembros. Después: **cero miembros activos** y salida del hijo confirmada. Solo se manipularon handles del árbol sintético propio; no se terminaron procesos del usuario.

La bandera kill-on-close está configurada, pero no se ensayó una segunda terminación cerrando únicamente el handle. El comportamiento ejecutado y acreditado es la terminación en cascada mediante TerminateJobObject con espera/verificación. Un Job limita procesos y recursos; no es un contenedor, firewall ni aislamiento de acceso a archivos.

## Voz offline

PyAV **18.1.0**, ctranslate2 **4.8.2** y faster-whisper importaron desde el runtime del paquete. La factoría creó el adaptador real con **device=cpu / compute_type=int8** y se confirmó soporte int8 de la CPU. El modelo permaneció sin cargar (`_cargado is None`).

Esto acredita dependencias nativas y preparación lazy. No demuestra captura de micrófono, descarga/caché del modelo, exactitud de transcripción ni inferencia. La ausencia de pesos es una condición explícita, no un fallback silencioso a una transcripción falsa.

## Persistencia y ciclo de vida

La ruta canónica instalada es **`%LOCALAPPDATA%/AISWESystem`**, no `AI-SWE-System`. No se cambió para adaptar la prueba. En modo perfiles, cada usuario mantiene su propio `data/users/<uuid>/state.sqlite3` bajo esa raíz. El helper verifica las rutas reales y la integridad de SQLite.

Los 14 controles del smoke incluyen registro de perfil sintético con criptografía empaquetada, API privada cerrada antes de autenticar, interfaz integrada, perfil vacío sin token global, aceptación de una tarea determinista, puerta humana, cierre ordenado, login tras nuevo arranque y recuperación del run/checkpoint persistidos. Ambos procesos del servidor terminaron ordenadamente. No se aprobó una generación de código sin Git ni se reutilizó una sesión del usuario.

## Reproducción en el equipo destino

Copiar el ZIP RC26 verificado y extraerlo en una carpeta nueva. Copiar también `tools/verify_second_pc_pilot.py` y `tools/verify_portable_profiles.py` manteniendo una carpeta `tools/` externa al bundle. El verificador usa solo biblioteca estándar, por lo que puede invocarse con el Python embebido sin instalar Python de desarrollo:

```powershell
# Desde la carpeta que contiene AISWESystem/ y tools/
.\AISWESystem\runtime\python.exe -B tools/verify_second_pc_pilot.py .\AISWESystem
```

No mover los scripts dentro de AISWESystem: el manifiesto debe permanecer idéntico. La evidencia se escribe en `docs/SECOND-PC-PILOT-EVIDENCE.json` junto a tools; logs y datos sintéticos van a un temporal nuevo. Opcionalmente `--output <carpeta-nueva>` permite elegir evidencia cruda, siempre fuera del bundle. La prueba de perfiles tarda aproximadamente dos ciclos de 90 segundos más preparación/cierre; el supervisor del helper tiene plazo de 240 segundos. No requiere un repositorio Git para estos checks de arranque.

Para cerrar el piloto físico, registrar el equipo destino y versión de Windows, repetir los controles allí y adjuntar el JSON; probar micrófono e inferencia con pesos locales verificados y, por separado, resolver la disponibilidad de Git antes de construir un producto. El JSON conserva `physical_second_pc=false`: requiere acta del operador para acreditar que se usó otro dispositivo. No se interpretará automáticamente una segunda ejecución en el mismo host como segunda PC.

## Evidencias y pendientes

[SECOND-PC-PILOT-EVIDENCE.json](SECOND-PC-PILOT-EVIDENCE.json) contiene los 6 controles de runtime, 14 del smoke, firmas, rutas, versiones, hashes y límites. Los 12 tests unitarios comprueban eliminación de secretos/proxies, desaparición de herramientas falsas del host, rechazo de rutas inseguras/colisiones/corrupción/residuos y prohibición de escribir dentro del paquete histórico. Ruff aprobado.

Quedan pendientes el equipo físico independiente, Windows 10, voz con audio/pesos, flujo de construcción con Git y configuración de proveedor del usuario. No se ensayaron contenedores, red a nivel OS, una regresión completa backend/frontend ni compatibilidad de todas las políticas empresariales. La declaración de cero descargas describe las operaciones del verificador y el modo HF offline; no es una captura global del tráfico del host.

# Cierre del portable operativo — 30 de octubre de 2026

## Seguimiento rc5 — recuperar perfil sin registro previo

ZIP: `dist/windows-v0.2.0-operational-rc5/AISWESystem-windows-x64.zip`.
SHA-256: `d1247f75c2201cc997ec4a00a8dcecfe7b5272fad594c2cb782fa3b0f014729b`.
Tamaño: 118.794.712 bytes; manifiesto de 4.726 archivos, CRC del ZIP comprobado.
Base `33fc64c` más `ProfileRoot.tsx`/`RestaurarPerfil.tsx`: recuperar desde acceso.
Incluye el lanzador y decisiones postgeneración; rc4 y rc3 quedan intactos.

Validación fuente focalizada: 36 backend PASS, 32 frontend PASS y 5 controles
de navegador PASS; TypeScript/Vite y Ruff aprobados. No se declara una nueva
regresión completa. Acta: `PROFILE-IMPORT-UI-VALIDATION.md`.
Portable rc5 extraído: **14 controles PASS**, salida 0 y cero llamadas pagadas,
con PATH reducido, perfil aislado, dos arranques y SQLite íntegro/persistente.
La prueba HTTP nueva pasó también con CPython y módulos empaquetados del rc5.
Informe: `dist/windows-v0.2.0-operational-rc5/portable-profiles-report.json`.
El reporte del usuario de funcionamiento en otra PC se conserva con sus límites;
no sustituye el recorrido de recuperación por UI en destino ni acredita producción.

## Seguimiento rc4 — restauración desde la interfaz

Nueva entrega: `dist/windows-v0.2.0-operational-rc4/AISWESystem-windows-x64.zip`.
SHA-256: `512bd67c625fb004e6eddda07b746fe6db5ace2120984f8ee7537fa74b86ecec`.
Tamaño: 118.793.386 bytes; manifiesto con 4.726 archivos. Conserva rc3 intacto.
Base documental `3d20867` más la corrección de `VistaSesion.tsx` que conserva
Base64 estándar al subir respaldos. Backend sin cambios respecto a rc3.

El fallo fue reproducido antes de corregirlo. Tras la corrección: 4 controles
de navegador, 32 pruebas frontend y compilación TypeScript/Vite aprobados.
Además, 17 pruebas de continuidad/memoria pasan en desarrollo y otras 17 con
CPython y módulos del portable rc3, incluida recuperación simulada sin repetir
Coder/Runner/Reviewer. No se suman las repeticiones a la regresión de 973 casos.
Integridad CRC del ZIP rc4 y sus hashes comprobados tras extraerlo, así como
identidad del backend y presencia del frontend corregido.

Smoke sobre el ZIP rc4 extraído: **14 controles PASS**, salida 0, cero llamadas
pagadas. Registro, autenticación, API protegida, UI, puerta humana, reinicio y
persistencia SQLite aprobados con PATH reducido y LOCALAPPDATA temporal.
Informe: `dist/windows-v0.2.0-operational-rc4/portable-profiles-report.json`.

Acta: `CONTINUITY-FOLLOWUP-2026-10-30.md`. Guía para el hito que requiere otro
equipo: `PORTABLE-SECOND-PC-PILOT.md`. La recuperación completa por UI en otra
PC y la producción pública no se dan por cerradas.

## Entrega

Rama: `feature/v0.2.0-madre-continuity`.
Código empaquetado: `4703934f2a16072c2df0b9c0059fd3d79497056f`.
Se conserva rc2 y se construye un directorio rc3 nuevo.

- ZIP: `dist/windows-v0.2.0-operational-rc3/AISWESystem-windows-x64.zip`.
- SHA-256: `f3f5b06944e3551c4645c610bd7bde6c4add3a01051b13abbc5ebb1fa023304d`.
- Tamaño: 118.793.405 bytes.
- Manifiesto: `AISWESystem/BUNDLE-MANIFEST.json`, 4.726 archivos indexados.
- Inicio: extraer el ZIP y abrir `AISWESystem/AISWESystem.cmd`.

CPython 3.13.14 oficial, con firmas Authenticode válidas de Python Software
Foundation para `python.exe` y `pythonw.exe`. No se genera un ejecutable nuevo
sin firma. Las ruedas oficiales se conservan sin modificar; no se afirma que
todas sus DLL tengan firma Authenticode. No requiere Python ni Node de desarrollo
en destino. Git sigue siendo requisito para trabajar con repositorios.

## Verificación

`npm run build` terminó sin errores de TypeScript. El constructor compiló además
el frontend hacia una carpeta nueva. Un `_captura.html` residual de la salida de
desarrollo quedó excluido; no forma parte de la aplicación distribuida.

Se comprobó la integridad CRC del ZIP, se extrajo y se compararon sus 74 módulos
Python con el código fuente, además de los estáticos de la compilación nueva.
Los hashes del manifiesto corresponden a los archivos extraídos.

Regresión fuente ya cerrada, sin cambios de código posteriores: **973 PASS,
4 SKIP, 0 fallos**, informe `_tmp/nova-operational-full-final.xml`.
Frontend: **32 PASS**; verificaciones de navegador: **30 PASS**. Estos resultados
corresponden a la validación fuente documentada en
`NOVA-OPERATIONAL-VALIDATION.md`; no se presentan como una repetición completa
desde el ZIP. En este cierre se repitió la compilación y la verificación portable.

Comando del verificador sobre la extracción del ZIP:

```powershell
.venv/Scripts/python.exe tools/verify_portable_profiles.py _tmp/operational-rc3-zip-extracted/AISWESystem _tmp/operational-rc3-profiles
```

Resultado portable: **14 controles PASS**, salida 0, `success: true` y
`paid_calls: 0`. Se verificaron arranque con PATH limitado a System32,
LOCALAPPDATA temporal, registro y autenticación cifrada, API privada protegida,
UI integrada, ejecución determinista pausada ante la puerta humana, reinicio,
checkpoint y SQLite persistentes con `PRAGMA integrity_check = ok`.
El informe queda en `_tmp/operational-rc3-profiles/report.json` y su copia sin
datos de usuario en `dist/windows-v0.2.0-operational-rc3/portable-profiles-report.json`.
Evidencia de construcción y cotejo:
`build-report.json`, `artifact-report.json` y `source-verification.json` en el
directorio rc3. No compartir los directorios temporales de datos de prueba como
parte de la entrega.

## Capacidades incluidas

- Síntesis de requisitos para productos nuevos, con propuesta editable y
  confirmación humana obligatoria antes de construir.
- Preparación previa: Git, repositorio con HEAD, configuración de modelos y
  disponibilidad del ledger local. Inicialización explícita de commit base vacío.
- Recuperación de huecos SSE mediante estado autoritativo, sin repetir agentes.
- Cancelación cooperativa con recibo verificable y limpieza acotada del worktree;
  solo se liberan reservas demostrablemente no despachadas.
- UX de entrega, guía de ejecución, memoria asociativa y control horario de gasto
  incorporados al portable, conservando contratos y puertas humanas.

## Límites y siguiente paso

No hubo llamadas de inferencia pagadas ni publicaciones reales en GitHub. El
servidor abierto anteriormente y los datos del usuario no se reemplazaron.
La verificación local con PATH reducido y LOCALAPPDATA aislado no sustituye una
PC o VM independiente. Falta ese piloto y el cierre integral de continuidad y
recuperación entre equipos; no se declara aprobación de producción pública.

La preparación no comprueba saldo remoto ni permisos reales del token. La
cancelación no garantiza interrumpir una petición HTTP ya despachada ni detener
su facturación. Un worktree no proporciona aislamiento fuerte de procesos/red.

El host de compilación reportó Node 24.13.0 afectado por CVE-2026-111497; la
herramienta recomienda actualizar a 24.22.1 o posterior. Node no se incluye ni
se necesita para ejecutar este portable.

# Cierre del portable operativo — 30 de octubre de 2026

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

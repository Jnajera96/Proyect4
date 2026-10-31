# Restauración de perfil desde acceso — 30 de octubre de 2026

## Evidencia aportada por el usuario

El usuario informó: «ya lo probé en otra PC y funciona». Se registra como prueba
de uso reportada, no como una ejecución instrumental del agente. No se indicaron
versión/hash del portable, versión de Windows, política SAC ni recorrido exacto.
No se infiere que también haya probado recuperación, micrófono o promoción.

## Brecha e implementación

La API `/auth/import-vault` ya permitía recuperar un perfil sin registro previo,
pero la pantalla de acceso no exponía ese flujo. Se añadió «Restaurar desde un
respaldo», con archivo cifrado, contraseña del archivo, nombre de perfil nuevo,
contraseña nueva confirmada y ruta de repositorio autorizada.

El envío usa Base64 estándar. Un error del servidor se muestra y permite corregir
los datos; la UI bloquea envíos simultáneos y contraseñas distintas. Tras el éxito
se vacían los campos y se entra en el perfil recuperado, sin reanudar tareas. Se
recuerda revisar historial y generar una nueva clave de rescate. No se sobrescriben
perfiles existentes ni se cambia la criptografía o el contrato del endpoint.

La selección sencilla está acotada a respaldos de un solo repositorio. Respaldos
con varias rutas requieren todavía un asistente para asignarlas individualmente;
no se fuerza una misma carpeta ni se oculta el rechazo del backend.

## Validación

- **36 backend PASS**: perfiles, clave de rescate, continuidad/memoria e integración
  HTTP nueva; informe `_tmp/profile-restore-regression.xml`.
- Integración HTTP real en dos espacios temporales: exportar una ejecución pausada,
  rechazar contraseña incorrecta, importar sin registro, mantener ID/puerta/ruta
  reautorizada, cero llamadas a modelo, rechazar perfil ocupado y entrar tras reinicio.
- **5 controles de navegador PASS** con ProfileRoot real y API sintética:
  `_tmp/profile-restore-browser/report.json`, `tools/verify_profile_restore.cjs`.
  Acreditan formulario y transición de acceso, no descifrado del archivo de fixture.
- **32 frontend PASS**, TypeScript/Vite y Ruff de la prueba aprobados.
- Prueba de importación HTTP repetida con CPython y módulos de rc5: **1 PASS**,
  `_tmp/profile-import-rc5.xml`. Smoke sobre ZIP extraído: **14 controles PASS**,
  reinicio y SQLite aprobados, sin llamadas pagadas.
- Dos escenarios de prueba iniciales se corrigieron: INSPECT_ONLY no garantizaba
  una puerta pendiente y el fixture debía reconocer consultas con parámetros.
  Los resultados finales anteriores corresponden a las pruebas corregidas.

No se usaron perfiles, tokens ni repositorios reales del usuario. No hubo consumo
de inferencia ni publicación. La suite backend completa no se repitió: el backend
no cambió en esta entrega. Las suites focalizadas no se suman al conteo histórico.

## Entrega y pendientes

El rc5 incluye esta pantalla y el lanzador/decisiones de `33fc64c`; anteriores
ZIP conservados. Hash y comprobación portable en `OPERATIONAL-STATUS-2026-10-30.md`.
Falta el recorrido integral de recuperación por UI con archivo real en otra PC,
el asistente para múltiples repositorios y las verificaciones independientes de
publicación/contexto/aislamiento descritas en `ROADMAP.md`.

# Pausa segura — Fase I / preparación J

**Actualización 27/10/2026:** el usuario solicitó continuar. La pausa fue revocada,
el defecto de `/GROUP` se corrigió y la validación del instalador final pasó.
Consultar `INSTALLER-VALIDATION.md` y `RELEASE-MATRIX-v0.1.0.md` para el estado actual.
Lo que sigue conserva el checkpoint histórico de `bfc5273`, no una orden de pausa vigente.

Pausa solicitada por el usuario por límite de uso diario. No continuar hasta su
solicitud. Baseline validada de H: `75425fe`, rama `productization/v0.1.0`.

## Avance de esta sesión

- `packaging/installer.iss`: instalador completo onedir, `PrivilegesRequired=lowest`,
  instalación por usuario, accesos Menú Inicio/Escritorio y desinstalador sin reglas
  de borrado de datos en `%LOCALAPPDATA%/AISWESystem`.
- `tools/build_installer.py`: busca ISCC en PATH/rutas habituales o argumento explícito;
  valida el bundle y construye en directorio nuevo.
- Inno Setup no estaba instalado. Se descargó 6.7.3 de la publicación oficial,
  firma Authenticode **Valid**, editor Pyrsys B.V.; SHA256 del instalador del compilador:
  `9c73c3bae7ed48d44112a0f48e66742c00090bdb5bef71d9d3c056c66e97b732`.
  Se preparó por usuario, sin elevación/reinicio, en
  `_tmp/installer-toolchain/compiler/ISCC.exe` del checkout principal.
- Compilación correcta: `dist/windows-i-rc1/AISWESystem-v0.1.0-setup.exe`,
  81910935 bytes. SHA256:
  `5349b1cb284b630f0b1b6ff63e9fad194a7dcc3f59a0de4df063b61893c5dd01`.
  **Candidato no validado para entrega**. Conserva el EXE de H sin cambios.
- Cuatro pruebas unitarias nuevas pasaron. No se ejecutó una suite completa nueva.
- `tools/verify_installer.py`: arnés de instalación, API instalada, fixture HTTP
  determinista local, promoción real, reinicio y desinstalación; aún no pasó completo.

## Punto exacto de detención

La corrida `_tmp/installer-i-validation-01/report.json` pasó instalación silenciosa
por usuario y presencia del runtime completo; falló:
`Start Menu and Desktop shortcuts created`.

El log muestra que los accesos sí se crearon, pero Menú Inicio usó el grupo
predeterminado `AI Software Engineering System` en vez del grupo único solicitado
por el arnés con `/GROUP=AI-SWE-Installer-Test-...`. Escritorio usó la ruta habitual.
Revisar la interacción de `/GROUP` con `DisableProgramGroupPage=yes`; no dar por
corregido ni debilitar la comprobación. Antes de repetir, proteger también la ruta
real del grupo predeterminado contra cualquier acceso preexistente del usuario.

El cleanup ejecutó el desinstalador: exit 0, log `Removed all? Yes`, sin reinicio.
Se comprobó que EXE y `_internal` de esa instalación ya no existen.
No queda un proceso de la prueba I activo. No hubo inferencia remota de pago.

## Pendientes al retomar

1. Corregir el conflicto de grupo/expectativas, mantener validación real de accesos
   y verificar su retirada al desinstalar.
2. Resolver cuatro avisos Ruff: mayúsculas en PROGRAMFILES/PROGRAMFILES(X86) y
   dos líneas largas en verify_installer.py. No estaban corregidos al pausar.
3. Repetir en destino nuevo el recorrido completo del EXE instalado: prueba que
   falla antes, requisitos → worktree/tests → revisión → reinicio en puerta de
   aprobación → aprobación explícita → promoción de bytes revisados; preservar
   pruebas/HEAD y validar SQLite persistente.
4. Verificar desinstalación, registro HKCU/accesos retirados y todos los datos de
   usuario preservados byte por byte; ejecutar pruebas completas pertinentes.
5. Es un destino/perfil/PATH aislado **en este host**, no una VM independiente.
   WindowsSandbox.exe no está presente. No declarar Windows limpio validado.
6. Solo si I pasa: redactar INSTALLATION-WINDOWS.md, PRODUCT-v0.1.0.md,
   KNOWN-LIMITATIONS-v0.1.0.md y matriz de J. **No crear todavía el tag v0.1.0.**

Trabajo aislado en `C:/Users/jose_/.codex/worktrees/provider-preflight/proyecto4-ai-swe`.
Sus cambios se guardan como checkpoint local, sin push. Documentos académicos
preexistentes del checkout principal permanecen intactos. Logs y artefactos están
en el checkout principal, no en el worktree. No borrar/restaurar los cambios del usuario.

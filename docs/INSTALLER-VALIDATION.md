# Fase I — instalación y desinstalación verificadas

Fecha: 27 de octubre de 2026. Baseline de reanudación: `bfc5273`.

## Alcance y resultado

I pasa en el alcance solicitado: destino de instalación aislado, LOCALAPPDATA
temporal, cuenta no elevada y PATH limitado a Windows/Git en el host de desarrollo.
**No es una VM independiente ni acredita Windows recién instalado.** No se
habilitaron características del sistema, servicios o reinicios para simularlo.

El compilador Inno Setup 6.7.3 se encontró en el directorio de herramientas preparado
en H/I; su instalador oficial había verificado Authenticode válido de Pyrsys B.V.
`tools/build_installer.py` admite ISCC explícito y busca también PATH/rutas estándar.

## Defecto reproducido y corrección

La corrida 01 creó accesos pero ignoró el grupo único `/GROUP` del arnés.
La documentación oficial confirma que `DisableProgramGroupPage=yes` ignora ese
parámetro. Se cambió a `no`, conservando el grupo predeterminado para uso normal.
También se protege el grupo predeterminado contra accesos preexistentes al probar.
No se eliminó ni relajó la aserción de accesos reales. Se resolvieron los cuatro
avisos de Ruff del checkpoint y se añadió la regresión de selección de grupo.

Fuentes: [DisableProgramGroupPage](https://jrsoftware.org/ishelp/topic_setup_disableprogramgrouppage.htm),
[parámetro GROUP](https://jrsoftware.org/ishelp/topic_setupcmdline.htm).

La corrida corregida 02 pasó. Después se alinearon versiones de API/frontend a
0.1.0 y se reconstruyeron EXE e instalador; la validación final volvió a pasar sobre
esos nuevos archivos. Las corridas anteriores se conservan como evidencia histórica.

## Prueba final reproducible

```powershell
.venv\Scripts\python.exe tools/build_installer.py --iscc <ruta-ISCC.exe> --bundle <carpeta-AISWESystem> --output <directorio-nuevo>
.venv\Scripts\python.exe tools/verify_installer.py <instalador.exe> <directorio-nuevo-de-prueba>
```

El arnés no depende de credenciales privadas. Usa un servidor HTTP local que da
propuestas deterministas exclusivamente para Coder/Reviewer. El EXE instalado usa
el gateway, API, grafo, políticas, worktree, pruebas y promotor reales. No se
inyectan estados, se modifican puertas ni se suplanta la promoción.
Las aprobaciones del arnés son decisiones explícitas de un escenario autorizado
sobre un repositorio descartable; no aprobación automática en repositorios reales.

La corrida final `_tmp/installer-release-validation-01/report.json` pasó 23 controles:

- Instalación sin elevación, copia de `_internal`, accesos Inicio/Escritorio y HKCU.
- La prueba funcional falla antes del cambio; el EXE/API/frontend arrancan y la API
  informa versión 0.1.0.
- Confirmación de requisitos y revisión conservan limpio el repositorio original.
- Las pruebas del worktree pasan con el trabajador empaquetado.
- Cierre y reinicio conservan SQLite, proyecto y checkpoint en `awaiting_approval`.
- Solo la aprobación posterior promueve exactamente los bytes revisados.
- Pruebas protegidas y HEAD originales intactos; solo `src/app.py` cambia.
- Informe final sin fallo de promoción; fixture llamado solo por Coder/Reviewer.
- Cierre, desinstalación exitosa y retirada de programa, `_internal`, accesos y HKCU.
- Todos los archivos del perfil de datos conservados byte por byte, incluidos
  `config/.env`, `data/state.sqlite3` y `logs/application.log`.

El EXE instalado coincide con el del paquete final:
`0137089dc1080590df3edbf35d509b370c2f81162e4932addc1a3482fbefec57`.
Instalador:
`1bd312a8e019773480389d95e6f7f375ae2f2d6b919774adde1967a7b22384ea`.
No hubo llamadas de pago ni renovación del presupuesto autorizado.

## Evidencia y pendientes reales

Evidencia consolidada final: `RELEASE-EVIDENCE-v0.1.0.json`. Datos de compilación:
`dist/windows-v0.1.0-rc1/installer-build.json`. Logs/corridas locales bajo `_tmp/`.
El software de prueba quedó desinstalado; sus datos temporales se conservan como
evidencia, no se confunden con datos de usuario reales.

La retirada y conservación anteriores no demuestran una actualización de versiones,
migración de datos, recuperación de cortes, firma de código, políticas de otro
equipo o compatibilidad con todos los Windows. WindowsSandbox.exe sigue ausente.
La matriz final muestra esas omisiones; I no se rotula como prueba en máquina limpia.

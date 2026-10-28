# Punto seguro de reanudación — 28 de octubre de 2026

Trabajo pausado a petición del usuario para trasladarse. Rama: `feature/v0.2.0-madre-continuity`. Base anterior: `2a666dffb43e431c9ed0ac2975bb4b275b40d003`. El commit que contiene este documento es el checkpoint; no es una release validada.

## Guardado

- Creación explícita de «Nuevo proyecto Git» en API/UI, consentimiento `create_if_missing` booleano estricto, README y primer commit en destino nuevo/vacío. Git debe estar instalado y el directorio padre debe existir. Se preserva el registro de repositorios existentes.
- Validación previa de rutas privadas, symlinks/reparse points, componentes `.git` y alias Windows con puntos/espacios, ADS y rutas ambiguas. Sin cambios en configuración global de Git, hooks, remotos o secretos.
- Researcher reconoce archivos web/SQL. Prompts orientados a proyectos autocontenidos con HTML/CSS/JavaScript, servidor Python estándar y JSON/SQLite, sin npm ni descargas.
- Al recortar propuestas se conservan primero las pruebas. Una propuesta recortada se detiene con `SCOPE_TRIMMED` y requiere intervención humana: no se promociona una implementación incompleta por tener pruebas verdes.
- Reviewer vuelve a poder rechazar defectos concretos aunque las pruebas pasen. Se restaura estimación conservadora del presupuesto y se rechazan reservas artificialmente reducidas en el verificador E2E.

## Evidencia disponible

- Coder/Reviewer existentes: 59 pruebas PASS. Nuevas pruebas de builder: 9 PASS, con calendario y calorías atravesando grafo, sandbox, pytest y Ruff reales, puertas humanas y promoción.
- Las respuestas de modelos en esos dos proyectos son fixtures `FakeModelAdapter`: prueban integración, no calidad de generación remota ni disponibilidad del proveedor.
- Navegador sobre fixtures con backend Python: navegación de meses, CRUD y persistencia JSON del calendario; CRUD, cálculos y persistencia SQLite de calorías. Totales comprobados: 299, 234, 130 y 0.
- Bootstrap: suite focalizada de API/proyectos aprobada; un caso de symlink real omitido por privilegios Windows, con cobertura determinista de reparse points. Endurecimiento final de rutas: 7 casos PASS. Frontend: 32 PASS y build aprobado; fixture Chromium de creación: 6 comprobaciones PASS.
- Presupuesto/gateway/perfiles: 22 PASS. Ruff focalizado aprobado. `git diff --check` aprobado. El archivo grande `nodes.py` conserva deuda de lint previa.
- Informes de implementación y evidencia resumida preservados en `docs/evidence/project-builder-checkpoint/`. Artefactos voluminosos y capturas adicionales permanecen en `_tmp/`, ignorado por Git.

## Pendiente al retomar, en este orden

1. Revisión final independiente del endurecimiento de alias Windows; la corrección y sus pruebas están guardadas, pero no se completó su segunda revisión.
2. Ejecutar una suite Python integrada sobre el checkpoint final, registrar resultados y resolver únicamente regresiones verificadas. Aún no se ejecutó la suite completa final.
3. Sincronizar el worktree `C:/Users/jose_/.codex/worktrees/provider-preflight/proyecto4-ai-swe`, comprobado limpio y en la base anterior al pausar. Está pendiente; no asumir que contiene este checkpoint.
4. Construir un NUEVO portable con Python firmado, comprobar arranque aislado, perfiles, creación de proyecto, manifiesto y ZIP. El ZIP anterior de calculadora NO incluye estos cambios.
5. Actualizar el acta de validación y la matriz del producto. No declarar producción ni generación universal a partir de fixtures.

## Restricciones conservadas

No se realizaron nuevas llamadas pagadas. El ledger existente reserva `2.99999104 USD` de los `3 USD` autorizados; no renovar ni modificar esa autorización. No ejecutar `--run-real` con el saldo actual. No incluir tokens, bóvedas, bases de datos de usuarios o `.env` en commits/paquetes.

Se conserva `v0.1.0` y su portable canónico `dist/windows-signed-python-rc2/AISWESystem-signed-python-rc2.zip`. Sin push, tags nuevos, cambios de políticas Windows ni instalaciones de dependencias en esta fase. Continúan pendientes los problemas conocidos de continuidad/importación/auto-respaldo de v0.2.0; este checkpoint no los resuelve.

Para reanudar: «Lee docs/RESUME-PROJECT-BUILDER-2026-10-28.md, verifica Git y continúa desde los pendientes, sin llamadas pagadas».

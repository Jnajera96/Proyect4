# Punto seguro de reanudación — 29 de octubre de 2026

**Actualización del 30 de octubre:** trabajo retomado. El formulario oculto por CSS
se corrigió y el navegador pasa 10 comprobaciones. Regresión completa: 926 PASS y
4 SKIP; verificación final focalizada: 19 PASS; frontend 32 PASS y build aprobado.
El estado vigente y los límites están en `INTUITIVE-UX-NEUROMAPA-VALIDATION.md`.
Las notas siguientes preservan el estado histórico de la pausa.

Pausa solicitada por el usuario para trasladarse. Rama: `feature/v0.2.0-madre-continuity`; base: `ab079d3`. Este punto conserva implementación en progreso, no constituye una release validada. No se realizaron llamadas de pago ni publicaciones GitHub.

## Cambios conservados

- Interfaz con capitalización tipo oración, selector local/GitHub y detalles técnicos desplegables.
- Guía posterior a promoción: GET de consulta, POST protegido para preparar `iniciar.bat`, lanzamiento explícito; detección estática de HTML, CLI y FastAPI. No sobrescribe un lanzador ajeno.
- Asistente de primera publicación GitHub, privado por defecto, confirmación explícita, PAT temporal y selección de archivos aprobados. Pruebas con transporte simulado; ninguna publicación real.
- Memoria asociativa SQLite por propietario/repositorio, observaciones idempotentes y selección de archivos relevantes para Researcher/Coder.
- Límite horario con ventana móvil y reservas conservadoras en el ledger de perfiles. Una reserva desconocida no se libera silenciosamente.
- Nuevas pruebas y verificador de navegador aislado en `tools/verify_intuitive_delivery.cjs`.

## Evidencia y estado de validación

- Pruebas focalizadas de compatibilidad: 103 PASS (`_tmp/intuitive-compatibility.xml`).
- Pruebas nuevas/contratos: 40 PASS (`_tmp/intuitive-new-tests.xml`), anteriores a la última prueba añadida al límite horario.
- Frontend: 32 pruebas y build pasaron antes de los últimos ajustes menores de CSS/etiquetas.
- Primera suite completa detectó dos defectos: serialización de `delivery_mode` e importación HTTP fuera de la capa de proveedores. Ambos fueron corregidos y sus verificaciones focalizadas pasaron. Falta repetir la suite completa limpia.
- El verificador de navegador pasó inicialmente 8 comprobaciones. La última repetición, tras añadir CSS real y una comprobación adicional, dejó `success: false` y solo una comprobación completada en `_tmp/intuitive-browser/report.json`. Investigar antes de declarar la UI validada; no ocultar este fallo.
- `git diff --check` sin errores de whitespace; advertencias únicamente de normalización CRLF/LF.
- Las suites existentes no se modificaron. Los informes `_tmp` son evidencia local ignorada por Git.

## Orden para retomar

1. Leer este documento y `docs/superpowers/plans/2026-10-29-intuitive-ux-neuromapa.md`; verificar rama, HEAD y árbol antes de editar.
2. Diagnosticar el fallo del verificador de navegador y revisar el último test `test_hourly_limit_stops_gateway_before_fake_adapter`.
3. Ejecutar Ruff sobre módulos/pruebas nuevas; verificar límites, contratos y seguridad de lanzamiento/publicación.
4. Añadir o completar E2E offline del flujo promovido hacia la guía de ejecución usando FakeModelAdapter y repositorio descartable.
5. Repetir suite backend completa, 32 pruebas frontend, build TypeScript/Vite y verificador de navegador. No realizar inferencia de pago.
6. Completar informe técnico, referencias y progreso; solo entonces preparar entrega validada.

## Límites que deben quedar explícitos

- La reducción 50–70% de tokens es una meta, no un resultado demostrado. Una selección sintética 24→8 reduce archivos 66,7%; no prueba ahorro equivalente en tokens o dinero.
- El freno horario usa la reserva restante completa de una ejecución; puede detener antes de llamar al modelo. Revisar alcance en gateways antiguos sin ledger de perfiles.
- La publicación implementada es primera publicación de proyecto nuevo; no sincronización general de repositorios con remotos/historia previa.
- FastAPI utiliza puerto 8765; revisar colisiones y mensajes antes de cerrar entrega.
- El worktree no es aislamiento fuerte de procesos/red.
- No se construyó un nuevo ZIP portable ni se actualizó el servidor que ya estaba abierto en puerto 8000. No confundir fuente modificada con aplicación instalada actualizada.

## Referencia Neuromapa

Patrones consultados, sin copiar ni ejecutar código: [repositorio Neuromapa](https://github.com/lumiel777/neuromapa), [memoria asociativa](https://raw.githubusercontent.com/lumiel777/neuromapa/main/aprender.py), [freno](https://raw.githubusercontent.com/lumiel777/neuromapa/main/hook_freno.py) y [licencia MIT](https://raw.githubusercontent.com/lumiel777/neuromapa/main/LICENSE). Sus mediciones propias no demuestran una reducción general de 50–70% para este proyecto.

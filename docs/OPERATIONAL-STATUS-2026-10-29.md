# Estado y punto seguro — 29 de octubre de 2026

## Resultado comprobado

El flujo central completó la prueba real `run-b70e76e5abd6`: estado `completed`,
sin errores, dos llamadas remotas, pytest y Ruff aprobados, Reviewer `accept`,
aprobación y promoción de dos archivos. Solo se usó el repositorio descartable
`_tmp/ui-calculator-e2e-20261029-01`. README quedó intacto. Los 29 casos numéricos
independientes pasaron antes y después de promover. No se modificó el repositorio
real del usuario. Promover aplica archivos; no crea un commit en ese repositorio.

Configuración que funcionó en el perfil `jose`:

- Coder: `Qwen/Qwen2.5-Coder-32B-Instruct:nscale`.
- Reviewer: `openai/gpt-oss-120b:nscale`.
- Analyst/Supervisor/Researcher: deterministas locales.
- Máximo por ejecución: 0,10 USD; límite acumulado del perfil: 2 USD.
- Coste declarado del E2E exitoso: 0,00096118 USD, no factura conciliada con HF.

Qwen2.5-Coder y Qwen3-235B como Reviewer produjeron objeciones falsas sobre
normalización de ángulos y pruebas presentes. No se forzó aceptación; se probó
un modelo de otra familia para revisión. El ejemplo aprobado no garantiza calidad
para cualquier proyecto ni certifica todos los modelos del catálogo.

## Correcciones y verificación

Guardar la bóveda conserva proyecto/borrador sin desmontar App; el encabezado
reconoce el perfil autenticado. Por defecto se ejecutan pytest local completo y
Ruff. `pytest.integration` sigue disponible explícitamente y su ausencia no se
convierte en PASS. Coder recibe los objetivos reales de verificación.

La normalización I001 con Ruff opera en memoria sobre la propuesta, sin ejecutar
código generado ni escribir archivos. Registra hashes antes/después en un evento
tipado. El diff se deriva del resultado; patcher, revisión y aprobación mantienen
sus controles. Los errores funcionales siguen fallando. Contrato frontend regenerado.

- Suite final: **909 PASS, 4 SKIP, 0 FAIL**, `_tmp/operational-full-verified.xml`.
- 32 pruebas de estados frontend; TypeScript/Vite correctos.
- Navegador: 5 controles de continuidad y 9 de interacción aprobados.
- rc1: 18 controles de paquete y 14 de perfiles/reinicio/SQLite aprobados.
- rc2: todos los hashes del manifiesto y normalizador empaquetado comprobados;
  UI, Coder, pytest, Ruff, Reviewer y promoción reales ejecutados desde rc2.
- Un fallo intermedio por esquema exportado obsoleto se corrigió regenerándolo;
  después pasó la suite completa. No se oculta ese fallo intermedio.

## Entrega y reanudación

ZIP: `dist/windows-v0.2.0-operational-rc2/AISWESystem-windows-x64.zip`.
SHA256: `b7c6895de40e879b377d4b8852178e437b01094b41d14ae348220d9d8b697e94`.
4719 archivos, sin tokens, bóvedas, bases de datos, logs ni pesos de modelos.
Extraer y ejecutar `AISWESystem/AISWESystem.cmd`. Git sigue siendo dependencia;
no hace falta Python/Node de desarrollo.

Servidor de esta sesión: PID 28032, `http://127.0.0.1:8000/app/`, desde rc2.
El PID puede cambiar al reiniciar. Logs: `_tmp/operational-live-rc2/`.
Se puede cerrar el equipo: SQLite y bóveda están guardados. Al volver, ejecutar
el CMD e iniciar sesión. No hay llamada del E2E pendiente. No se creó tag ni push;
las entregas anteriores y v0.1.0 se conservaron.

Evidencia local: `_tmp/operational-gptoss-final.json`,
`_tmp/scientific-oracle-gptoss.json`, `_tmp/scientific-oracle-promoted.json`,
`_tmp/operational-promotion-completed.png`. No publicar bases de datos ni bóvedas.

Presupuesto del laboratorio: máximo acumulado **5 USD**; reserva conservadora
preservada **4,99999104 USD**. Los intentos adicionales se acotaron dentro del
mismo bloque de 1 USD, sin aumentar esa reserva. Consumo declarado de las cinco
corridas con respuesta de hoy: **0,01131482 USD**. La reserva de 1 USD del HTTP 401
anterior permanece por consumo incierto. Reservado no equivale a facturado.

## Avance hacia v0.2.0 portable y recuperable

**75/100**, estimación técnica ponderada (74,75 redondeado), no métrica automática.
La meta incluye uso local confiable y continuidad en otro equipo; no equivale a
una plataforma pública de producción.

| Objetivo | Peso | Avance | Para llegar a 100 |
|---|---:|---:|---|
| Perfiles y bóveda | 15% | 95 | Recuperación/actualización en otro equipo |
| Agentes y promoción | 30% | 85 | Otros proyectos reales y evaluación de falsos veredictos |
| UI, actividad y proyectos | 10% | 90 | Comprobación previa y mensajes accionables completos |
| Voz | 5% | 90 | Micrófono/audio en el equipo de destino |
| Memoria, modos y rollback | 10% | 80 | Validación integral independiente de recuperación |
| Continuidad y respaldo | 15% | 45 | Importación UI, auto-backup y recuperación post-promoción |
| Distribución y operación segura | 15% | 45 | Otra PC/VM, actualizaciones y aislamiento de procesos |

## Fallas y límites pendientes

1. Calidad variable de modelos: pueden generar código incorrecto o rechazar código
   correcto. Preferir la combinación validada; no hay diez modelos certificados.
2. Falta comprobación previa completa de repositorio, credenciales y saldo con
   acciones guiadas. Un token presente no acredita permisos ni saldo real.
3. Continuidad: auto-backup productivo, importación UI, recuperación post-promoción,
   reserva de nombre huérfana y validación de archivos/esquemas siguen pendientes,
   según `ANTIGRAVITY-v0.2.0-AUDIT.md`. No se cerraron hoy.
4. Worktree no aísla procesos/red. Las pruebas ejecutan código en el host: no hay
   acreditación para exposición pública ni producción segura.
5. Este ZIP no se probó en otra PC/VM. No se certifican todas las políticas SAC,
   actualización/migración o cancelación fuerte.
6. El catálogo fechado el 27 de octubre aún no refleja el éxito por rol de GPT OSS
   de hoy. Las tarifas declaradas no sustituyen conciliación de facturación.

Siguiente ruta: comprobación previa; calendario/calorías reales dentro del saldo
conciliado; cerrar continuidad; validar otra PC; fortalecer aislamiento antes de
producción. Nova permanece como referencia de patrones, sin migración ni copia de módulos.

# Cuotas del ejecutor en Windows

Fecha: 31 de octubre de 2026. Base: `d790f9c`. Incremento offline, sin inferencias
pagadas. Recuperación entre PC y publicación real GitHub continúan en pausa.

## Comportamiento

Cada objetivo de pruebas crea un Job Object con límites antes de asignar y
reanudar el proceso suspendido:

| Recurso | Valor predeterminado | Alcance |
| --- | ---: | --- |
| Procesos activos | 16 | Total simultáneo asociado al grupo; incluye el proceso inicial. |
| Memoria comprometida | 1.024 MiB | Total del grupo, no sólo un hijo. Windows rechaza compromisos adicionales sobre el límite. |
| CPU en modo usuario | 600 segundos | Tiempo acumulado de los procesos del grupo; Windows termina el grupo al excederlo. |

El timeout de pared existente sigue siendo independiente. Estas cuotas se renuevan
por objetivo y por intento; no constituyen un presupuesto agregado de toda la
ejecución del grafo. CPU no significa porcentaje de uso ni tiempo de kernel; memoria
comprometida no significa RSS total del host, caché de archivos o memoria de brokers
externos. No se declara aislamiento de archivos ni red.

## Configuración y cableado

Settings expone `runner_limits`, validado por un modelo Pydantic inmutable. Valores
enteros estrictos: procesos 1–128, memoria 64–8.192 MiB y CPU 1–3.600 segundos. Se
rechazan booleanos, infinito, cero y campos desconocidos. No existe un valor cero
que desactive silenciosamente una protección. Ejemplo documentado en `.env.example`:

```dotenv
AI_SWE_RUNNER_LIMITS={"max_processes":16,"memory_mb":1024,"cpu_seconds":600}
```

No se modificó el `.env` privado. El nodo de pruebas toma la configuración de su
contexto de perfil y la pasa explícitamente al runner. Las instrucciones del modelo
y RunOptions no cambian estas cuotas. La prueba de perfiles conserva sus
comprobaciones de rutas/objetivos y verifica además que cada perfil recibe su cuota.
Los dos dobles de continuidad se adaptan al nuevo argumento sin retirar afirmaciones.

El código nativo usa JOB_OBJECT_LIMIT_ACTIVE_PROCESS, JOB_OBJECT_LIMIT_JOB_MEMORY
y JOB_OBJECT_LIMIT_JOB_TIME, conservando KILL_ON_JOB_CLOSE y sin breakaway. Al cerrar
el grupo se reduce la posibilidad de crear nuevos hijos y se preservan la memoria
y el reloj de CPU mediante JOB_OBJECT_LIMIT_PRESERVE_JOB_TIME: no se reinicia el
presupuesto durante la limpieza. Un error de preparación produce RunnerError; no
hay fallback a ejecución sin cuotas en Windows.

Se conserva el estado real del proceso. En este host el límite de CPU devolvió
`0xC0000044` (STATUS_QUOTA_EXCEEDED), no el código Win32 1816 esperado inicialmente.
Ambas representaciones reciben un mensaje de cuota insuficiente, sin inventar
que una salida cero prueba ausencia de intentos denegados. Un programa puede
manejar legítimamente MemoryError o un rechazo de creación y terminar bien.

La aplicación de estas cuotas es Windows. POSIX conserva el runner anterior; si
un llamador solicita explícitamente cuotas Job Object fuera de Windows, se rechaza.
No se incorporan dependencias nuevas, instalaciones globales ni ejecutables generados.

## Pruebas y calibración

- Antes del cambio, el test consultó la configuración real del Job Object y falló:
  no había límite de procesos (`0`, frente al límite requerido). Evidencia:
  `_tmp/resource-before.xml`.
- Memoria: la misma reserva sintética de 128 MiB falla con cuota de 64 MiB
  (MemoryError) y pasa con 256 MiB; no se intenta agotar la RAM del host.
- Procesos: crear un hijo falla con máximo 1 y funciona con máximo 2, esperando
  su cierre antes de terminar el padre.
- CPU: un bucle sintético termina por la cuota de un segundo antes del timeout
  de pared de diez segundos. No es una medición de facturación ni de tokens.
- Configuración inválida, lectura de Settings, preservación de cuotas al cerrar
  y los siete casos de ciclo de vida de procesos permanecen cubiertos.
- ZIP extraído: **33 PASS**, `_tmp/resource-rc15-tests.xml`; runtime y módulos
  embebidos de rc15, sin cargar src de desarrollo.
- Frontend: **39 PASS** y TypeScript/Vite aprobado; no hay cambios de interfaz.
- Ruff de runner, módulo nativo, Settings y pruebas nuevas/de perfiles: aprobado.
  En nodes y las pruebas de continuidad se mantienen 22, 10 y 2 avisos previos,
  respectivamente, sin avisos nuevos (`_tmp/check-resource-lint.py`).
- La corrida focalizada ampliada del puente restringido quedó sin terminar y se
  interrumpió tras verificar su identidad. No se cuenta como un PASS. Se usa la
  regresión completa fuera de ese puente para las pruebas que requieren entorno local.

La calibración inicial falló únicamente por esperar el código Win32 en lugar del
NTSTATUS observado (`_tmp/resource-first.xml`); se conserva como evidencia fallida.
Los resultados finales de regresión, smoke y paquete se registran al cerrar abajo.

## Referencias primarias y límites pendientes

[Límites básicos del Job Object](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information),
[memoria comprometida del grupo](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information)
y [valores NTSTATUS](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-erref/596a1078-e883-4972-9bbc-49e60bebca55).

Siguen pendientes aislamiento real de archivos/red, defensa contra procesos
creados mediante brokers externos, validación en Windows independiente y pilotos
de producto/continuidad. No se equipara este control de recursos a una VM o un
contenedor seguro ni a aprobación de producción pública. Rc14 se conserva para
retorno; sólo se cambia la entrega canónica si las verificaciones finales aprueban.

Regresión completa: 1.095 PASS / 4 SKIP, cero fallos/errores, 586.742 s;
`_tmp/resource-full.xml`, salida de pytest 0 (`_tmp/resource-full-result.json`).
Smoke: `_tmp/resource-rc15-smoke/report.json`, 14/14, ambos cierres código 0.
ZIP: 121.290.582 bytes, 4.736 hashes, firmas válidas Python Software Foundation.


## Rc15 — cuotas nativas del ejecutor Windows

Se aplican por objetivo 16 procesos, 1.024 MiB de memoria comprometida y 600 s de
CPU de usuario acumulada, configurables con `AI_SWE_RUNNER_LIMITS`. La limpieza
preserva el reloj de CPU y las cuotas de memoria; no hay fallback sin cuotas en
Windows. No se modifica el `.env` privado ni se añaden dependencias.

1.095 backend PASS / 4 SKIP, 39 frontend PASS y build aprobado, 33 pruebas desde
el ZIP y 14/14 controles del smoke estándar. Cero llamadas pagadas.
Entrega local: `dist/windows-v0.2.0-rc15-resource-limits/AISWESystem-windows-x64.zip`.
SHA-256: `d16dfd57986f1fd8618da99033b52efb68b6c104915138465f6b8df1cc31bc30`.
Acta: `RUNNER-WINDOWS-RESOURCE-LIMITS.md`. Rc14 y anteriores se conservan.
Avance estimado: 85/100 (84,65 ponderado; operación segura 75→80). Siguen pendientes
aislamiento de archivos/red, calidad/ahorro con modelos y matriz Windows independiente.
Los pilotos de recuperación entre PC y publicación real GitHub continúan pausados.

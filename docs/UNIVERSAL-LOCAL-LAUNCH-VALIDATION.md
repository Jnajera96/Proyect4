# Prueba local y decisión posterior — 30 de octubre de 2026

Base: `d2e9aee`, rama `feature/v0.2.0-madre-continuity`.

## Comportamiento implementado

Después de una promoción verificada se muestra una ficha global, también visible
en la vista de flujo, con dos secciones: «Probar en local» y «Decisión después de
probar». La apertura es explícita; no se ejecuta código al descubrir la aplicación.

- HTML: abre el navegador.
- Python CLI y FastAPI: ejecutan en consola independiente de Windows.
- Biblioteca Python: abre una consola interactiva con sus funciones cargadas.
  Nombres de archivo no importables como módulos usan `runpy` en esa consola.
- Otros archivos promovidos válidos: hay un iniciador para abrir la carpeta, con
  aviso de que no se detectó un punto de entrada compatible. No se afirma que un
  formato desconocido pueda ejecutarse automáticamente.

Todos los BAT nuevos usan UTF-8 sin BOM, página de códigos 65001 y pausa final.
Se conservan las comprobaciones de promoción, hashes y rutas, y no se reemplaza
un `iniciar.bat` existente no coincidente. Los errores se muestran sin ocultar
la guía ya obtenida. GET continúa siendo de solo lectura; preparar y lanzar usan
las mutaciones autorizadas existentes.

El prompt del Coder exige un punto de entrada humano (HTML o `__main__` con
ejemplos/menú), manteniendo el alcance confirmado y sin interacción al importar.

«Modificar o pedir cambios» vuelve a la vista general que contiene el compositor,
selecciona el proyecto de la ejecución y enfoca la instrucción, sin enviar otra
tarea. «Subir a GitHub» abre el asistente existente; no publica automáticamente.
Si el proyecto ya no está registrado, ambas acciones se deshabilitan y se explica
qué falta. Las decisiones no se bloquean artificialmente hasta pulsar el lanzador:
abrir una ventana no demuestra que la persona haya terminado de probar.

## Evidencia offline

- 49 pruebas backend PASS: `test_launch_guide.py`, `test_delivery_pipeline.py` y
  `test_product_requirements.py`; `_tmp/universal-launch-delivery.xml`.
- Incluye ejecución real del BAT interactivo con bibliotecas sintéticas en Windows,
  archivos `calculator.py`, `math-tools.py` y `class.py`, y llamada de una función.
- 32 pruebas frontend PASS; TypeScript/Vite aprobado.
- 12 controles de navegador PASS con App real y API de fixture:
  `tools/verify_intuitive_delivery.cjs`, `_tmp/intuitive-browser/report.json`.
  Verifica apertura explícita, retorno desde flujo con proyecto/foco, ausencia de
  ejecución automática y modal de publicación con errores/éxito simulados.
- Ruff del lanzador y sus pruebas aprobado; `git diff --check` sin errores.

No hubo inferencias pagadas ni publicación real. La regresión backend completa
previa de 973 casos no se repitió ni se presenta como resultado de esta mejora.
Este cierre actualiza fuente y compilación; el ZIP rc4 anterior permanece intacto
y no contiene estos cambios. Falta incorporarlos al siguiente portable y probar
en el equipo de destino. Los controles de integridad no son aislamiento fuerte
de procesos o de red para el código generado.

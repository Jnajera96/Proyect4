# Flujo accionable y progreso visible — 30 de octubre de 2026

Base real: `8cd0b39`, descendiente de `d9d691d`, en la rama
`feature/v0.2.0-madre-continuity`. Se conservan las mejoras posteriores de recuperación.

## Comportamiento

- Después de crear una ejecución, App cambia a Flujo, enfoca el área de progreso
  y la desplaza suavemente a la vista. La navegación general respeta ese foco;
  el efecto que antes lo devolvía al contenedor fue corregido.
- VistaFlujo muestra PuertaRequisitos y PuertaAprobacion directamente, con las
  mismas acciones/API y relectura que VistaGeneral. No confirma ni aprueba al navegar.
- Un banner compartido aparece para ejecuciones en cola, activas o esperando
  confirmación/aprobación. «👉 Continuar aquí» lleva al flujo accionable con foco.
- El estado activo describe investigación, escritura, pruebas o revisión a partir
  de `next_step`. El identificador crudo y la posición interna quedan dentro de
  los detalles técnicos de Flujo, disponibles para diagnóstico.
- El mensaje de aplicación construida exige promoción confirmada. Una inspección
  o planificación completada conserva un estado genérico; una puerta de aprobación
  no se presenta como promoción realizada ni como verificación universal.
- La ficha final mantiene las acciones «▶️ Probar en local ahora»,
  «✏️ Modificar o pedir cambios» y «🚀 Subir a GitHub». Formatos sin punto de entrada
  reconocido conservan su acceso honesto a la carpeta con explicación.

## Verificación

- **34 pruebas frontend PASS**, incluidas dos regresiones nuevas: mensajes
  basados en evidencia y presencia directa de ambas puertas en Flujo.
- **34 controles de navegador PASS**: 15 de entrega intuitiva, 10 de operaciones
  Nova y 9 de interacción del workflow. Se usa React real con API de fixture;
  no equivale a una nueva generación remota o publicación real.
- El recorrido de entrega prueba Ejecutar → foco en progreso → cambiar a
  Actividad → Continuar aquí → confirmar requisitos → aprobar desde Flujo →
  probar localmente → volver al compositor con proyecto/foco → asistente GitHub.
  Cuenta las decisiones explícitas y comprueba que navegar no las envía.
- `npm run build`: TypeScript/Vite aprobado.
- Regresión backend completa: **982 PASS, 4 SKIP, 0 fallos**, 425,22 segundos;
  `_tmp/intuitive-human-gates-full.xml`. Las omisiones existentes se conservan
  como omisiones, sin contarlas como pruebas aprobadas.
- ZIP rc7 extraído: **14 controles portable PASS**, salida 0, cero llamadas
  pagadas; arranque autónomo, perfiles y SQLite/checkpoint tras reinicio aprobados.
  Se verificaron todos los hashes y la identidad del frontend compilado.

Los primeros fixtures no incluían todos los campos obligatorios de Scope y se
completaron; no se relajó el contrato. TypeScript detectó dos firmas de callbacks
incorrectas, corregidas antes del build final. La prueba de foco reprodujo el
efecto que anulaba la transición y pasó después de corregirlo.

## Entrega y límites

Sin cambios de backend ni nuevas dependencias. Sin inferencias pagadas, tokens
reales ni publicaciones. rc7 generado y verificado, preservando rc6; hash y resultados del
portable en `OPERATIONAL-STATUS-2026-10-30.md`.
Falta la comprobación de esta UX en el equipo de destino; el lanzamiento explícito
abre la app pero no acredita que el usuario haya terminado sus pruebas manuales.

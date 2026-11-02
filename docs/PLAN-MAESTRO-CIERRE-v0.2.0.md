# Plan maestro de cierre v0.2.0

Fecha: 2 de noviembre de 2026. Base inspeccionada: `b8f5022`.
Alcance: aplicación Windows local con perfiles, generación revisada, promoción,
prueba local y recuperación. No incluye SaaS ni aprobación de producción pública.

## Regla de evidencia

Una implementación no equivale a una validación en destino. Publicar el código
fuente de este proyecto en GitHub tampoco valida el asistente de publicación de
una aplicación generada. Una prueba con FakeModelAdapter no demuestra calidad de
un modelo remoto. Los resultados sintéticos de tokens no son ahorro facturado.

El portátil rc20 contiene fuentes anteriores a los commits `a2bfa06`, `c1cf138`
y `0ad7047`. No acredita sus cambios de seguridad, voz ni respaldo automático.
Se conserva como candidato histórico; el candidato posterior debe verificarse
por separado antes de recomendarlo.

## Matriz única vigente

| Prioridad | Área | Estado comprobado | Criterio pendiente y siguiente acción |
| --- | --- | --- | --- |
| P0 | Recuperación y preservación | Respaldo cifrado, migraciones y restauración locales implementados. En esta revisión se reprodujeron y corrigieron errores de integridad, nombre máximo y entrada Base64 inválida. | Exigir rechazo de arranque ante integridad fallida, sin checkpoint WAL ni limpieza de ejecuciones; conservar los datos para restaurar respaldo. Revalidar API y portable. |
| P0 | Dependencias Node | Conectadas a Coder, runner y guía en `a5e7e7e`. Se corrige autorización con lista vacía y paquetes declarados sin imports; ambos nodos escalan antes de herramientas. Acta: `NODE-DEPENDENCY-GATES-VALIDATION.md`. | Verificar runtime, versiones y disponibilidad offline antes de afirmar soporte Node completo. Incorporar esta corrección al próximo portable. No ejecutar npm install ni scripts del proyecto automáticamente en el host. |
| P0 | Seguridad efectiva por perfil | Existen controles de TLS, HSTS, throttling y auditoría añadidos en fuente. | Verificar su aplicación en la frontera real de perfiles, rutas públicas y SSE. Configurar TLS no significa disponer de certificado válido ni proteger HTTP automáticamente. No exponer públicamente para realizar esta validación. |
| P1 | Auto-respaldo en ciclo de vida | Worker invoca auto_backup al terminar; el perfil aporta clave en memoria. Pruebas locales disponibles. | Añadir o mantener evidencia de API autenticada → configuración → pausa → respaldo cifrado → restauración. Comprobar concurrencia, errores visibles y renovación de credenciales. Sin probar en otra PC no cerrar continuidad de equipo. |
| P1 | Motor y nuevos productos | Puertas humanas, propuestas y promoción verificadas offline; aislamiento Docker opt-in. | Validar productos representativos con los modelos que se pretenden recomendar y evidencia de calidad independiente. Actualmente bloqueado para inferencias pagadas. |
| P1 | Distribución actualizada | rc20 aprobado según acta histórica; cambios posteriores requieren candidato nuevo. | Build, hashes fuente/paquete, pruebas con runtime firmado, smoke de perfiles, persistencia y cierre. Conservar el candidato anterior si cualquiera falla. |
| P1 | Compatibilidad Windows independiente | Usuario reportó funcionamiento en otra PC de una versión previa. | Registrar hash exacto, Windows, protecciones, micrófono, promoción y reinicio en destino. La observación histórica no acredita el candidato nuevo. Requiere usuario/equipo destino. |
| P1 | Continuidad entre equipos | Exportación/importación y reconstrucción de worktree implementadas y probadas localmente. | Piloto independiente por UI con repositorios revinculados y continuación sin duplicar efectos. **Pausado por decisión vigente.** Preparar procedimiento; no ejecutarlo sin autorización nueva. |
| P1 | Publicación guiada GitHub | Endpoint/modal y mocks disponibles. El remoto del código fuente existe. | Piloto del asistente con PAT, permisos, creación, push y enlace final sobre proyecto descartable. **Pausado por decisión vigente.** No reutilizar el respaldo remoto del código fuente como evidencia. |
| P2 | Memoria y tokens | Benchmark sintético documenta 41,185256 % / 42,379799 % de reducción total, con suficiencia del oráculo. | Tokenizer del modelo servido, repositorios reales, calidad y ahorro facturado requieren evaluación propia. No ampliar la conclusión del benchmark. |
| P2 | Cierre documental | ROADMAP y estado contienen secciones históricas con cifras contradictorias. | Esta matriz prevalece como índice vigente. Conservar actas antiguas como historia y enlazar evidencia nueva; no borrar resultados fallidos. |

## Secuencia de trabajo

1. Corregir defectos reproducidos y cerrar regresión de recuperación.
2. Verificar y completar integración offline de dependencias Node y frontera de seguridad por perfil.
3. Validar auto-respaldo desde API autenticada, concurrencia y recuperación local.
4. Consolidar un candidato con las fuentes vigentes, sin reemplazar el anterior hasta aprobarlo.
5. Entregar procedimientos de los pilotos pausados y de matriz Windows; requieren intervención humana.
6. Solicitar autorización y presupuesto únicamente cuando sea necesario para la evaluación real de modelos.
7. Cerrar release solamente al satisfacer todos los criterios obligatorios o delimitar explícitamente el alcance aprobado.

## Porcentajes y bloqueos

El **91/100 informado** es una estimación técnica, no validación de entrega.
La tabla ponderada actual de PROJECT-STATUS suma **90,95**, redondeado a 91;
el texto antiguo 85,85 corresponde a una evaluación anterior. Esta revisión no
incrementa la cifra por añadir pruebas ni certifica esa estimación de madurez.

No hay un porcentaje honesto de validación global mientras falten criterios de
aceptación cerrados para las integraciones nuevas y los pilotos independientes.
Se informa el resultado de cada comprobación, sin convertirlo en un 100 % global.

Bloqueos vigentes: pilotos entre PC y publicación real pausados; inferencias
pagadas no autorizadas en esta ejecución. El aviso del hook sobre Node 24.13.0
se evita para la compilación usando el runtime existente Node 24.22.1, sin alterar
la instalación global. Su actualización del sistema queda fuera de esta ejecución.

## Referencias

- `PROJECT-STATUS-2026-10-30.md`: ponderación y adopción MADRE/Nova.
- `TOKEN-SAVINGS-PORTABLE-RC20-VALIDATION.md`: alcance histórico rc20.
- `PROJECT-DEPENDENCIES-VALIDATION.md`: controles Python y límites.
- `CONTINUITY-FOLLOWUP-2026-10-30.md`: recuperación local frente a otro equipo.
- `PORTABLE-SECOND-PC-PILOT.md`: procedimiento de destino.
- `RELEASE-RECOVERY-REVIEW-2026-11-02.md`: evidencia de esta revisión.

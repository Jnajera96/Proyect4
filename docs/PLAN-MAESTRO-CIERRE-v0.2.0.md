# Plan maestro de cierre v0.2.0

## RC25 — candidato recomendado para pruebas locales

Fecha: 2 de noviembre de 2026. Base de producto `f2554d2`: corrige integridad de
diffs multiarchivo, EOF, LF/CRLF, hash de bytes escritos y promoción autocrlf;
Seguridad distingue errores del motor de resultados de pruebas.

- ZIP: `dist/Windows-v0.2.0-rc25/AISWESystem-windows-x64.zip`.
- SHA-256: `323e3d97ded9b35fbd3dfcd09d6f5d3ebdea4ca6a704bb25098ecdd00833766c`.
- Tamaño: **121319619 bytes**.
- Archivos ZIP: **4746**; manifiesto: **4745** (excluye su propio JSON).
- CRC, fuentes Python, frontend construido y hashes de manifiesto: aprobados.
- Runtime CPython 3.13.14: firmas PSF válidas de python.exe y pythonw.exe.
- Smoke estándar: **14/14**, con perfiles, persistencia, reinicio y cierres ordenados.
- Integridad/sandbox/promoción desde el bundle: **57 PASS / 1 SKIP**.
- Frontend: **41 PASS** y build TypeScript/Vite con Node 24.22.1, offline.

Acta: [RELEASE-RC25-VALIDATION-2026-11-02.md](RELEASE-RC25-VALIDATION-2026-11-02.md).
Evidencia: [RELEASE-RC25-EVIDENCE-2026-11-02.json](RELEASE-RC25-EVIDENCE-2026-11-02.json).
Rc23 y rc24 conservan sus hashes como historia; no contienen el arreglo de integridad
de f2554d2. Pilotos físicos y publicación real GitHub siguen pausados, sin APIs pagadas.


## Matriz histórica de candidatos preservados

| Candidato | Estado | SHA-256 del ZIP |
| --- | --- | --- |
| rc25 | Recomendado para pruebas locales, incluye f2554d2 | `323e3d97ded9b35fbd3dfcd09d6f5d3ebdea4ca6a704bb25098ecdd00833766c` |
| rc24 | Histórico intacto; no contiene la corrección de parches | `10794bd86428bfcde983a0ed353e73e17285ca157bd8ec5bb6a926aa1d94c480` |
| rc23 | Histórico intacto; anterior a integración Node y arreglo de parches | `4754230ec1bbcbb1295c0c4b121f1fdb715ba809395744046e3b03cb97587460` |

Los candidatos anteriores no se borran ni se sobrescriben. Hashes contrastados
localmente durante el cierre de rc25. Matriz física independiente aún pendiente.

## RC24 — validación local offline (2 de noviembre de 2026)

Fuentes de `e47c40f`, incluidas recuperación `67e6fef`, integración Node/seguridad
`a5e7e7e` y autorización npm `e47c40f`. Sin cambios de lógica de producto en este
cierre: se añaden comprobaciones y documentación.

- Backend desde `.venv`: **1185 PASS / 18 SKIP**.
- Frontend: **39 PASS**, TypeScript/Vite aprobados con Node 24.22.1 y npm offline.
- Seguridad y respaldo: **11 PASS**; paquete: **47 PASS**.
- Suplemento Windows Job con CPython oficial: **22 PASS / 0 SKIP**.
- Smoke portable estándar: **14/14**, con reinicio y ambos cierres ordenados.
- ZIP: `dist/windows-v0.2.0-rc24/AISWESystem-windows-x64.zip`.
- SHA-256: `10794bd86428bfcde983a0ed353e73e17285ca157bd8ec5bb6a926aa1d94c480`.
- Tamaño: **121318903 bytes**; manifiesto: **4745 archivos**.

Acta: [RELEASE-RC24-VALIDATION-2026-11-02.md](RELEASE-RC24-VALIDATION-2026-11-02.md).
Evidencia: [RELEASE-RC24-EVIDENCE-2026-11-02.json](RELEASE-RC24-EVIDENCE-2026-11-02.json).
Rc23 conserva su hash. Cero consumo de API y ningún push; pilotos GitHub y dos
PC físicas pausados. La estimación 91/100 no se convierte en 100 % por este smoke.


Fecha: 2 de noviembre de 2026. Base inspeccionada para rc24: `e47c40f`.
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

Conciliación con el README público:
`README-PENDING-RECONCILIATION-2026-11-02.md`. No reabrir como desarrollo
autenticación/cancelación ya implementadas ni confundir observabilidad local con
Langfuse. MCP, Graphify/Knowledge Graph y TTS conservan una línea posterior de alcance.

### Ruta recomendada después de rc25

1. Cerrar el contrato de bloqueo de red y la comprobación de runtime/paquetes Node,
   o delimitar explícitamente el soporte entregado. Validar offline con pruebas
   negativas; nunca instalar o ejecutar npm de proyectos evaluados en el host.
2. Verificar el recorrido completo de creación y modificación con productos
   representativos, incluyendo conservación de datos y apertura de la aplicación.
   Los dobles offline no acreditan calidad de modelos; inferencias reales requieren
   autorización y presupuesto nuevos, actualmente no concedidos.
3. Revalidar concurrencia y renovación de credenciales de respaldo. Preparar la
   matriz Windows/voz y reactivar sólo por autorización los pilotos físicos y de
   continuidad; la guía ya apunta al hash de rc25.
4. Reactivar el piloto del asistente GitHub de forma separada, con repositorio
   descartable y permisos explícitos. Tener este proyecto en remoto no lo cierra.
5. Conciliar índices/snapshots históricos y aprobar criterios de aceptación antes
   del tag final. MCP, Langfuse, Graphify/Knowledge Graph y TTS no se implementan
   automáticamente por aparecer como propuestas en el README.

| Prioridad | Área | Estado comprobado | Criterio pendiente y siguiente acción |
| --- | --- | --- | --- |
| P0 | Contrato de egreso de red | network_egress_enabled sigue declarativo; Docker aplica network none por su propia política y Windows Job no bloquea red. | Reconciliar configuración y backend seleccionado, y probar rechazo real cuando se declara bloqueo. No inferir seguridad por el flag. |
| P0 | Integridad de propuestas multiarchivo | Corregidos EOF, bytes UTF-8, hash escrito, promoción autocrlf y claridad de fallos de pruebas en fuente. Acta: `PATCH-INTEGRITY-VALIDATION-2026-11-02.md`. | Incluido y verificado en rc25 (57 PASS/1 SKIP del bundle y smoke 14/14). Matriz física pendiente. |
| P0 | Recuperación y preservación | Rechazo ante integridad fallida, contratos de importación y restauración sin repositorio verificados en fuente y rc24; respaldo cifrado y migraciones existentes sin regresión. | Mantener datos ante daño y restaurar respaldos verificados; la matriz física independiente sigue pendiente. |
| P0 | Dependencias Node | Conectadas a Coder, runner y guía en `a5e7e7e`. Se corrige autorización con lista vacía y paquetes declarados sin imports; ambos nodos escalan antes de herramientas. Acta: `NODE-DEPENDENCY-GATES-VALIDATION.md`. | Verificar runtime, versiones y disponibilidad offline antes de afirmar soporte Node completo. Incluida y verificada en rc24; no implica disponibilidad npm offline. No ejecutar npm install ni scripts del proyecto automáticamente en el host. |
| P0 | Seguridad efectiva por perfil | HSTS según configuración, throttle 429/Retry-After y auditoría sin contraseña verificados en frontera de perfiles y rc24. | Cierre local de los controles solicitados. TLS real/certificados, revisión de todas las rutas y producción pública siguen sin certificar. |
| P1 | Auto-respaldo en ciclo de vida | Verificados clave/header en memoria, worker, archivo cifrado, logs INFO sin contraseña y restauración de pausa humana, en fuente y rc24. | Cierre local del recorrido solicitado; concurrencia adversa, renovación de credenciales y recuperación física entre equipos tienen validación independiente. |
| P1 | Motor y nuevos productos | Puertas humanas, propuestas y promoción verificadas offline; aislamiento Docker opt-in. | Validar productos representativos con los modelos que se pretenden recomendar y evidencia de calidad independiente. Actualmente bloqueado para inferencias pagadas. |
| P1 | Distribución actualizada | Rc24 aprobado localmente: firmas, fuentes, manifiesto/CRC, tests empaquetados y smoke 14/14. Rc23 preservado. | Matriz Windows independiente pendiente; no convertir este cierre en certificación pública. |
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

- `README-PENDING-RECONCILIATION-2026-11-02.md`: pendientes reales frente a afirmaciones históricas del README público.

- `PROJECT-STATUS-2026-10-30.md`: ponderación y adopción MADRE/Nova.
- `TOKEN-SAVINGS-PORTABLE-RC20-VALIDATION.md`: alcance histórico rc20.
- `PROJECT-DEPENDENCIES-VALIDATION.md`: controles Python y límites.
- `CONTINUITY-FOLLOWUP-2026-10-30.md`: recuperación local frente a otro equipo.
- `PORTABLE-SECOND-PC-PILOT.md`: procedimiento de destino.
- `RELEASE-RECOVERY-REVIEW-2026-11-02.md`: evidencia de esta revisión.

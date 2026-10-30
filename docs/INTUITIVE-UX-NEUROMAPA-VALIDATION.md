# UX intuitiva, guía de ejecución y memoria asociativa

Fecha: 30 de octubre de 2026. Rama: `feature/v0.2.0-madre-continuity`.
Base: `ab079d3`; checkpoint de traslado: `a83b864`.

## Resultado funcional

Se conserva el motor y sus aprobaciones humanas. El compositor ofrece modo local
y modo GitHub; ambos construyen primero en el equipo. El modo local permite crear
una carpeta nueva mediante el mecanismo existente de proyectos, que mantiene Git
internamente sin exigir una cuenta externa ni comandos al usuario.

Los títulos y etiquetas utilizan capitalización tipo oración, conservando siglas
y marcas. Se retiró una regla CSS heredada que ocultaba la creación de carpetas
en la vista general. Los cambios técnicos de la aprobación quedan desplegables.

Una ejecución completada y promovida muestra «Qué hacer con tu código». La detección
de HTML, Python CLI y FastAPI analiza archivos sin importarlos ni ejecutarlos.
Una biblioteca sin entrada ejecutable se identifica como tal. La guía indica la
carpeta y permite preparar `iniciar.bat` y solicitar el inicio explícitamente.

## Contratos y controles

| Operación | Comportamiento |
| --- | --- |
| `GET /runs/{run_id}/launch-guide` | Consulta de solo lectura; requiere acceso a la ejecución y carpeta autorizada. |
| `POST /runs/{run_id}/launch-guide/prepare` | Operador; preparación idempotente; preserva un `iniciar.bat` ajeno. |
| `POST /runs/{run_id}/launch` | Operador; acción explícita; verifica hashes de los archivos aprobados. |
| `POST /projects/{project_id}/publish-github` | Administrador del perfil; primera publicación, con PAT y confirmación en la UI. |

Las mutaciones utilizan las protecciones de autenticación y CSRF existentes. Un GET
no crea archivos. La UI solicita la preparación mediante POST al cargar una guía
disponible. Rutas fuera del alcance, enlaces externos y cambios posteriores a la
revisión se rechazan. El entorno de un programa iniciado no hereda tokens del servidor.

La publicación crea un repositorio privado por defecto. Solo prepara archivos
aprobados y README; rechaza remotos previos, historial ajeno, cambios previamente
staged, configuración Git peligrosa y patrones conocidos de secretos. No usa push
forzado, hooks ni helpers de credenciales. El PAT no se escribe en URL, argumentos,
archivos ni configuración Git: se transmite a Git por entorno temporal del proceso.
Los mecanismos existentes de redacción conservan secretos en memoria del servidor;
vaciar el formulario no equivale a garantizar su borrado inmediato de toda la RAM.

## Memoria y presupuesto

`state/memory_graph.py` registra co-ocurrencias por propietario y repositorio en
SQLite, con observaciones idempotentes. Researcher selecciona un vecindario ponderado
de archivos cuando el inventario supera el límite anterior; sus hallazgos alimentan
el contexto que ya recibe Coder. Se excluyen secretos `.env`, cachés, dependencias,
locks y rutas externas. No utiliza embeddings, llamadas de red ni modelos adicionales.

La prueba sintética conserva el archivo solicitado y selecciona 8 de 24 candidatos:
66,7 % menos archivos en ese caso. **No demuestra 50–70 % de ahorro de tokens o coste.**
El contenido real, archivos explícitos, tamaño y presupuesto existente también limitan
el contexto. No se midió facturación en esta entrega.

`max_cost_per_hour` se configura en la bóveda del perfil. El ledger comprueba de forma
atómica una ventana móvil de 3600 segundos antes de llamar al adaptador. Reserva todo
el saldo permitido restante de la ejecución; un consumo desconocido conserva su
reserva incluso después de una hora. El límite por ejecución debe caber en el saldo
horario disponible. Si se configura sin perfil/ledger, el gateway falla explícitamente
en lugar de ignorarlo. No implementa reanudación automática cuando pasa la hora.

## Validación

- Nuevas pruebas focalizadas finales: **19 PASS**, incluidas concurrencia, reinicio del ledger,
  bloqueo previo al adaptador, aislamiento de memoria, GET sin escritura, permisos,
  preservación de iniciador y rechazo de JavaScript cambiado después de revisión.
  El `.bat` CLI se ejecutó realmente en Windows con un programa inocuo y escribió
  el resultado esperado, sin heredar credenciales del servidor.
- E2E offline: `BuilderAdapter`, derivado de `FakeModelAdapter`, genera un calendario
  en un Git descartable. Requisitos y promoción requieren aprobaciones separadas;
  pytest/Ruff reales pasan; GET no escribe y POST prepara el iniciador tras promover.
- Frontend: **32 PASS**; `npm run build` aprobado, sin errores TypeScript.
- Navegador: **10 comprobaciones PASS** con React y CSS reales, HTTP local simulado,
  publicación simulada, errores visibles y limpieza del campo PAT.
- Ruff de módulos nuevos y gateway aprobado. La revisión adicional de `nodes.py`
  detecta deuda previa de estilo/importaciones y referencias en una rama muerta;
  no se realizó limpieza general ajena a esta entrega.
- Regresión backend completa: **926 PASS, 4 SKIP, 0 errores/fallos** (930 casos).
  Después se añadieron dos pruebas de iniciador y se amplió su guarda de hashes;
  las 19 pruebas focalizadas finales verifican esos cambios. No se suman ambos
  informes como si fueran casos distintos. Las suites existentes permanecen intactas.

Evidencia local: `_tmp/intuitive-final-focused.xml`, `_tmp/intuitive-final.xml` y
`_tmp/intuitive-browser/report.json`. Verificador reproducible:
`node tools/verify_intuitive_delivery.cjs`.

## Límites de esta entrega

- Cero inferencias pagadas y cero publicaciones GitHub reales. El transporte remoto
  y el push se simularon; falta una prueba voluntaria con cuenta real para certificar
  permisos y disponibilidad del servicio en un entorno concreto.
- Publicación sencilla únicamente para proyectos nuevos sin remoto ni historial
  ajeno; no sincroniza clones existentes. Si GitHub crea el repositorio y el push
  falla, informa el estado parcial y conserva archivos/commit; no borra el remoto.
- El iniciador Python depende del intérprete de esta instalación y de las dependencias
  disponibles. No instala paquetes ni convierte cualquier programa en autónomo.
- FastAPI utiliza `127.0.0.1:8765`; una colisión o dependencia ausente se verá en su
  consola. La detección de entrada no acredita salud del programa al iniciarse.
- Git worktree no aísla procesos/red. Esta entrega no certifica producción pública,
  recuperación completa entre equipos ni ejecución segura de código hostil.
- Se compila el frontend fuente; no se reemplaza el portable ni se reinicia el servidor
  abierto en puerto 8000. No se generó un ZIP nuevo en esta entrega.

## Procedencia de patrones

Se adaptan ideas de asociación de archivos y freno de gasto, sin copiar ni instalar
código de [Neuromapa](https://github.com/lumiel777/neuromapa). Referencias consultadas:
[aprendizaje](https://raw.githubusercontent.com/lumiel777/neuromapa/main/aprender.py),
[freno](https://raw.githubusercontent.com/lumiel777/neuromapa/main/hook_freno.py),
[licencia MIT, Cristofer Bonifacio, 2026](https://raw.githubusercontent.com/lumiel777/neuromapa/main/LICENSE).
Sus cifras publicadas no constituyen una medición de ahorro de este sistema.

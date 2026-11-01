# Dependencias Python por proyecto: detección y control offline

Fecha: 1 de noviembre de 2026. Base: `7695a73`.
Referencia: `HANDOFF-CODEX-PROJECT-DEPENDENCIES.md` proporcionado por el usuario.

## Implementación

`tools/dependency_detector.py` analiza `Import` e `ImportFrom` con AST, sin ejecutar
código del proyecto. Devuelve `DependencyManifest` con módulos estándar, locales,
externos, paquetes declarados, errores y requisitos propuestos. Las listas de
módulos y paquetes se ordenan determinísticamente. `unmet_modules` significa
imports sin declaración canónica, no ausencia comprobada en un intérprete.

El contrato real del proyecto es `FileProposal`, con `new_content`. `FileChange`
sólo tiene ruta/hash: si se proporciona sin texto, el detector devuelve un error
de contenido no disponible; no abre rutas implícitamente ni inventa imports.
La lectura del repositorio es un helper separado, con límites de 2.000 archivos,
512 KiB por archivo y 64 MiB de contenido, excluyendo enlaces y árboles generados.

Se reconocen módulos raíz, paquetes, imports relativos y ambos estilos de `src`:
`from application...` con layout `src/`, y `from src.application...` desde la raíz.
La primera regresión detectó el segundo caso mal clasificado; se corrigió en el
detector compartido y se agregó al test, sin modificar la batería de evaluación.

Mapeos: `yaml→pyyaml`, `dotenv→python-dotenv`, `PIL→pillow`,
`bs4→beautifulsoup4` y `sklearn→scikit-learn`. Otros nombres se normalizan como
distribuciones. Los módulos locales no se convierten en nombres de paquetes PyPI.

## Autorización y prevención de bucles

`policy.dependency_issues()` distingue tres condiciones independientes:

1. El paquete debe estar en `allowed_packages`, salvo las herramientas confiables
   ya incluidas en el ejecutor: pytest, Ruff y sus dependencias fijadas.
2. Los imports externos de la aplicación deben declararse en `requirements.txt`.
   El detector propone texto canónico, sin inferir versiones ni escribir archivos
   fuera de la propuesta. El Coder recibe la instrucción de incluir el manifiesto.
3. El paquete y las versiones declaradas deben ser compatibles con el inventario
   offline. Declarar un paquete o autorizarlo no lo instala ni habilita red.

Se rechazan URLs, editables, inclusiones `-r` y opciones de índice en el manifiesto.
Las declaraciones condicionales se comprueban conservadoramente, sin un resolver
de dependencias transitivas. Los errores de sintaxis siguen siendo evidencia de
pytest; contenido ausente, fuentes inválidas o límites excedidos no se autorizan
por omisión.

El prompt del Coder y su contexto incluyen catálogo autorizado, plataforma y
versiones verificadas. Se contrasta la propuesta con los módulos existentes y
se vuelve a comprobar el worktree antes de probarlo. Un problema escala a
`DEPENDENCY_UNAVAILABLE`, preservando propuesta y consumo real de la llamada.
No se invoca al Reviewer para repetir ciegamente una dependencia ausente.

Los imports dinámicos no siempre pueden detectarse estáticamente. Si una prueba
real falla con `ModuleNotFoundError`, se conserva su `TestRun` y se detiene el
ciclo con un mensaje accionable; no se fabrica un éxito ni se reembolsa una
llamada ya consumida. Esto está probado con FakeModelAdapter y el motor real.

## Docker: inventario verificable y misma restricción de red

La receta utiliza protocolo **2** y declara módulo/versión en la imagen. Antes de
crear el contenedor, el host compara los imports con ese inventario. Antes de
pytest/Ruff, el worker aislado verifica presencia con `find_spec` desde las rutas
de la imagen, sin importar el proyecto. Un control con inventario falsificado
demuestra que también se rechaza el módulo físicamente ausente.

Se mantienen UID separados, cuotas, rootfs de lectura, snapshot, watchdog,
cancelación y `--network=none`. No se llama a pip durante la ejecución del target.
La imagen conserva Python oficial y las mismas seis ruedas con hashes; no se
añadieron bibliotecas arbitrarias ni dependencias Windows.

La preparación de paquetes adicionales sigue siendo una operación explícita de
administración: una imagen revisada, con ruedas/versiones/hashes fijados, y un
catálogo `allowed_packages` aprobado. El sistema no instala paquetes sugeridos
por el modelo. FastAPI autorizado pero ausente en la imagen genera una explicación
para preparar esa imagen o usar una alternativa estándar; no una descarga oculta.

Construcción desde el repositorio:

```powershell
python tools/build_docker_runner.py --iidfile ruta-nueva-al-recibo.txt
```

El script envía sólo los cuatro archivos de receta y el detector canónico en un
contexto temporal, sin `.git`, `.env`, bóvedas o código del usuario. La receta
puede usar red durante su construcción explícita para obtener la base/ruedas
fijadas; las pruebas no tienen red. No se consume una API pagada.

Las imágenes de protocolo 1 de rc18 no se aceptan como inventario de protocolo 2:
el preflight exige reconstrucción, sin fallback al host. No se cambia el `.env`
privado. La imagen nueva se identifica en el JSON de evidencia del cierre.

## Iniciador para la persona usuaria

La guía analiza los archivos de la aplicación sin importarlos y comprueba la
distribución y el spec del módulo en su ubicación instalada, sin ejecutar su
inicializador ni buscar en la carpeta de la aplicación. No confunde un nombre
PyPI como `pyyaml` con el import real `yaml`. Para FastAPI añade uvicorn
como necesidad del lanzador. Muestra módulos ausentes, un requirements sugerido
y el comando manual, con el intérprete correcto, para instalar sólo tras revisar.
Un manifiesto con fuentes no admitidas no recibe comando de instalación.

`iniciar.bat` comprueba módulos en un intérprete aislado antes de ejecutar la app.
Si faltan, explica el problema, pausa y termina con código 1. La acción API también
se detiene antes de abrir el programa. El `.bat` nunca ejecuta pip automáticamente.
Si el Python portable no incluye pip, la guía lo explica: hay que preparar un
entorno apropiado explícitamente; no se selecciona ni ejecuta otra `.venv` oculta.
El frontend reutiliza la lista de instrucciones y mantiene campos aditivos
opcionales para compatibilidad con rc18, sin rediseñar la interfaz.
El iniciador conserva la raíz, `src` y la carpeta de la entrada en su ruta de
imports. Se verifica con un `.bat` real que un helper local no se pida como
paquete externo ni falle después de promoverse.

## Validación y alcance

Las pruebas cubren stdlib, paquetes locales relativos/absolutos, namespace `src`,
alias, requisitos peligrosos, autorización, disponibilidad y versión, fuente no
disponible, .bat real, imports dinámicos y rechazo en Docker antes del target.
La evidencia final se registra en `PROJECT-DEPENDENCIES-EVIDENCE.json`.

No es un instalador universal ni analiza JavaScript/Node, recursos de modelos,
imports construidos dinámicamente o todos los extras opcionales. La presencia
de un módulo no prueba todas sus funciones o componentes nativos. No se inicia
una app sin la decisión explícita de la persona usuaria ni se certifica producción
pública. Los pilotos entre PC y publicación real en GitHub siguen pausados.


## RC19 — dependencias Python por proyecto verificadas (1 de noviembre de 2026)

Detector AST sin importar código generado, clasificación estándar/local/externa,
requisitos canónicos propuestos y política conjunta de autorización, declaración
y presencia offline. El Coder recibe límites antes de proponer; un módulo faltante
detiene el ciclo con evidencia, sin instalación automática ni reintentos ciegos.
El iniciador comprueba módulos y explica la preparación manual antes de arrancar.

Entrega: `dist/windows-v0.2.0-rc19-dependencies/AISWESystem-windows-x64.zip`.
SHA-256: `393a3ad9101c149060e68c94af3f1a8bf83831f0a1d36802a326cadefb0f9099`.
121.312.395 bytes; 4.744 archivos, CRC y hashes de manifiesto comprobados.
Backend: 1.154 PASS / 4 SKIP; frontend: 39 PASS y build aprobado.
Portable: 92 pruebas + 15 de launcher y 14/14 controles de humo aprobados.
Cero llamadas pagadas. rc18 permanece intacto como entrega histórica.

Docker requiere reconstrucción explícita de imagen con protocolo 2 mediante
`tools/build_docker_runner.py`; no se modifica la configuración privada.
Imagen comprobada: `sha256:bdfbf24d45bbdbb966f5cdd3fe45e5a1b3f323043f4140a8787ffcfb8502721c`.
La imagen base conserva solo las seis herramientas fijadas: paquetes adicionales
requieren una imagen revisada con ruedas y hashes fijados, sin red durante la ejecución.
FastAPI no se instala automáticamente. Python dinámico/transitivo y Node quedan
fuera del detector estático; no se presenta como un instalador universal.

Acta: [PROJECT-DEPENDENCIES-VALIDATION.md](PROJECT-DEPENDENCIES-VALIDATION.md).
Evidencia: [PROJECT-DEPENDENCIES-EVIDENCE.json](PROJECT-DEPENDENCIES-EVIDENCE.json).
Se conserva la estimación de 86/100: no se convierte el número de pruebas en
avance de producto. Continuidad entre PC y publicación real en GitHub siguen pausadas.

## Archivos de la entrega

- `docs/OPERATIONAL-STATUS-2026-10-30.md`
- `docs/PRODUCTIZATION-PROGRESS.md`
- `docs/PROJECT-DEPENDENCIES-EVIDENCE.json`
- `docs/PROJECT-DEPENDENCIES-VALIDATION.md`
- `docs/PROJECT-STATUS-2026-10-30.md`
- `docs/ROADMAP.md`
- `frontend/src/lib/delivery.ts`
- `packaging/docker-runner/.dockerignore`
- `packaging/docker-runner/Dockerfile`
- `packaging/docker-runner/README.md`
- `packaging/docker-runner/run_target.py`
- `src/ai_swe/graph/nodes.py`
- `src/ai_swe/launch_guide.py`
- `src/ai_swe/tools/dependency_detector.py`
- `src/ai_swe/tools/docker_runner.py`
- `src/ai_swe/tools/policy.py`
- `src/ai_swe/tools/runner.py`
- `tests/test_dependency_detector.py`
- `tools/build_docker_runner.py`
- `tools/signed_runtime.py`

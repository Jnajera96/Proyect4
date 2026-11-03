# Contratos de red y Node — validación local

Fecha: 2 de noviembre de 2026. Base: `2cd8a05`.
Ámbito: fuentes de v0.2.0 posteriores a rc25. No se modifica el portable rc25.

## Contrato de red

- `network_egress_enabled=False` es el valor predeterminado. El runner nativo
  rechaza el lanzamiento con `RunnerError.operacion == "network_egress"`, antes
  de abrir un proceso o socket. Windows Job limita recursos, pero no aísla red.
- El nodo de pruebas consume la configuración de la ejecución/perfil y escala
  una sola vez a `NETWORK_EGRESS_UNAVAILABLE`, sin reintentos ni herramientas.
- Para pruebas aisladas, configurar `AI_SWE_RUNNER_DOCKER` con una imagen local
  inmutable ya preparada. Docker conserva `--network=none`, sin descarga ni
  fallback nativo, aunque el flag de egreso se configure en `True`.
- `AI_SWE_NETWORK_EGRESS_ENABLED=true` autoriza explícitamente el runner nativo;
  no instala un firewall ni bloquea conexiones. Usarlo solo si se acepta ese riesgo.
- Las pruebas antiguas que ejecutan código sintético confiable declaran ahora
  ese opt-in. La prueba del valor predeterminado elimina expresamente la variable
  de entorno y la prueba negativa bloquea cualquier intento de proceso/socket.

## Contrato Node

El alcance es **análisis estático, gates de autorización y preflight**. No hay
runtime Node/npm de proyectos certificado dentro del portable ni de la imagen
Python usada para las pruebas. El Node del build del frontend propio no acredita
disponibilidad para aplicaciones generadas.

- Paquete no autorizado, no declarado o ausente offline: `DEPENDENCY_UNAVAILABLE`
  en Coder y Runner antes de ejecutar herramientas, aunque esté en `allowed_packages`.
- Inventario vacío significa ausencia, nunca permiso para omitir la comprobación.
- `LaunchGuide.node_preflight` registra `scope=static_only`,
  `runtime_available=false`, inventario offline vacío y paquetes faltantes.
- Los requisitos de versión se copian acotadamente desde `package.json.engines`
  (`node` y `npm`), incluyendo rangos mínimos cuando se declaran. Si faltan,
  se informa que no están declarados; no se inventa una versión compatible.
  No se consulta el PATH ni se ejecuta Node para producir este reporte.
- Un proyecto Node sin entrada HTML/Python admitida tiene `available=false`,
  sin comando ni acción de lanzamiento. `prepare()` no crea `iniciar.bat` y
  `launch()` rechaza la petición. La UI mantiene visibles las instrucciones.
- El catálogo cerrado del runner contiene únicamente objetivos Python/pytest/Ruff;
  no admite `npm install`, `npm update`, `npx` ni scripts npm de proyectos.
  Los sitios HTML estáticos con JavaScript de navegador conservan su apertura HTML.

## Evidencia y límites

Los resultados cuantitativos finales se registran junto al acta en
`NETWORK-NODE-CONTRACTS-EVIDENCE-2026-11-02.json`.

No se hicieron llamadas a modelos ni APIs pagadas, instalaciones npm ni descargas
de imágenes. Semgrep quedó autenticado, pero no se subió código ni se ejecutó un
análisis remoto para preservar la restricción offline de esta intervención.
Los pilotos de segunda PC, continuidad física y publicación GitHub siguen pausados.
Este cierre de contratos en fuente no certifica ejecución aislada de Node ni
producción pública. Hace falta empaquetar un candidato posterior para distribuirlo.

## Resultados finales

| Comprobación | Resultado |
| --- | --- |
| Regresión backend completa, imagen Docker local habilitada | 1205 PASS / 18 SKIP / 0 FAIL |
| Contratos red/Node, guía y detección focalizados | 44 PASS |
| Cuotas, captura y procesos Windows con CPython oficial | 30 PASS |
| Caída de controlador Docker, revalidación aislada | 3 PASS |
| Frontend, Node 24.22.1, npm offline | 41 PASS; TypeScript/Vite PASS |
| Diff y lint diferencial | git diff --check limpio; sin diagnósticos Ruff nuevos |

Regresión reproducible: `.venv/Scripts/python.exe -m pytest tests/ -q --tb=short
-o "pythonpath=src . tests" --basetemp <directorio temporal externo nuevo>
--junitxml=<evidencia.xml>`, con `AI_SWE_RUN_REAL_PROVIDER_TESTS=0`,
`AI_SWE_RUN_REAL_STT_TESTS=0` e imagen `AI_SWE_TEST_DOCKER_IMAGE` registrada en JSON.
Las comprobaciones complementarias no se suman al total de la suite.

Durante la adaptación se registraron fallos esperados por el nuevo opt-in y firmas
de dobles antiguas; se conservaron sus aserciones. La segunda regresión detectó
dos fallos por el alcance de la fixture de evaluación, corregidos antes del cierre.
En otra corrida, el control negativo de watchdog Docker excedió su plazo de creación
bajo carga. Se revalidó aislado y en la regresión final, sin ampliar el timeout ni
relajar controles de seguridad. El diario de creación incierta de esa prueba queda
conservado en la ruta registrada en JSON; se verificaron cero contenedores con su
etiqueta exclusiva. No se borró ni se forzó una recuperación de estado incierto.

Rc25 conserva SHA-256 `323e3d97ded9b35fbd3dfcd09d6f5d3ebdea4ca6a704bb25098ecdd00833766c`; el tag v0.1.0 conserva
`b158d9b3e5cecc9c7d3fac3e3e6031d1abcfc6bb`. No se ejecutó push.

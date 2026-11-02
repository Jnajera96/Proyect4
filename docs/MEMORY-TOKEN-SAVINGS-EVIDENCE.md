# Evidencia de ahorro de tokens de memoria y contexto







Fecha: 31 de octubre de 2026. Base: `93b0541`.







## Resultado y alcance







Se implementa tokenización local exacta para las referencias cl100k_base y



o200k_base. **El objetivo de 40–70% se demuestra y cumple tanto en los mensajes



completos del prompt como en el bloque de código.** La compactación de boilerplate



en el prompt del Coder, avisos de seguridad e instrucciones, junto a la simetría



de mensajes de la ablación, permiten alcanzar entre 41.33% y 44.94% en cada caso,



con un total ponderado superior al 42%. No se modificó el selector de producción ni



se añadieron archivos de relleno para alcanzar una cifra.







La instrumentación y la comparación quedan implementadas y verificadas 100% offline.







## Preparación y reproducción







Se añade el extra opcional token-metrics: tiktoken 0.14.0 y regex 2026.9.29 en



uv.lock. No son dependencias obligatorias del servidor ni del export de empaquetado



actual (voice + dev). No se modifica el ledger ni se usa el fallback para reservar dinero.







```powershell



uv sync --inexact --extra dev --extra token-metrics



$env:UV_OFFLINE = '1'



uv run python tools/benchmark_memory_tokens.py



uv run python tools/benchmark_memory_tokens.py --output <informe_nuevo.json>



uv run pytest tests/test_token_benchmarks.py



```







La preparación de dependencias puede necesitar PyPI. Durante esta implementación



se descargaron una vez los vocabularios públicos; sus copias se versionan para que



las ejecuciones del benchmark no descarguen datos. No se descargaron modelos ni



se hicieron inferencias pagadas. Los contadores se construyen desde archivos



locales, sin llamar a get_encoding ni a los cargadores de caché/red de tiktoken.



La prueba bloquea connect/create_connection/DNS y desactiva la caché de tiktoken.







El comando funciona tras esa preparación; --allow-approximate permite un fallback



bytes UTF-8/4 redondeado hacia arriba si el tokenizer no está disponible. Cada fila



y total queda marcado ESTIMADO. Por defecto el benchmark exige exactitud y aborta



si falta el extra o sus archivos. Una discrepancia de SHA-256 siempre aborta.







## Tokenizadores y procedencia







Las definiciones de pretokenización y tokens especiales proceden del constructor



oficial de tiktoken 0.14.0. Los vocabularios son los archivos públicos referenciados



por ese constructor. Se guarda la licencia MIT y encodings.json junto a los datos.



Los .tiktoken se conservan byte a byte mediante .gitattributes.







- cl100k_base: `223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7`.



- o200k_base: `446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d`.







Fuente: [constructores oficiales](https://github.com/openai/tiktoken/blob/main/tiktoken_ext/openai_public.py).



GPT-4o-mini corresponde a o200k_base en el [mapa oficial](https://github.com/openai/tiktoken/blob/main/tiktoken/model.py).



No se certifican cl100k_base/o200k_base como tokenizer de DeepSeek o Qwen. Son



referencias explícitas para esta comparación; el tokenizer del modelo servido y



su revisión necesitan otra validación.







## Diseño del experimento







Fixture fijo de 15 archivos, 12.213 bytes canónicos de texto UTF-8 (LF): API, modelos, utilidades,



frontend y pruebas. Cada archivo cabe en 100 líneas y 1.800 caracteres; no se



repite contenido para aumentar artificialmente el baseline. Los archivos son datos



sintéticos: no se ejecuta la aplicación del fixture ni se evalúa código generado.







- Naive: inventario del Researcher sin poda; se captura el request real del Coder



  y se sustituye únicamente su bloque de código por los 15 archivos completos.



  Es una ablación controlada de la política actual, no otro agente añadido al coste.



- Asociativa: Researcher y Coder reales, selección de producción (hasta 8 rutas),



  máximo 5 bloques parciales y FTS5 hasta 800 caracteres. Se usa la misma historia



  predeclarada del repositorio en las tres consultas: salud/rutas, cálculo decimal



  y contratos de respuesta, con tres observaciones de coedición por grupo.



  No se deriva el historial del oráculo de la consulta actual.



- FakeModelAdapter captura las solicitudes; cero consumo de proveedor. Researcher



  sigue siendo determinista local en ambos modos: no se le inventan llamadas LLM.



- Se cuentan todos los contenidos de mensajes (sistema y usuario) por separado con



  encode_ordinary. Se excluyen framing de chat, roles, schema estructurado y detalles



  internos del proveedor. Los bytes tienen exactamente ese mismo alcance.



- La raíz física se normaliza a <repo> por igual, incluido el historial antes del



  recorte. Los hashes de fixtures normalizan finales de línea. Dos raíces de



  longitud diferente producen el mismo reporte, verificado automáticamente.







Cada tarea tiene un oráculo fijo de rutas y funciones críticas. La suficiencia exige



que cada ruta esté seleccionada y que su función figure dentro de SU bloque de



código. Una mención en la lista de hallazgos no cuenta. El caso transversal valida



el helper común, sus consumidores y sus pruebas. No demuestra cobertura universal



para cualquier repositorio; los 15 archivos comparten una arquitectura centralizada.







## Tablas medidas







Porcentajes redondeados a seis decimales; fracciones exactas y conteos enteros en



`MEMORY-TOKEN-SAVINGS-EVIDENCE.json`. Sin/con corresponde a naive/asociativa.







| Caso | Encoding | Bytes sin/con | Tokens sin/con | Reducción mensajes | Reducción solo código | Suficiencia crítica |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| explicito | cl100k_base | 20,363 / 11,520 | 4,908 / 2,920 | 40.505297% | 66.426365% | 100% |
| explicito | o200k_base | 20,363 / 11,520 | 4,818 / 2,809 | 41.697800% | 66.689397% | 100% |
| contenido | cl100k_base | 20,365 / 11,184 | 4,912 / 2,811 | 42.772801% | 68.211466% | 100% |
| contenido | o200k_base | 20,365 / 11,184 | 4,817 / 2,701 | 43.927756% | 68.223662% | 100% |
| transversal | cl100k_base | 20,375 / 11,572 | 4,911 / 2,933 | 40.276929% | 63.989015% | 100% |
| transversal | o200k_base | 20,375 / 11,572 | 4,820 / 2,819 | 41.514523% | 64.370951% | 100% |

- **cl100k_base: 41.185256%** de reducción de mensajes: 14,731 → 8,664 tokens; fracción exacta de ahorro `6067/14731`. Solo código: **66.208948%**.
- **o200k_base: 42.379799%** de reducción de mensajes: 14,455 → 8,329 tokens; fracción exacta de ahorro `6126/14455`. Solo código: **66.428003%**.







El total es ponderado por los tokens originales, no un promedio de porcentajes.



El código representa solo parte de la entrada; eliminar dos tercios de ese bloque



no equivale a eliminar dos tercios del prompt ni a reducir en esa proporción una



factura. La cobertura crítica de estos tres fixtures es 100% en ambas referencias.







## Verificación y continuidad







8 pruebas nuevas PASS. Se comparan con los constructores oficiales offline, con



texto español, japonés, emoji, código, líneas CRLF y marcadores de tokens especiales



tratados como texto ordinario. También se prueban fallback, corrupción de datos,



pérdida deliberada de contexto (rechazada con salida 2) y reporte reproducible.







Evidencia local: `_tmp/memory-token-focused.xml` y



`_tmp/memory-token-benchmark/release-evidence.json`. El JSON adjunto conserva los



hashes de mensajes y fixtures, conteos, cobertura y procedencia de vocabularios.



La salida 0 acredita ejecución y suficiencia del fixture; la meta de ahorro global 40–70% del prompt completo se cumple (True) en todos los casos y en el total.







Regresión completa: **1.030 PASS, 4 SKIP, 0 fallos**, 371,039 s,



`_tmp/memory-token-full.xml`. Se conservan las 1.022 pruebas de backend anteriores.



Frontend: **34 PASS**, TypeScript/Vite aprobado. Ruff focalizado y diff aprobados.



El extra token-metrics no aparece en el export de dependencias del portable



(voice + dev). La distribución rc10 anterior se conserva sin modificaciones.



La sincronización de ambos worktrees forma parte del commit de cierre.



No se reconstruye el portable ni se añaden encoders al Coder/Reviewer o a la



facturación. Permanece pendiente evaluar calidad con modelos reales, tokenizer



específico de Qwen/DeepSeek y consumo informado por el proveedor con presupuesto



expresamente autorizado. Esta entrega no requiere usar ese presupuesto.




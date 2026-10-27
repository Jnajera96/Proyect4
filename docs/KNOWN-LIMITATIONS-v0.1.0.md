# Limitaciones conocidas — candidato v0.1.0

Fecha: 27 de octubre de 2026. Estas limitaciones forman parte de la revisión del tag.

## Entorno y distribución

- Se validó en el host de desarrollo con destinos/perfiles temporales y PATH
  reducido, no en una VM independiente ni en todos los Windows compatibles.
  Windows Sandbox no está disponible. Redistribuibles, políticas corporativas,
  antivirus y SmartScreen de otro equipo no están acreditados por esta prueba.
- EXE e instalador no tienen firma de código. El compilador Inno Setup obtenido
  del proveedor sí tenía firma válida; eso no firma el producto que compila.
- Git es una dependencia externa. Node/Python de desarrollo no hacen falta para
  iniciar el paquete; no se promete ejecutar pruebas de cualquier proyecto con
  dependencias que no estén preparadas para él.
- No hay validación de actualización sobre versiones instaladas anteriores,
  migración de esquema, reparación ni recuperación completa ante cortes del sistema.

## Modelos, voz y costes

- Analyst/Supervisor usan respaldo determinista local; los GGUF evaluados no pasaron
  todos los casos y no se habilitaron. Coder/Reviewer requieren modelo para generar
  cambios. La evaluación remota fue pequeña y en repositorios sintéticos.
- El E2E del instalador usa respuestas deterministas por HTTP local con el gateway
  real, pruebas reales y puertas intactas. No equivale a calidad de un modelo real
  ni a una prueba remota de facturación del instalador.
- Voz validada con faster-whisper small, CPU/int8 y una prueba física reportada por
  el usuario. No se valida todo acento/ruido ni CUDA. En este host faltaba una DLL
  CUDA; si se pide CUDA explícitamente, falla sin fallback silencioso.
- Pesos STT no incluidos. Configurar small o una ruta local antes de usar voz;
  large-v3 sigue siendo el ajuste general heredado y no se validó para este hardware.
- Confianza de transcripción es heurística, no probabilidad calibrada.
- Presencia de token/modelo no acredita permisos, saldo, proveedor disponible ni
  inferencia correcta. El límite de 3 USD autorizado al laboratorio no se renueva
  ni se convierte en un límite global automático de uso del producto.

## Seguridad y operación

- Producto mono-usuario en loopback. Las claves opcionales no aportan multiusuario
  ni aislamiento fuerte. No se acredita exposición pública o producción.
- El worktree limita dónde aplica cambios el sistema; no es contenedor ni VM.
  Ejecutar pruebas del repositorio ejecuta código local. El bloqueo de salida de
  red del proceso de pruebas no está implementado; el ajuste existente no lo aplica.
- El archivo de configuración privado está en el perfil de Windows, no cifrado
  por la aplicación. Los filtros redactan secretos conocidos en logs; no se ofrece
  borrado/retención general ni una garantía de sanitización de todo contenido privado.
- Cancelación de ejecución sigue devolviendo 501. El cierre ordenado puede esperar
  trabajos aceptados; no se añadió cancelación simulada ni apagado remoto.
- Promover no crea commit. No hay rollback transaccional general del producto,
  integración MCP/Graphify/Knowledge Graph/Langfuse/TTS o Jupyter dentro del runtime.
- Permanecen avisos históricos de lint ajenos a los cambios; se verificó Ruff
  focalizado. Las pruebas optativas reales omitidas se identifican en la matriz.

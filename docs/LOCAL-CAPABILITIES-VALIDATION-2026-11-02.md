# Capacidades locales — alcance y validación

Fecha: 2 de noviembre de 2026. Base limpia: `86ce801`.
Diseño: [LOCAL-CAPABILITIES-DESIGN-2026-11-02.md](LOCAL-CAPABILITIES-DESIGN-2026-11-02.md).
El usuario cambió la prioridad para terminar la sección de capacidades del README.
El nuevo portable y los pilotos quedan pausados. Rc25 y el tag v0.1.0 se conservan.

## Qué se implementó

| Capacidad | Alcance probado en las fuentes | Lo que no acredita |
| --- | --- | --- |
| Autenticación | Perfiles, claves por rol, bóveda y fronteras existentes, revalidados por regresión | Servicio público multiusuario certificado |
| Cancelación | Cooperativa, recibo, limpieza y reservas existentes; no stub 501 | Cancelación instantánea o interrupción garantizada de facturación remota |
| Aislamiento | Cuotas Windows Job; Docker con red none; rechazo nativo cuando se exige bloqueo de sockets | Firewall nativo o una VM por defecto |
| Observabilidad | Resumen y descarga de eventos SQLite correlacionados por run/trace; últimas verificaciones; tokens y coste disponible | Captura de prompts/código ni precio facturado confirmado por proveedor |
| Langfuse | Exportación manual administrativa OTLP/HTTP JSON, destinos y errores validados con HTTP simulado | Servicio instalado o recepción real independiente |
| MCP | Cliente/servidor stdio propio 2025-06-18, handshake, read_file y git_status limitado a HEAD; Researcher conectado y cuota contabilizada | Estado completo del worktree, compatibilidad MCP universal, servidores arbitrarios, escritura o shell |
| Grafo | Archivos, símbolos e importaciones Python mediante AST local; selección previa de memoria asociativa; filtro y descarga en UI | Significado inferido por LLM, grafo de llamadas universal ni Graphify externo integrado |
| TTS | Reproducción/parada voluntarias en navegador, solo voces localService=true; ausencia de voz explícita | Audición física ni disponibilidad en todos los equipos/navegadores |

No se añadieron dependencias al runtime. Los extras SDK MCP/Langfuse no son
necesarios para estas implementaciones. El cliente HTTP queda en el límite de
adapters existente (`models/providers/langfuse.py`); no se altera la sustitución
de proveedores de modelos.

## Uso y configuración

Los valores se configuran en el `.env` externo de la instalación; el paquete
no contiene secretos. En modo instalado: `%LOCALAPPDATA%/AISWESystem/config/.env`.
No se modificó el archivo privado del usuario en esta intervención.

```dotenv
AI_SWE_MCP_ENABLED=true
AI_SWE_TTS_ENABLED=true
# Opcional, solo si ya existe un servicio Langfuse preparado:
AI_SWE_LANGFUSE_ENABLED=false
AI_SWE_LANGFUSE_HOST=http://127.0.0.1:3000
AI_SWE_LANGFUSE_PUBLIC_KEY=
AI_SWE_LANGFUSE_SECRET_KEY=
```

- Reiniciar la aplicación después de configurar; los valores predeterminados de
  MCP, TTS y Langfuse permanecen desactivados.
- En Actividad, «Consultar trazas» no invoca modelos; «Descargar traza local»
  guarda JSON de metadatos. El informe se limita a 2.000 eventos e informa recorte.
- «Ver relaciones del código» analiza hasta 100 rutas que el Researcher ya leyó.
  No enumera otros proyectos/perfiles ni ejecuta el código. Permite filtrar un
  elemento y descargar relaciones. Archivos truncados/no válidos no producen
  relaciones inventadas; se informa análisis incompleto.
- Con MCP activado, hasta cinco lecturas pasan por un proceso separado, protocolo
  acotado y Policy Engine. Se rechazan secretos, rutas privadas, enlaces, escapes
  de alcance y archivos no regulares. Se leen como máximo 32 KiB por archivo.
  El hijo no recibe tokens ni PYTHONPATH del repositorio. Si falla, se escala a
  MCP_UNAVAILABLE sin fallback silencioso; no elude cuota ni puertas humanas.
  La operación git_status devuelve explícitamente scope=head_only y
  working_tree_inspected=false: consulta una referencia local con rev-parse,
  sin inspeccionar contenido ni activar filtros clean/smudge del repositorio.
- La lectura de voz se ofrece en la ficha de resultado. Solo se lee el resumen
  que el usuario decide reproducir, máximo 4.000 caracteres; se puede detener.
  No se elige una voz remota si falta una local. El reporte textual sigue disponible.
- Langfuse exige habilitación, claves, rol administrativo y confirmación explícita.
  No se envía nada al arrancar, al consultar trazas ni en el camino crítico del grafo.
  El destino remoto exige HTTPS; HTTP solo se admite en bucle local, sin credenciales
  dentro de la URL ni redirecciones. No se exportan prompts, respuestas, código,
  pruebas stdout ni nombres de perfil. Los IDs se separan por perfil.
  Se informan rechazos parciales, respuesta inválida, 401, redirección y red caída;
  el SQLite local no se borra ni cambia por esos fallos.

## Fuentes de los contratos

- [MCP stdio](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)
  y [ciclo de vida](https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle).
- [Langfuse OTLP](https://langfuse.com/integrations/native/opentelemetry): HTTP JSON,
  endpoint `/api/public/otel/v1/traces`, autenticación Basic, atributos de uso/coste
  y cabecera de ingesta v4. No se usa el endpoint legacy de ingesta.
- [Voces locales Web Speech](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesisVoice/localService).

La consulta de documentación pública fue de solo lectura; las validaciones no
llamaron a modelos, proveedores de voz ni a un Langfuse real.

## Evidencia

Las cifras y artefactos finales se registran en
`LOCAL-CAPABILITIES-EVIDENCE-2026-11-02.json`. Las pruebas de navegador usan React
real y HTTP local con voces/servicio simulados; no son una audición física.
No se mezclan los recuentos de suites solapadas para inflar el total.

## Pendientes separados

1. Incorporar las fuentes y UI a un portable posterior a rc25 y repetir su smoke.
2. Probar una voz local real y Langfuse preparado por el usuario si decide activarlos.
3. Evaluar Graphify contra el grafo nativo con repositorios representativos antes
   de adoptar un SDK/servicio adicional. No se marca Graphify como implementado.
4. Mantener pausados los pilotos de publicación GitHub y continuidad física.
5. Actualizar el remoto solo con autorización explícita; no se hizo push.

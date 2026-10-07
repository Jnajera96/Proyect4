> **Procedencia.** Documento del conjunto `AI_SWE_documentacion_actualizada`,
> derivado de la auditoría técnica externa del 2026-10-06.
> Estado: **VIGENTE**. Integrado sin modificar su contenido técnico;
> solo se añadió esta cabecera. Ver `_PROCEDENCIA.txt`.

# 13 — Prompt para iniciar M2

ACTÚA COMO ARQUITECTO E INGENIERO DE IA DEL PROYECTO.

Objetivo: iniciar M2 sin romper la infraestructura M1 verificada.

REGLAS:
1. No reemplazar LangGraph.
2. No rediseñar `RunState` salvo incompatibilidad demostrable.
3. No modificar HITL, Policy Engine o persistencia sin necesidad probada.
4. No introducir MCP, Graphify ni STT real todavía.
5. No permitir escritura del Coder en el workspace principal.
6. No introducir shell arbitrario.
7. No eliminar pruebas existentes.
8. Toda nueva funcionalidad debe incluir pruebas.
9. Todo output de LLM debe validarse con Pydantic.
10. El LLM nunca decide permisos, rutas o límites.

PRIMER ENTREGABLE:
Implementar únicamente `ModelGateway` con interfaz independiente del proveedor, configuración por entorno, structured output, timeout, retry, fallback, errores tipados, token/cost accounting, integración con Budget, redacción de secretos y tests.

NO conviertas todavía `coder`, `reviewer` ni `researcher` en agentes LLM.

Al terminar: enumera archivos modificados, explica decisiones, ejecuta tests, reporta evidencia y detente.

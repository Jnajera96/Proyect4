> **Procedencia.** Documento del conjunto `AI_SWE_documentacion_actualizada`,
> derivado de la auditoría técnica externa del 2026-10-06.
> Estado: **VIGENTE**. Integrado sin modificar su contenido técnico;
> solo se añadió esta cabecera. Ver `_PROCEDENCIA.txt`.

# 06 — Model Gateway para M2

## Objetivo
Crear una única frontera entre agentes y proveedores de modelos.

```python
class ModelGateway(Protocol):
    async def generate_structured(
        self, *, messages, response_model, role, budget
    ): ...
```

## Debe manejar
- proveedor/modelo por configuración,
- structured output,
- timeout,
- retry,
- fallback,
- errores tipados,
- conteo de tokens,
- costo cuando exista,
- budget,
- redacción de secretos,
- correlación por `run_id`/`trace_id`.

## No debe
- escribir archivos,
- ejecutar shell,
- cambiar el workflow,
- saltarse el Policy Engine,
- persistir claves en State.

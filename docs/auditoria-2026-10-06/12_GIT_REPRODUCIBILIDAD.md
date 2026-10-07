> **Procedencia.** Documento del conjunto `AI_SWE_documentacion_actualizada`,
> derivado de la auditoría técnica externa del 2026-10-06.
> Estado: **VIGENTE**. Integrado sin modificar su contenido técnico;
> solo se añadió esta cabecera. Ver `_PROCEDENCIA.txt`.

# 12 — Git y reproducibilidad

## Hallazgo a corregir
El proyecto auditado estaba sin versionar en su propio repositorio; el `.git` cercano pertenecía a otro proyecto.

## Estado deseado
```text
proyecto4-ai-swe/
├── .git/
├── src/
├── tests/
├── frontend/
└── docs/
```

## No versionar
- `.env`
- `var/state.sqlite3`
- `.venv`
- caches
- temporales
- backups de mutaciones

## Reproducibilidad mínima
Una máquina nueva debe poder clonar, seleccionar versión de Python, instalar dependencias bloqueadas, ejecutar tests, levantar API y abrir frontend con comportamiento equivalente.

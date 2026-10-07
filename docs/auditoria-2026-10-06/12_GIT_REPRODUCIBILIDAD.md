> **Procedencia.** Documento del conjunto `AI_SWE_documentacion_actualizada`,
> derivado de la auditoría técnica externa del 2026-10-06.
> Estado: **VIGENTE** (hallazgos); **RESUELTO** (los dos) — ver nota de cierre.
> Integrado sin modificar su contenido técnico; solo se añadió esta cabecera.
> Ver `_PROCEDENCIA.txt`.

> **Nota de cierre (2026-10-06, fase `F1`).** Los dos hallazgos de este documento
> están **resueltos y verificados**:
> 1. **Versionado.** El proyecto tiene repositorio propio, commit de cierre de `M1`
>    `7446bdf` y etiqueta local `m1-verified-baseline`. Sin remoto.
> 2. **Reproducibilidad.** Existe `uv.lock` (99 paquetes), `.python-version` (`3.13`)
>    y cotas superiores en `pyproject.toml`. Comprobado: un entorno reconstruido
>    desde el lockfile, en otra ubicación, reproduce **211/211** pruebas.
> Evidencia completa: [`../BASELINE-PRE-M2.md`](../BASELINE-PRE-M2.md).

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

# 12-bis — Plan de reproducibilidad (documento de trabajo)

> **Estado:** PROPUESTA, pendiente de ejecutar en la fase `F1`.
> **No se ha generado ningún lockfile todavía.** Este documento describe el
> mecanismo y su justificación, que es lo que la fase `F1` exige antes de tocar
> nada. Ver `docs/auditoria-2026-10-06/12_GIT_REPRODUCIBILIDAD.md` para el
> requisito de origen.

---

## 1. Diagnóstico del estado actual (verificado)

| Aspecto | Estado real |
|---|---|
| Versión de Python | **3.13.14** en el entorno auditado; `pyproject.toml` exige `>=3.12` |
| Fichero que fija la versión | **no existía** → se añadió `.python-version` con `3.13` en esta sesión |
| Lockfile | **no existe** |
| Fijación de versiones | **solo mínimos** (`>=`), sin techo ni pin |
| Dependencias directas | 9 base + 4 extras |
| Herramienta de gestión disponible | `uv 0.12.0` (verificado, no instalado por esta sesión) |
| Reversión de versiones durante esta sesión | **ninguna** — no se actualizó ni instaló ningún paquete |

---

## 2. Por qué hace falta un lockfile

`pyproject.toml` declara `langgraph>=0.2`. El entorno tiene **1.2.14**. Es una
versión mayor `1.x` frente a la `0.2` declarada: cambios potencialmente
rompientes de API entre ambas. Dos instalaciones en fechas distintas pueden
resolver versiones distintas de las ~10 dependencias directas y de sus
transitivas, y el proyecto no tiene forma de detectarlo.

Lo mismo aplica a `fastapi`, `pydantic` y `langgraph-checkpoint-sqlite`: todas se
declaran con mínimo abierto.

---

## 3. Mecanismo propuesto: `uv`

**Herramienta elegida: `uv`** — y el motivo es que **ya está disponible**
(`uv 0.12.0`), sin necesidad de instalar nada nuevo. `pip-compile`, `poetry` y
`pdm` no están disponibles en este entorno.

### Alternativa considerada y descartada

`pip freeze > requirements.txt` **no se usará**, aunque es lo más simple,
porque:

- congela **todo** el entorno, incluidas las dependencias ajenas al proyecto
  (`pandas`, `pymupdf`, `cairosvg`, `sqlite-vec`…) que existen por el entorno del
  agente y **no son del proyecto**;
- no distingue extras (`[voice]`, `[mcp]`, `[dev]`);
- no registra qué paquete motivó cada dependencia transitiva.

Un `requirements.txt` con 90 paquetes que nadie instaló a propósito es peor que no
tener lockfile: da la ilusión de reproducibilidad y arrastra deuda ajena.

### Comandos previstos para `F1` (NO ejecutados)

```bash
# Requiere lock total, incluidos extras. `--universal` produce un lock portable
# entre sistemas operativos.
uv lock

# Instalación reproducible a partir del lock:
uv sync --frozen --extra dev --extra voice
```

Previsiblemente `uv lock` generará `uv.lock` en la raíz. Deberá:

1. **no** fijar versiones a valores arbitrarios — debe resolver la primera
   versión compatible y **conservarla**;
2. cubrir los cuatro extras (`mcp`, `voice`, `observability`, `dev`);
3. registrarse **después** de decidir si se sube el mínimo de `langgraph` a
   `>=1.0`, porque la discrepancia `0.2` vs `1.2.14` es real y conviene que el
   manifiesto diga la verdad.

---

## 4. Punto de decisión pendiente (para el usuario)

**`langgraph>=0.2` frente a la realidad `1.2.14`.** Hay dos opciones legítimas y
la elección es del equipo, no del auditor:

- **Opción A — elevar el mínimo** a `langgraph>=1.2`. El manifiesto pasa a
  describir lo que se usa. Requiere confirmar que nada dependa de semántica de
  `0.2`.
- **Opción B — dejar `>=0.2` y confiar en el lock.** Las instalaciones con lock
  son reproducibles; las instalaciones sin lock quedan sujetas a resolución.

**Recomendación:** Opción A. Un manifiesto que declara soporte para una API que
no se ha probado nunca es una promesa sin respaldo. Pero **no se ha aplicado**:
cambiar el mínimo de una dependencia es una decisión técnica con impacto, no una
corrección documental.

---

## 5. Otros elementos de reproducibilidad

| Elemento | Estado |
|---|---|
| `.python-version` | ✅ añadido en esta sesión (`3.13`) |
| `.env.example` documenta nombres, nunca valores | ✅ ya correcto |
| `.gitignore` excluye estado y secretos | ✅ endurecido en esta sesión |
| Tests sin red ni secretos | ✅ ya cierto — 153 pruebas corren sin LLM |
| Dockerfile | 🟡 existe; **no verificado** en esta sesión (no se construyó la imagen) |
| docker-compose | 🟡 existe; **no verificado** |

---

## 6. Criterio de término de `F1`

Una máquina nueva debe poder:

1. clonar el repositorio,
2. leer `.python-version` y seleccionar Python 3.13,
3. `uv sync --frozen` (más extras),
4. `pytest` → 153 aprobadas,
5. `python tools/verify_m1_assumptions.py` → 5/5,
6. levantar la API y abrir el frontend con comportamiento equivalente.

Ninguno de estos pasos se ha ejecutado sobre una máquina limpia; la fase `F1`
termina cuando se haya hecho **al menos una vez**.

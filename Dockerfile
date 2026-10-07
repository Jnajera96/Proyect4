# Imagen del sistema. Sirve para dos cosas distintas:
#   1. Reproducibilidad del entorno.
#   2. Aislamiento de la ejecucion de codigo (docs/02-tecnologias.md, seccion 13).
#
# El aislamiento es una capa de seguridad, no una comodidad: la ejecucion de
# pruebas y la escritura de archivos ocurren aqui dentro, sin salida de red.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencias del sistema minimas. Git es necesario porque el worktree aislado
# es el mecanismo de contencion de cambios (DEC-07).
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --upgrade pip && pip install .

# Usuario sin privilegios: el proceso no debe poder escribir fuera de su area.
RUN useradd --create-home --uid 10001 aiswe \
    && mkdir -p /app/var/workspaces \
    && chown -R aiswe:aiswe /app
USER aiswe

EXPOSE 8000

# La API no ejecuta tareas largas; los trabajadores escalan por separado (RNF-E3).
# Se usa `--factory` para no crear el almacen al importar el modulo: importarlo en
# una prueba no debe tener efectos secundarios sobre el sistema de archivos.
CMD ["uvicorn", "ai_swe.api.app:crear_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

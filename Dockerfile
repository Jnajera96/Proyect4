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

# **La interfaz por defecto es el bucle local, no todas.** `python -m ai_swe` fija
# `127.0.0.1` en una constante, por una razon que aqui vale igual: la API **no tiene
# autenticacion** (AUD-06) y una ejecucion escribe codigo y lanza pruebas. Arrancar
# en `0.0.0.0` de fabrica convierte una imagen de prototipo en un servicio abierto
# para cualquiera que alcance el puerto, y basta un `docker run -p` distraido.
#
# Exponerla es entonces una decision **explicita**, en dos pasos: `AI_SWE_HOST=0.0.0.0`
# dentro del contenedor (lo hace `docker-compose.yml`, que ademas publica el puerto
# solo en el bucle local del host) y, si de verdad va a escuchar en una interfaz de
# red, la autenticacion que hoy no existe. El README lo dice.
ENV AI_SWE_HOST=127.0.0.1

# La API no ejecuta tareas largas; los trabajadores escalan por separado (RNF-E3).
# Se usa `--factory` para no crear el almacen al importar el modulo: importarlo en
# una prueba no debe tener efectos secundarios sobre el sistema de archivos.
CMD ["sh", "-c", "uvicorn ai_swe.api.app:crear_app --factory --host \"$AI_SWE_HOST\" --port 8000"]

# Imagen del ejecutor

Desde el repositorio utiliza `python tools/build_docker_runner.py --iidfile <ruta-nueva>`.
El constructor prepara un contexto mínimo e incluye el detector canónico de
`src/ai_swe/tools/dependency_detector.py`; no dupliques ese archivo en esta carpeta.

La receta copiada al portable ya contiene el detector y admite `docker build`
directamente sobre `tools/docker-runner`. El protocolo 2 requiere reconstruir
las imágenes anteriores; no se modifica automáticamente la configuración privada.

Inventario fijado: pytest 9.1.1, Ruff 0.16.10, iniconfig 2.3.1, packaging 26.3,
pluggy 1.6.0 y Pygments 2.21.0. No contiene FastAPI/Uvicorn ni instala paquetes
durante los tests. Ver `docs/PROJECT-DEPENDENCIES-VALIDATION.md` para los límites
y la aprobación explícita de dependencias adicionales.

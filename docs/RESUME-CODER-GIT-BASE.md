# Punto seguro — bloqueo Git antes del Coder

Pausado a petición del usuario para continuar mañana. Base anterior: `0964657`, rama `feature/v0.2.0-madre-continuity`. El commit que contiene este documento guarda el diagnóstico y la corrección; no acredita generación remota nueva ni cierre de producción.

## Diagnóstico verificado, sin modificar datos del usuario

Se leyeron las bases de AISWESystem en modo SQLite `mode=ro`, recuperando el checkpoint final de LangGraph (el `state_json` de runs contiene el estado inicial y no sirve como estado final). No se abrieron bóvedas, no se copiaron credenciales y no se hizo inferencia.

Última ejecución encontrada en esta PC: `run-86d60158f3e8`, `needs_human`, **0 llamadas al modelo**, sin propuesta. Su preflight emitió `SANDBOX_NO_REPO`, seguido por un error secundario `CODER_PRODUCED_NO_CHANGES`.

Ruta elegida: `%USERPROFILE%/Desktop/prueba_proyecto_asia`. Git confirma que es una raíz con `.git`, pero `git rev-parse --verify HEAD^{commit}` falla: **no tiene commit inicial**. Ese es el motivo concreto por el que no se puede crear el worktree, no una negativa del modelo.

Clon válido comprobado: `%USERPROFILE%/Desktop/prueba_proyecto_asia/Proyect_4`. Git confirma raíz correcta y HEAD de commit `e7050ade83fea274f2cb3c5542b60d544ba00332`. No se cambió el registro del proyecto ni se creó un commit en ninguna de estas carpetas del usuario.

El run anterior `run-ac30709688ca` es otro caso: sí tuvo una llamada y una respuesta vacía. No confundirlo con el último bloqueo, que ocurrió antes de llamar al modelo.

## Corrección guardada

- `graph/model_routing.py`: el preflight distingue raíz Git inválida de raíz válida sin HEAD. La segunda recibe `SANDBOX_NO_BASE_COMMIT`, con explicación y opciones de seleccionar el clon válido o usar «Nuevo proyecto Git» en otra carpeta.
- `graph/nodes.py`: si el estado ya es terminal después de Coder, el router pasa a `finalize`. Así conserva la causa original y no añade un error engañoso de propuesta vacía ni intenta aplicar una propuesta tras un bloqueo.
- Regresión actualizada: repositorios con metadatos falsos y sin HEAD se detienen antes de construir gateway, con una sola causa apropiada y cero llamadas.

## Evidencia

- **54 pruebas focalizadas PASS**, sin omisiones, errores ni fallos: calculadora, builder E2E offline y Coder. XML local `_tmp/git-base-preflight-suite.xml`.
- Ruff de `model_routing.py` y las pruebas modificadas aprobado. `nodes.py` conserva deuda previa de lint; no se declara limpio todo ese archivo.
- TypeScript/Vite compilaron al empaquetar.
- **9 comprobaciones focalizadas del paquete aprobadas** con su Python embebido: imports, raíz sin HEAD, bloqueo sin gateway/Coder, causa única, ruta terminal, aceptación tras un commit creado solo en fixture temporal, igualdad de fuentes empaquetadas, manifiesto completo e integridad ZIP. Informe durable: `docs/evidence/git-base/portable-report.json`.
- No se repitió el smoke HTTP completo de 14 controles ni toda la suite del producto para este candidato. El candidato anterior conserva esa evidencia por separado.

Portable nuevo: `dist/windows-v0.2.0-git-base-rc1/AISWESystem-windows-x64.zip`.

SHA256: `e6e661a442c9a1e6fd54cdb2fbedd09600c49ccc7f5824008b44b7f8e0648e79`.

## Continuar mañana

1. Verificar HEAD y árbol limpio; leer esta acta antes de repetir diagnósticos.
2. Pedir al usuario registrar/seleccionar la carpeta del clon **Proyect_4**, no la superior, o crear un proyecto nuevo con la opción explícita que genera su base inicial. No modificar su Git ni su base de perfiles automáticamente.
3. Confirmar qué paquete/proceso está utilizando; cerrar el anterior antes de abrir otro. El nuevo diagnóstico no cambia los resultados históricos ni corrige rutas ya guardadas.
4. Verificar una tarea nueva con requisitos concretos. Si Codex debe iniciar inferencia remota, obtener nueva autorización de gasto primero: el laboratorio anterior sigue prácticamente reservado (2.99999104 de 3 USD). No renovar ni reiniciar ese ledger.
5. Evaluar después mejoras tempranas de preparación/validación de proyectos sin commit, con autorización explícita para mutar repositorios existentes. Mantener los pendientes de auditoría, aislamiento y continuidad visibles.

Estimación comunicada: aproximadamente 80 % hacia despliegue funcional local; no es una medición automática ni un porcentaje de preparación para producción pública.

# Preflight de configuración y proveedores

Fecha: 26 de octubre de 2026. Módulo 3.1 de la propuesta inspirada en MADRE.

## Alcance implementado

Diagnóstico determinista reutilizable en
`src/ai_swe/models/providers/diagnostics.py`, con CLI JSON en
`src/ai_swe/preflight.py`. La ubicación del transporte conserva la frontera HTTP
exigida por las pruebas arquitectónicas, sin cambiar sus aserciones.
No instala ni descarga modelos, no llama a generaciones, no invoca CLIs de agentes
y no escribe configuración. Usa únicamente dependencias existentes.

```powershell
python -m ai_swe.preflight
python -m ai_swe.preflight --check-remote
# Solo si se quiere comprobar un motor local configurado por separado:
python -m ai_swe.preflight --local-base-url http://127.0.0.1:8089/v1
```

La primera forma no hace peticiones de red. `--check-remote` permite únicamente un
GET de identidad a `https://huggingface.co/api/whoami-v2` cuando el perfil remoto
está configurado. El probe local solo acepta loopback literal y consulta `/health`
sin credenciales. No se siguen redirecciones ni se confía en proxies del entorno.
Un token de HF nunca se envía a un endpoint configurable.

## Perfil vigente y resultados

- Analyst y Supervisor deterministas: un servidor GGUF no es requisito y no se
  diagnostica su ausencia como error.
- Coder y Reviewer por API: se comprueba el modelo, el adapter, el Router de HF
  y la clave efectiva de `AI_SWE_MODEL_API_KEY`, la misma que usa el gateway.
- `HF_TOKEN` por sí solo no configura el runtime. Puede usarse una referencia
  `${HF_TOKEN}` en el campo de la clave del gateway según la configuración del perfil.
- Presencia de clave sin probe produce `credential_present_unverified`.
- Identidad aceptada produce `credential_validated=true`. No acredita permiso de
  inferencia, saldo, modelo disponible o calidad; `billing_verified` e
  `inference_verified` permanecen en false.
- Una indisponibilidad o límite de tasa deja la validez desconocida (`null`), en
  lugar de declarar inválido el token. Un 401/403 se informa como rechazo de
  autenticación/autorización, sin copiar el cuerpo del servidor.
- Configuración inválida en CLI genera un diagnóstico fijo sin imprimir valores
  de entrada que pudieran contener secretos.

Se consulta la presencia de la configuración instalada en
`%LOCALAPPDATA%/AISWESystem/config/.env`. La ausencia es una advertencia que no
impide el uso offline. No se crea el archivo ni se afirma que el runtime ya lo
cargue: la migración de rutas y la integración con el launcher siguen pendientes
en G/H. El preflight no se insertó como bloqueo nuevo de endpoints existentes.

## Evidencia

- 20 pruebas offline cubren modo sin red, configuración ausente o inválida,
  separación de presencia/validez, respuestas 401/403/429/503, rechazo de URLs
  locales malformadas, ausencia de credenciales en probes locales y prevención
  de redirecciones a terceros.
- Regresiones focalizadas junto al routing: 27 pruebas aprobadas.
- Un GET real de identidad aceptó el token configurado. No se exportó identidad
  de cuenta, cuerpos de respuesta o token. `inference_calls=0`.
- La configuración instalada todavía no existe en este equipo; se informó como
  advertencia. El perfil determinista no requirió GGUF.
- JSON real sanitizado: `PREFLIGHT-EVIDENCE.json`.

Suite completa final: 745 PASS, 3 SKIP, 0 FAIL en 161.201 segundos. Ruff
focalizado aprobado; la prueba arquitectónica de separación HTTP se mantuvo.
No se
declaran ejecutable, instalador, FTS5, modos nuevos, rollback ni vista cruzada.
Esos cuatro últimos módulos permanecen en backlog v0.2.0.

## Trazabilidad

La inspiración es el diagnóstico de arranque de MADRE. Se reutiliza el concepto,
sin incorporar su código ni sus envolturas de CLIs. La propuesta y las diferencias
con nuestro perfil están en `PROPUESTA-MEJORAS-INSPIRADAS-EN-MADRE.md`.

Fuentes consultadas:

- https://github.com/jossuealcacao-exe/madre
- https://github.com/jossuealcacao-exe/madre/blob/main/docs/REFERENCE.md
- https://huggingface.co/docs/hub/api
- https://huggingface.co/docs/inference-providers/en/pricing

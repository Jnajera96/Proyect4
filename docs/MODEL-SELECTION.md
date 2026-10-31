# Selección de modelos por perfil — 27 de octubre de 2026

La bóveda incluye diez rutas HF por selector y «Otro modelo» para introducir
un identificador propio. Reviewer vacío hereda Coder. Se guardan los mismos
campos API existentes (`model_name`, `reviewer_model`); sin cambios backend.

Solo `Qwen/Qwen2.5-Coder-32B-Instruct:nscale` tiene una validación real E2E
registrada aquí: `REAL-MODEL-VALIDATION.md`, promoción/aprobación, rechazo y cambios.
El selector distingue esa evidencia histórica de los nueve candidatos sin ensayo
E2E propio. No se ofrece un ranking universal ni diez modelos supuestamente probados.

Se consultó el catálogo público https://router.huggingface.co/v1/models sin token
ni inferencia. Las diez rutas seleccionadas figuraban live, con salida estructurada
declarada y precio publicado. Eso no valida permisos de cuenta, calidad de resultados,
compatibilidad del contrato completo ni acceso futuro. Snapshot acotado:
`frontend/src/lib/modelCatalog.json`; fuente completa local `_tmp/hf-public-models.json`.
Las fichas de cada modelo se enlazan desde la UI.

«Aplicar tarifas» copia los importes publicados, convierte USD/millón a USD/mil y
conserva tanto el nombre enrutado como el alias base de respuesta. Preserva otras
entradas existentes y no asigna precios inventados a nombres personalizados.
Solo se aplica con el endpoint del router HF; un endpoint propio requiere sus
propias tarifas. Seleccionar modelo o tarifas no activa roles ni realiza llamadas.

## Uso

1. Cerrar la instancia anterior antes de abrir el portable actualizado.
2. Configurar bóveda → elegir Coder y Reviewer (o «mismo que Coder»).
3. Aplicar y revisar tarifas fechadas; para modelo propio declarar su tabla manual.
4. Token propio, casillas coder/reviewer, presupuesto acumulado y máximo por corrida.
5. Guardar, crear una tarea nueva y confirmar los requisitos interpretados.

## Verificación

- TypeScript + Vite build: PASS.
- Frontend:27 PASS, incluidas preservación de nombres personalizados, herencia
  Reviewer y conversión de tarifas/alias sin perder entradas previas.
- Paquete firmado real + Chromium:10 controles PASS: ambas opciones y persistencia
  vía API, roles, token no reflejado, rechazo de precios inventados para custom,
  configuración sin tareas ni inferencia, sin errores JS.
- `_tmp/model-selection-packaged-browser/report.json` y captura custom-models.png.
- Manifiesto completo y CRC ZIP comprobados al empaquetar.
- No se repitió la suite backend: no cambió su código. No se hizo inferencia nueva,
  push, tag ni modificación de secretos/perfiles del usuario.

Portable: `dist/windows-v0.2.0-model-selector-rc1/` (hash en ZIP-INFO.json).
Backend/base5f230f4 más cambios frontend de este árbol, aún sin commit.
Los bloqueadores de `PORTABLE-v0.2.0-TEST-REPORT.md` siguen vigentes; no es producción.

ZIP entregado: `AISWESystem-v0.2.0-SELECTOR-MODELOS.zip`, 118756219 bytes.
SHA256: `6dd2fcce6f19be6c08f259686c74cfe5b893d60d66f44ac37320af7d302a8e2d`.
Manifiesto:4715 archivos verificados. CRC ZIP aprobado. No reemplaza ZIP anteriores.


## Actualización del 31 de octubre

Las diez rutas ahora tienen sondas de contrato reales documentadas en
`MODEL-ROUTE-VALIDATION-2026-10-31.md`: ocho con Coder 2/2 + Reviewer 2/2,
y DeepSeek V3.2/Qwen3 Next con Coder 1/1 + Reviewer 1/1. El selector muestra
esa evidencia y la fecha sin cambiar la bandera histórica projectValidated.
Las dos últimas no declaran esquema nativo pero aprobaron modo JSON/Pydantic;
no se presentan como fallidas sólo por sus metadatos. Falta E2E de aplicaciones
para los nueve modelos alternativos. No se recomienda un ranking por estas sondas.

# Corrección de integridad de parches multiarchivo

Fecha: 2 de noviembre de 2026. Base: `c68a646`.
Diagnóstico previo: `VIDEO-NEW-PROJECT-FAILURE-2026-11-02.md`.

## Cambios

- `_diff_unificado` delimita líneas sin LF con `\ No newline at end of file`
  y un salto de protocolo, evitando fusionar la siguiente cabecera con código.
  La marca conserva la ausencia de salto en el contenido; no lo normaliza.
- `_contar_desde_diff` ignora explícitamente metadatos de barra inversa.
- El parser conserva finales de línea físicos y distingue el lado de la marca
  EOF. Soporta archivo vacío creado frente a borrado y conserva LF/CRLF/no-LF.
- `Sandbox.escribir` y `leer` preservan bytes UTF-8 sin conversión Windows.
- `aplicar` compara SHA-256 de bytes reales después de escribir. Una discrepancia
  registra «Corrupción de parche: el SHA-256 escrito no coincide con la propuesta»
  y el archivo no se incluye como aplicado exitosamente. El motor escala antes
  de pruebas/promoción; también se controla un error al leer para verificar.
- Seguridad distingue errores del motor y pruebas/linter, ofrece su salida y
  muestra la última evidencia por objetivo para no conservar un falso fallo histórico.

## Extensión necesaria descubierta por regresión

La primera regresión completa encontró 16 fallos de promoción. El sandbox ya
contenía LF fiel, pero Git con `core.autocrlf=true` convertía la salida a CRLF:
el verificador de promoción detectaba la diferencia y revertía correctamente.
Se conservó ese verificador. La aplicación usa `core.autocrlf=input` sólo para
ese comando, sin cambiar configuración local/global. El diff conserva bytes de
las rutas que Git considera modificadas; un checkout intacto no produce cambios
espurios por sus CRLF. Se añadieron tres casos de promoción con autocrlf activo.
Las pruebas existentes de no-op, promoción, continuidad y rollback se conservaron.

El parser mantiene su alcance de reconstrucción de propuestas completas: no se
presenta como un aplicador universal de hunks arbitrarios con contexto. El control
de hash rechaza una reconstrucción que no coincida en lugar de aceptarla.

## Resultados offline

| Comprobación | Resultado |
| --- | --- |
| Comando solicitado: test_patch_integrity.py + test_f7_sandbox.py | 46 PASS / 1 SKIP |
| Ampliada: promoción, continuidad, rollback y acta Fase C | 78 PASS / 1 SKIP |
| Suite completa desde .venv | 1196 PASS / 18 SKIP |
| Suplemento Windows Job con CPython oficial firmado | 22 PASS / 0 SKIP |
| Frontend | 41 PASS, TypeScript/Vite aprobados con Node 24.22.1 |

Las cifras son conjuntos con pruebas compartidas: no se suman como casos únicos.
Las omisiones completas se enumeran en el JSON. Windows Job se comprueba con
CPython no-Store sin quitar los guards; proveedor/STT reales y symlinks sin
privilegio no se fuerzan. Docker usa la imagen local existente sin red ni descarga.

Pruebas nuevas: tres archivos con/sin LF y con CRLF; ast.parse de los Python;
comparación byte a byte y SHA; cambio entre EOF previo/nuevo y git apply --check;
vacío/borrado; corrupción espuria inyectada; promoción bajo autocrlf. La fixture
de corrupción usa monkeypatch sobre la clase porque Sandbox es frozen: no se
modificó esa propiedad de seguridad. Frontend añade fallo vigente y fallo histórico
ya superado, con renderizado real en memoria y sin backend/red.

Los comentarios y docstrings existentes de los cuatro archivos Python se
compararon estáticamente y permanecen intactos. Ruff no añade diagnósticos en
esos módulos; el archivo de pruebas nuevo aprueba Ruff.

## Entrega y límites

Corrección en fuente, sin APIs pagadas, push, cambios de credenciales ni ediciones
del proyecto/calculadora del usuario. Los worktrees se sincronizan en el commit.
**Rc24 conserva su versión anterior; no contiene esta corrección.** Queda pendiente
construir y verificar otro portable antes de distribuirla a usuarios del ZIP.
Los pilotos físicos/GitHub continúan pausados. No se infiere calidad de modelos
reales a partir de estas pruebas offline ni se modifica la estimación global.

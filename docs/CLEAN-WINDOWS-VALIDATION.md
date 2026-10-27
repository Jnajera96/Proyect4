# Validación externa pendiente — Windows independiente

Estado: **NO EJECUTADA**. Esta guía no acredita una VM ni una instalación externa.
Complementa `RELEASE-MATRIX-v0.1.0.md`; no reemplaza los reportes de este host.

## Preparación

Usar otra máquina Windows x64 o una VM independiente con instantánea inicial.
Registrar edición/build de Windows, RAM, usuario estándar, versión de Git y
navegador. La aplicación requiere Git; no instalar Python/Node para operarla.
Transferir el instalador de `dist/windows-premium-rc1/` y `SHA256SUMS.txt`.
No transferir `.env`, tokens, SQLite ni datos del desarrollador.

Comprobar el SHA256 del instalador con `Get-FileHash -Algorithm SHA256` y compararlo
con el manifiesto. Conservar cualquier resultado de antivirus/SmartScreen tal
cual aparezca. El producto no está firmado; no desactivar protecciones para
convertir un bloqueo en una prueba aprobada.

## Matriz a completar con evidencia

| Control | Resultado actual | Evidencia a guardar |
| --- | --- | --- |
| Integridad y versión del instalador | PENDIENTE | SHA256 y propiedades del archivo |
| Instalación como usuario estándar | PENDIENTE | Carpeta elegida, código de salida, ausencia de solicitud de elevación |
| Accesos de Inicio/Escritorio | PENDIENTE | Apertura desde ambos accesos creados |
| Arranque sin Python/Node | PENDIENTE | PATH de la sesión y diagnóstico `--runtime-info` |
| Primer arranque sin proveedor | PENDIENTE | Salud y aviso con campos pendientes; sin llamada remota |
| Interfaz clara/oscura y teclado | PENDIENTE | Capturas, foco, menú y ausencia de errores de navegador |
| Repositorio Git descartable | PENDIENTE | Registro, historial y conservación del original |
| Voz opcional CPU/int8 | PENDIENTE | Modelo small externo, texto editable y confirmación sin autoejecución |
| Flujo de promoción determinista | PENDIENTE | Prueba inicialmente fallida, diff/revisión, aprobación y bytes finales |
| Reinicio y SQLite | PENDIENTE | Mismo historial y puerta persistida después del cierre/reapertura |
| Desinstalación | PENDIENTE | Programa/accesos retirados y datos de usuario preservados |
| Antivirus/SmartScreen | PENDIENTE | Resultado real, sin asumir compatibilidad |

Para el flujo determinista se puede usar el arnés existente
`tools/verify_installer.py` con un intérprete de control separado y PATH reducido
para los procesos de producto. El intérprete del arnés no debe confundirse con
una dependencia del EXE. El arnés crea y retira una instalación propia, utiliza
un repositorio descartable y un fixture de modelos HTTP local. No usar un perfil
que ya tenga el producto instalado: su protección debe impedir sobreescribirlo.

No habilitar proveedores de pago ni reutilizar el token del desarrollador para
completar esta matriz. Una prueba de modelo remoto requiere autorización y límite
económico propios; no es necesaria para comprobar el fixture de promoción.

## Cierre

Registrar fecha, responsable, versiones, hashes, resultado de cada control y rutas
de evidencia en un acta nueva. Un fallo reproducible vuelve a VERIFY → FIX →
REVERIFY. Un control sin ejecutar sigue pendiente. Revisar entonces el alcance
del release y la aprobación expresa del tag local `v0.1.0`; nunca hacer push
automáticamente. La firma de código y la exposición multiusuario siguen fuera
del alcance del candidato local.

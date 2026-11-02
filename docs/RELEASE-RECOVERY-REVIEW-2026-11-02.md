# Revisión de recuperación y candidato rc23

Fecha: 2 de noviembre de 2026. Base: `b8f5022`.

## Defectos reproducidos y corregidos

1. Una integridad SQLite fallida permitía checkpoint WAL y arranque con limpieza
   de ejecuciones. Ahora se aborta antes de modificar datos y se liberan los
   recursos del ciclo de vida. No se intenta reparar ni sobrescribir la base.
2. Renombrar un perfil válido de 64 caracteres excedía el límite. Se reserva
   espacio para el sufijo, conservando el perfil original y la unicidad.
3. Base64 inválido en `/continuity/import` lanzaba NameError por un import fuera
   de alcance. Se conserva el contrato de error de continuidad 409 con explicación.
4. El nuevo valor predeterminado `rename` de `/auth/import-vault` creaba perfiles
   duplicados ante una repetición. Se recupera `error` como predeterminado;
   `rename` continúa disponible cuando se solicita expresamente. Las dos pruebas
   existentes de importación vuelven a pasar sin alterar sus expectativas.
5. Un auto-respaldo autenticado de inspección sin repositorio no podía restaurarse:
   el marcador de ausencia de repositorio se trataba como una ruta Git. Se conserva
   únicamente ese marcador en la interpretación, sin relajar mapeo de rutas reales.

La prueba nueva de API hace registro, configuración, ejecución, pausa humana,
auto-respaldo cifrado, rechazo de contraseña incorrecta e importación en otro
directorio de perfiles. Conserva run_id y estado pendiente. Es una simulación
local reproducible, no una prueba en otra PC ni un piloto de UI.

## Validación y límites de evidencia

Los XML originales se conservan en `_tmp`; el resumen persistente está en
`RELEASE-RECOVERY-EVIDENCE-2026-11-02.json`. El primer intento completo no fue
verde: 13 fallos correspondían al daemon Docker cerrado y dos al cambio de
contrato de importación. Se inició Docker Desktop existente y se repitieron
56 controles de integración, todos aprobados. No se debilitó ninguna prueba.

La nueva prueba Base64 inicialmente esperaba 400: se alineó al contrato ya
existente 409 del manejador ContinuityError, comprobando también mensaje y clase.
Las pruebas empaquetadas de API mono-perfil necesitan modo explícito; ejecutarlas
con el predeterminado de perfiles no equivale a probar esos mismos endpoints.
El smoke independiente mantiene el predeterminado instalado y sus 14 controles.

No hay nuevos diagnósticos Ruff en los cinco archivos de código/pruebas cambiados
respecto a la base. Se mantiene la deuda de estilo previa, sin refactor masivo.
El hook informó Node 24.13.0 vulnerable: se usó Node 24.22.1 existente para test/build,
sin modificar Node global ni instalar dependencias del sistema.

## Distribución

Rc20 permanece intacto; rc21 y rc22 documentan intentos intermedios y no se recomiendan.
Rc23 verifica CRC, hashes de los archivos y coincidencia byte a byte de las fuentes,
con CPython oficial firmado y sin incluir archivos privados de desarrollo.
No requiere apagar las protecciones de Windows; la compatibilidad independiente
debe verificarse en el equipo destino y no se presume a partir de este host.


## Revisión vigente — 2 de noviembre de 2026

Plan único: [PLAN-MAESTRO-CIERRE-v0.2.0.md](PLAN-MAESTRO-CIERRE-v0.2.0.md).
Acta: [RELEASE-RECOVERY-REVIEW-2026-11-02.md](RELEASE-RECOVERY-REVIEW-2026-11-02.md).
Rc23 verificado localmente; rc21/rc22 retenidos y rc20 conservado.
Backend: 1185 PASS / 4 SKIP en la regresión completa;
el último caso de restauración sin repositorio y su corrección se verificaron
además con 16 pruebas fuente y 47 pruebas del portable final.
Frontend: 39 PASS y build con Node 24.22.1; smoke: 14/14. Cero llamadas pagadas.

ZIP: `dist/windows-v0.2.0-rc23-recovery/AISWESystem-windows-x64.zip`.
SHA-256: `4754230ec1bbcbb1295c0c4b121f1fdb715ba809395744046e3b03cb97587460`.
Se corrigen cinco defectos de recuperación, sin cambiar confirmaciones humanas
ni sobrescribir perfiles. La cifra 91/100 sigue siendo una estimación informada,
no certificación de entrega. Integración Node, frontera TLS/perfiles y pilotos
independientes siguen abiertos conforme al plan; el remoto del código fuente
no constituye un piloto del asistente GitHub.

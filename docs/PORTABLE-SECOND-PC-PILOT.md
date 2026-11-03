# Piloto del portable en otra PC

Actualizado: 2 de noviembre de 2026, candidato rc25. **Piloto físico pausado**;
esta guía prepara la validación, no autoriza ni acredita su ejecución.

ZIP: `dist/Windows-v0.2.0-rc25/AISWESystem-windows-x64.zip`.
SHA-256: `323e3d97ded9b35fbd3dfcd09d6f5d3ebdea4ca6a704bb25098ecdd00833766c`.
Acta: `RELEASE-RC25-VALIDATION-2026-11-02.md`.

## Alcance

Esta guía prepara la prueba pendiente; no acredita que ya se haya realizado.
Usar un usuario de prueba, un repositorio descartable y datos sintéticos.
Conservar Smart App Control y las demás protecciones de Windows activas.
No copiar el perfil real ni compartir tokens, contraseñas o archivos de bóveda.

## Preparación

1. Transferir el ZIP indicado en el acta operativa y comparar su SHA-256:
   `Get-FileHash -LiteralPath '<ruta al ZIP>' -Algorithm SHA256`.
2. Extraer todo el ZIP a una carpeta nueva; conservar `runtime`, `packages`,
   `app` y los estáticos. Abrir `AISWESystem.cmd`.
3. Registrar versión de Windows, arquitectura y política de integridad activa.
   No requiere instalar Python o Node. Git sí es requisito para construir.
4. Crear un perfil de prueba con contraseña propia y guardar su clave de rescate
   fuera de la PC. Verificar que el perfil nuevo no tenga token heredado.

## Recorrido offline

1. Abrir la UI, comprobar el mensaje de proveedor no configurado y que permita
   usar la sesión sin colapsar. No introducir un token real para este recorrido.
2. Elegir un repositorio Git descartable con HEAD; comprobar preparación y sus
   mensajes. No usar el repositorio del proyecto ni archivos personales.
3. Crear una ejecución de inspección y verificar la pausa para confirmar
   requisitos. No se debe lanzar una inferencia remota.
4. Cerrar el launcher, abrirlo de nuevo, iniciar sesión y comprobar que la
   ejecución y su puerta humana permanecen. Registrar cualquier bloqueo Windows.
5. Para voz offline, usar pesos locales previamente preparados y verificados;
   no descargar durante el piloto. Si faltan, registrar «voz pendiente por pesos».
   Los pesos de STT no vienen dentro del portable. Seguir la sección específica
   de CPU/int8 y verificar texto editable y confirmación explícita.

## Continuidad entre equipos

1. En la PC de origen, usar únicamente el perfil y repositorio de prueba.
   Pausar antes de exportar; configurar una carpeta de auto-respaldo de prueba.
2. Exportar un `.aiswe-vault` con contraseña y transferir el archivo cifrado.
   Comprobar que existe una copia completa antes de cerrar el equipo de origen.
3. En destino, autorizar una ruta nueva vacía para reconstruir el repositorio.
   Verificar que no se sobrescriba un perfil o repositorio con trabajo existente.
4. Importar, comprobar historial, memoria, presupuesto y puerta pendiente antes
   de reanudar. La importación no debe aprobar ni ejecutar agentes por sí sola.
5. Registrar por separado restauración en perfil existente y recuperación de
   perfil perdido: la cobertura de un flujo no acredita la del otro.
6. Para promoción, usar la prueba determinista automatizada y sus fixtures. Una
   generación remota manual exige autorización y límite de gasto independientes.

## Evidencia que devolver

- Hash del ZIP, fecha, versión de Windows y Git; pasos aprobados y fallidos.
- Estado antes/después del reinicio y de la importación; texto exacto del error.
- Si hubo bloqueo SAC/CodeIntegrity, evento y archivo afectado, sin desactivar
  protecciones para lograr un aprobado.
- No enviar contraseñas, tokens, bases SQLite, claves de rescate ni respaldos.

El aislamiento de procesos/red y el cierre de producción pública siguen siendo
requisitos independientes de este piloto.

## Comandos exactos de integridad y arranque rc25

En PowerShell, ajustar las rutas del ZIP y una carpeta de destino nueva:

```powershell
$zip = 'C:\Users\usuario\Downloads\AISWESystem-windows-x64.zip'
$destino = 'C:\Users\usuario\Desktop\AISWE-rc25-piloto'
(Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash
# Comparar con el hash del acta antes de extraer. No usar -Force.
Expand-Archive -LiteralPath $zip -DestinationPath $destino
$app = Join-Path $destino 'AISWESystem'
& "$app\AISWESystem.cmd" --runtime-info
Get-AuthenticodeSignature -LiteralPath "$app\runtime\python.exe" |
    Select-Object Status,SignerCertificate
$manifest = Get-Content -LiteralPath "$app\BUNDLE-MANIFEST.json" -Raw | ConvertFrom-Json
foreach ($item in $manifest.PSObject.Properties) {
    $actual = (Get-FileHash -LiteralPath (Join-Path $app $item.Name) -Algorithm SHA256).Hash
    if ($actual -ne $item.Value) { throw "Hash incorrecto: $($item.Name)" }
}
& "$app\AISWESystem.cmd"
```

Esperado: modo `installed`, perfiles activos, frontend presente y firma válida
de Python Software Foundation. `frozen=false` es normal para CPython firmado;
el marcador de bundle activa el modo instalado. El navegador abre una URL local
`127.0.0.1` con puerto disponible. Anotar URL y cerrar con Ctrl+C en la consola,
esperando el cierre antes de reabrir. Los datos deben persistir bajo
`%LOCALAPPDATA%\AISWESystem`, fuera del ZIP extraído.

No instalar Python, Node ni paquetes para lograr el arranque. Git y el runner
Docker tienen requisitos separados; el ZIP no instala Docker ni acredita un
runtime Node para aplicaciones generadas. Conservar SAC/SmartScreen activos:
no pulsar «Ejecutar de todas formas», desbloquear archivos ni cambiar políticas
para convertir un bloqueo en aprobado. Recoger evidencia de sólo lectura:

```powershell
Get-WinEvent -LogName 'Microsoft-Windows-CodeIntegrity/Operational' -MaxEvents 20 |
    Select-Object TimeCreated,Id,Message
```

Registrar Windows edición/build x64, navegador, Git y protecciones activas.
Si no hay permiso para leer eventos, anotarlo sin elevar privilegios.

## Micrófono y Whisper CPU/int8 sin red

Con servidor cerrado y una carpeta con los pesos completos del modelo
`Systran/faster-whisper-small`, configurar sólo la consola del piloto:

```powershell
$env:AI_SWE_STT_MODEL = 'D:\Modelos\faster-whisper-small'
$env:AI_SWE_STT_DEVICE = 'cpu'
$env:AI_SWE_STT_COMPUTE_TYPE = 'int8'
$env:AI_SWE_STT_LANGUAGE = 'es'
$env:HF_HUB_OFFLINE = '1'
& "$app\AISWESystem.cmd"
```

Permitir micrófono únicamente para la URL local. En «Dictar la instrucción»,
grabar «Analiza el proyecto y muestra un resumen. No modifiques archivos»,
detener y transcribir. Editar una palabra y pulsar «Usar como instrucción».
El texto debe quedar editable sin crear una ejecución automáticamente.
Registrar fidelidad, modelo, CPU/int8 y error literal si falla. Si los pesos
están incompletos, no habilitar red ni instalar paquetes como solución implícita.
Los mocks y el smoke no prueban micrófono físico ni inferencia Whisper real.

## Precisión del piloto de bóveda

Esta sección sigue pausada hasta autorización nueva. En origen, esperar worker
inactivo y confirmar el estado completado del auto-respaldo; copiar únicamente
el `.aiswe-vault` sintético y conservar el original. Desde acceso en destino,
elegir restaurar perfil, ingresar contraseña localmente y revisar los repositorios
antes de asignar una carpeta vacía y distinta a cada uno, sin solapamientos.
Una inspección sin repositorio no requiere inventar una ruta.

Usar un nombre de perfil nuevo; repetir importación con el mismo nombre debe
rechazarse por defecto. Renombrar sólo se solicita expresamente. Antes de reanudar,
comprobar run_id, historial, memoria, presupuesto, repositorios revinculados y puerta
humana pendiente. La importación no aprueba ni ejecuta agentes. Reiniciar destino
y repetir las comprobaciones; si hay worktree, revisar base SHA y parche antes
de reanudar. Ante fallo conservar origen: no sobrescribir repositorios ni copiar
SQLite sobre un perfil activo. No enviar bóvedas o secretos con el reporte.

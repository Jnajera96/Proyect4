# Piloto del portable en otra PC

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
5. Conceder micrófono solo si se desea probar voz; comprobar texto editable y
   confirmación explícita. Los pesos de STT no vienen dentro del portable, por lo
   que una descarga inicial puede ser necesaria; registrar ese requisito.

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

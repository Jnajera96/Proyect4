# Registro, visibilidad y recuperación — 28 de octubre de 2026

## Registro: evidencia y alcance

El texto comunicado por el usuario («Usa al menos12 caracteres. Sin esta contraseña
no se puede recuperar la bóveda») era ayuda fija del formulario, no la causa del fallo.
No se dispone del error HTTP/campo concreto de su equipo; no se afirma haberlo
reproducido. Sí se reprodujo el bloqueo nativo por campos incompletos, que no dejaba
mensaje persistente dentro del formulario. Ahora ese estado indica el campo afectado.
El registro válido completo pasa en navegador fuente y portable. Se añaden:
confirmación de contraseña, Mostrar/Ocultar y mensajes seguros para nombre inválido
(sin @ ni puntos), nombre existente/reservado y fallos de escritura. No se borran
usuarios ni reservas automáticamente para fingir éxito.

## Recuperación

Desde una sesión, «Recuperación de acceso» exige la contraseña actual. Genera32bytes
aleatorios mediante secrets.token_urlsafe(32), mostrados solo en el panel abierto.
La clave envuelve el mismo DEK de la bóveda con Scrypt/AES-GCM y AAD por propietario.
El wrapper cifrado se guarda dentro de vault.json; no se guarda el código en claro.
Guardar configuración de proveedor conserva el wrapper de rescate.

«Olvidé mi contraseña» requiere nombre, código y nueva contraseña confirmada.
Se autentica la bóveda antes de escribir, se cambia la envoltura de contraseña en una
sustitución atómica y se consume el código. Se revocan todas las sesiones del proceso;
se rechaza el cambio con solicitudes/tareas activas. El login valida que su cabecera
no haya cambiado mientras esperaba el bloqueo. Un objeto desbloqueado antiguo no
puede guardar de nuevo la envoltura anterior. Sin preguntas de seguridad ni bypass.

No restaura contraseñas olvidadas antes de preparar el código. Tampoco reemplaza
un respaldo ante pérdida de archivos/equipo. Los límites de copia offline, concurrencia
entre procesos/máquinas y los defectos previos de continuidad siguen documentados;
no se promete un bloqueo distribuido ni recuperación de archivos perdidos.

## Verificación

-26 pruebas de recuperación/perfiles/aislamiento aprobadas antes del último guard.
-5 pruebas finales de recuperación aprobadas: rotación/consumo, propietario, datos
  preservados, API/sesiones, origen ajeno y solicitud activa, login/save obsoletos.
-Frontend27 PASS; TypeScript/Vite PASS; Ruff y diff--check PASS.
-Chromium fuente10 controles y portable10 controles PASS: validación visible,
  Mostrar/Ocultar, confirmación, registro, rescate, guardado de bóveda tras configurar
  rescate, recuperación desde login y conservación de credencial sintética.
-Seguridad: revisión independiente focalizada sin hallazgos críticos/importantes;
  guard de save obsoleto también revisado. Informe local `_tmp/profile-recovery-review.md`.
-El último guard se añadió antes de entregar ZIP, actualizando el módulo de la carpeta
  candidata y regenerando el manifiesto. Pre/post hash en final-source-update.json.
  Prueba con intérprete embebido confirma preservación de datos y rechazo de save
  obsoleto. No se atribuye al recorrido previo de navegador este guard añadido después.
-Sin inferencia ni cambios de perfiles/secretos reales. No se repitió la suite completa
  backend; persisten las limitaciones reportadas en PORTABLE-v0.2.0-TEST-REPORT.md.

ZIP nuevo: dist/windows-v0.2.0-recovery-rc1/ (hash en ZIP-INFO.json).
Los ZIP anteriores se conservan. Código todavía sin commit; no tag ni push.

# Perfiles locales

El launcher abre por defecto el registro y acceso por nombre de usuario y contraseña,
incluso si una configuración anterior contiene `AI_SWE_PROFILE_MODE=false`.
Usa `python -m ai_swe.launcher` desde el entorno del proyecto o `AISWESystem.cmd`
en el portable. El modo heredado solo se solicita expresamente con `--no-profiles`.
Al iniciar directamente con uvicorn, activa `AI_SWE_PROFILE_MODE=true`.
No se migran datos antiguos automáticamente.

Abre `/app/`, crea un perfil con una contraseña de al menos 12 caracteres y entra a tu espacio.
Cada persona tiene su propio historial, SQLite, worktrees, logs y bóveda cifrada.
Si olvidas la contraseña, necesitas una clave de rescate generada previamente desde
«Recuperación de acceso», confirmando tu contraseña actual. Guárdala fuera del equipo.
«Olvidé mi contraseña» permite usarla una sola vez para definir otra contraseña,
conservando la misma bóveda y datos. Después hay que generar otra clave de rescate.
Sin contraseña ni clave previamente generada, no existe un bypass de descifrado.
La clave no sustituye una copia de los archivos del perfil ante pérdida del equipo.

El registro confirma dos contraseñas y permite mostrarlas/ocultarlas. El nombre
admite letras, números, espacios, guiones y guion bajo; no es un correo electrónico.
Si ya existe, inicia sesión con él o elige otro: alargar la contraseña no libera nombres.

La carpeta por defecto es `users/` junto a la base configurada; puedes elegir otra con
`AI_SWE_PROFILES_ROOT`. Usa una carpeta fuera de los repositorios de trabajo: los repositorios
que contienen archivos internos de perfiles, o están dentro de ellos, se rechazan.

En **Configurar bóveda** guarda tu propio token HF/API, endpoint HTTPS compatible con OpenAI,
modelos y tarifas en USD. El token no vuelve a mostrarse. Un campo vacío conserva el token;
la casilla de eliminar lo borra. Los roles remotos se activan solo al declarar credencial,
tarifas, límite acumulado y máximo por ejecución. Un perfil vacío no usa claves del entorno global.

Las reservas son estimaciones locales. Antes de cada intento se reserva el resto del máximo
por ejecución; al recibir consumo conocido se contabiliza ese importe. Si el proveedor no
reporta uso o la respuesta se pierde, la reserva permanece. Esto no garantiza la factura del proveedor.

**Cerrar sesión** revoca la cookie y espera el cierre de los trabajos ya aceptados antes de
liberar su contexto. Las sesiones caducan a las 8 horas por defecto. Los datos de perfiles
protegen la separación a través de la API, no frente a administradores de Windows o programas
que ya tienen acceso a todos los archivos de la cuenta.

Para verificación local sin inferencia externa: `python tools/verify_profiles.py` comprueba
registro, acceso, salida, bóveda, ejecución/SSE y separación entre dos personas en Chromium.

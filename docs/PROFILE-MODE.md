# Perfiles locales

Activa perfiles con `AI_SWE_PROFILE_MODE=true` o inicia el launcher con `--profiles`.
La distribución instalada usa perfiles por defecto. Para conservar el modo local heredado,
configura explícitamente `AI_SWE_PROFILE_MODE=false`. No se migran datos antiguos automáticamente.

Abre `/app/`, crea un perfil con una contraseña de al menos 12 caracteres y entra a tu espacio.
Cada persona tiene su propio historial, SQLite, worktrees, logs y bóveda cifrada.
Sin la contraseña no se puede recuperar la bóveda.

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

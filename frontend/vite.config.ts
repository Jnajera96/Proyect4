import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// La aplicacion se sirve **desde el mismo origen que la API**, bajo `/app`, que es
// como la monta FastAPI (`app.mount("/app", StaticFiles(...))`). Por eso:
//
//   - `base: "/app/"` hace que los recursos construidos se pidan a `/app/assets/...`
//     y no a `/assets/...`, que no existe en el servidor.
//   - En desarrollo, `server.proxy` reenvia `/health`, `/runs`, `/projects` y
//     `/transcriptions` al backend en 127.0.0.1:8000. Sin el proxy, el navegador
//     pediria esos recursos al servidor de Vite (5173) y recibiria el `index.html`
//     de la SPA en lugar de JSON.
//
// El puerto del backend es configurable por `AI_SWE_BACKEND` para no fijar 8000.
const backend = process.env.AI_SWE_BACKEND ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  base: "/app/",
  build: {
    outDir: "dist",
    // **No se vacia `dist` antes de escribir.** El entorno de trabajo bloquea los
    // borrados en bloque: el `rmSync` con el que Vite vacia el directorio de
    // salida lo aborta, y `npm run build` -y con el todo el que dependa de el,
    // incluido `tools/verify_frontend.py`, que reconstruye antes de verificar-
    // se quedaba sin construccion posible.
    //
    // Las consecuencias estan acotadas y son peores que la alternativa:
    //   - Los ficheros viejos se quedan en `dist` (que esta ignorado por git). No
    //     se sirven: `index.html` solo referencia los del ultimo build, y Vite
    //     escribe nombres con hash nuevo.
    //   - Quien quiera un `dist` limpio lo borra a mano, fuera de la herramienta.
    //
    // Falso verde que esto evita: construir de verdad. Si algun dia el borrado
    // vuelve a estar permitido, `emptyOutDir: true` es preferible.
    emptyOutDir: false,
  },
  server: {
    port: 5173,
    proxy: {
      "/health": { target: backend, changeOrigin: true },
      "/runs": { target: backend, changeOrigin: true },
      "/projects": { target: backend, changeOrigin: true },
      "/transcriptions": { target: backend, changeOrigin: true },
    },
  },
});

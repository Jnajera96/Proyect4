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
    emptyOutDir: true,
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

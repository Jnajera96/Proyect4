import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ProfileRoot } from "./components/ProfileRoot";
import "./estilos.css";
import "./workspace.css";

// El montaje real: un unico punto de entrada. La sonda del verificador
// (`tools/verify_frontend.py`) marca el arranque como fallido si algo lanza aqui,
// de modo que un error de montaje no se confunde con "no paso nada".
const raiz = document.getElementById("root");
if (!raiz) {
  throw new Error("no existe #root en el documento");
}

createRoot(raiz).render(
  <StrictMode>
    <ProfileRoot />
  </StrictMode>,
);

import { useEffect, useState } from "react";
import type { RunState } from "../lib/contracts";
import { delivery, type LaunchGuide } from "../lib/delivery";
import { PublicarGitHubModal } from "./PublicarGitHubModal";
import { Panel } from "./ui";

export function GuiaEjecucion({ estado, projectId, puedeOperar }: {
  estado: RunState; projectId?: string; puedeOperar: boolean;
}) {
  const [guide, setGuide] = useState<LaunchGuide | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [publish, setPublish] = useState(false);
  useEffect(() => {
    let active = true;
    // A read remains read-only; preparing the launcher uses the CSRF-protected mutation.
    (async () => {
      try {
        let result = await delivery.guide(estado.run_id);
        if (active && puedeOperar && result.available && !result.prepared) result = await delivery.prepare(estado.run_id);
        if (active) setGuide(result);
      } catch (cause) { if (active) setError((cause as Error).message); }
    })();
    return () => { active = false; };
  }, [estado.run_id, puedeOperar]);
  async function launch() {
    setBusy(true); setError(""); setMessage("");
    try {
      await delivery.launch(estado.run_id);
      setMessage(guide?.kind === "web_static" ? "Se solicitó abrir tu navegador." : "Se abrió una ventana para tu aplicación. Revisa allí su resultado.");
    } catch (cause) { setError((cause as Error).message); }
    finally { setBusy(false); }
  }
  return <section className="guia-ejecucion" aria-label="Qué hacer con tu código">
    <Panel titulo="Qué hacer con tu código">
      {!guide && !error && <p role="status">Preparando las instrucciones de tu aplicación…</p>}
      {guide && <><h3>{guide.summary_es}</h3><ol>{guide.instructions.map(text => <li key={text}>{text}</li>)}</ol>
        {guide.available && <button className="primario" onClick={() => void launch()} disabled={busy || !puedeOperar}>
          {busy ? "Abriendo…" : guide.launch_action === "open_browser" ? "Abrir en el navegador" : "Ejecutar aplicación"}</button>}
        {guide.command && <details><summary>Ver el comando de inicio</summary><pre>{guide.command}</pre>
          <button onClick={() => void navigator.clipboard.writeText(guide.command).then(() => setMessage("Comando copiado.")).catch(() => setError("No se pudo copiar. Selecciona el comando manualmente."))}>Copiar comando</button></details>}
      </>}
      {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
      {projectId && puedeOperar && <button onClick={() => setPublish(true)}>🚀 Publicar en GitHub</button>}
      {publish && projectId && <PublicarGitHubModal projectId={projectId} alCerrar={() => setPublish(false)} />}
    </Panel>
  </section>;
}

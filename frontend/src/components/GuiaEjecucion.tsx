import { useEffect, useState } from "react";
import type { RunState } from "../lib/contracts";
import { delivery, type LaunchGuide } from "../lib/delivery";
import { PublicarGitHubModal } from "./PublicarGitHubModal";
import { Panel } from "./ui";

export function GuiaEjecucion({ estado, projectId, puedeOperar, alPedirCambios }: {
  estado: RunState; projectId?: string; puedeOperar: boolean; alPedirCambios: () => void;
}) {
  const [guide, setGuide] = useState<LaunchGuide | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [publish, setPublish] = useState(false);
  useEffect(() => {
    let active = true;
    setGuide(null); setError(""); setMessage(""); setPublish(false);
    // A read remains read-only; preparing the launcher uses the CSRF-protected mutation.
    (async () => {
      try {
        let result = await delivery.guide(estado.run_id);
        if (active) setGuide(result);
        if (active && puedeOperar && result.available && !result.prepared) result = await delivery.prepare(estado.run_id);
        if (active) setGuide(result);
      } catch (cause) { if (active) setError((cause as Error).message); }
    })();
    return () => { active = false; };
  }, [estado.run_id, estado.status, puedeOperar]);
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
      {estado.status === "needs_human" && (
        <p className="aviso" role="status" style={{ marginBottom: "1rem" }}>
          ⚠️ Las validaciones automáticas se detuvieron. Puedes probar el borrador bajo tu responsabilidad; aún no está aprobado ni verificado y se ejecuta en tu equipo.
        </p>
      )}
      {!guide && !error && <p role="status">Preparando las instrucciones de tu aplicación…</p>}
      <h3>Probar en local</h3>
      {guide && <><p>{guide.summary_es}</p><ol>{guide.instructions.map(text => <li key={text}>{text}</li>)}</ol>
        {guide.available && <button className="primario" onClick={() => void launch()} disabled={busy || !puedeOperar}>
          {busy ? "Abriendo…" : guide.kind === "unknown" ? "Abrir carpeta del proyecto" : "▶️ Probar en local ahora"}</button>}
        {guide.command && <details><summary>Ver el comando de inicio</summary><pre>{guide.command}</pre>
          <button onClick={() => void navigator.clipboard.writeText(guide.command).then(() => setMessage("Comando copiado.")).catch(() => setError("No se pudo copiar. Selecciona el comando manualmente."))}>Copiar comando</button></details>}
      </>}
      {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
      <h3>Decisión después de probar</h3>
      <p>Revisa el resultado y elige si quieres ajustarlo o compartirlo.</p>
      <div className="fila">
        <button disabled={!puedeOperar || !projectId || busy} onClick={alPedirCambios}>✏️ Modificar o pedir cambios</button>
        <button disabled={!puedeOperar || !projectId || busy || estado.status !== "completed" || estado.promotion_receipt?.status !== "promoted"} onClick={() => setPublish(true)}>🚀 Subir a GitHub</button>
      </div>
      {estado.status !== "completed" && <p>Para publicar, primero completa la revisión y aprueba los cambios.</p>}
      {!projectId && <p>Registra o selecciona este proyecto para pedir cambios o publicarlo.</p>}
      {publish && projectId && <PublicarGitHubModal projectId={projectId} alCerrar={() => setPublish(false)} />}
    </Panel>
  </section>;
}

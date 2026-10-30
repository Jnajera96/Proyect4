import { useState } from "react";
import { api } from "../lib/api";
import { ESTADOS_TERMINALES, type RunState } from "../lib/contracts";

export function CancelarEjecucion({ estado, puedeOperar, alActualizar }: {
  estado: RunState; puedeOperar: boolean; alActualizar: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [requested, setRequested] = useState(false);
  const receipt = estado.cancellation;
  const pending = receipt?.status === "requested" || (requested && !receipt);
  async function cancel() {
    if (!window.confirm("¿Cancelar esta ejecución y descartar su worktree no promovido? Una llamada ya enviada puede generar gasto.")) return;
    setBusy(true); setError("");
    try { const result = await api.cancelarRun(estado.run_id); setRequested(result.cancellation?.status === "requested"); alActualizar(); }
    catch (cause) { setError((cause as Error).message); }
    finally { setBusy(false); }
  }
  return <section aria-label="Cancelación de ejecución">
    {puedeOperar && !ESTADOS_TERMINALES.has(estado.status) && <button className="peligro" disabled={busy || pending} onClick={() => void cancel()}>
      {pending ? "Cancelación solicitada" : busy ? "Solicitando…" : "Solicitar cancelación"}</button>}
    {pending && <p role="status">Cancelación solicitada. La operación actual puede terminar antes de parar; todavía no hay confirmación de parada.</p>}
    {receipt?.status === "confirmed" && <p role="status">Parada confirmada. No se ejecutarán más agentes ni se promoverá esta propuesta.</p>}
    {receipt?.status === "too_late" && <p role="status">La operación ya había terminado o promovido cambios. Cancelar no revierte esa promoción.</p>}
    {receipt?.worktree_cleanup === "failed" && <p role="alert">Los agentes se detuvieron, pero no se pudo limpiar el worktree. Sus archivos se conservaron para revisión.</p>}
    {Boolean(receipt?.unresolved_reservations) && <p role="alert">Se conservan {receipt?.unresolved_reservations} reservas con consumo incierto. Cancelar no demuestra que el proveedor haya dejado de facturar.</p>}
    {error && <p role="alert">{error}</p>}
  </section>;
}

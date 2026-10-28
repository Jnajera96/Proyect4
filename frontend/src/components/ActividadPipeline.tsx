import { useEffect, useState } from "react";
import type { RunEvent, RunState } from "../lib/contracts";
import { Panel } from "./ui";

const INICIOS = new Set(["node_started", "model_request_started", "test_target_started"]);
const FINALES = new Set(["node_completed", "node_skipped", "model_response_received", "test_target_completed"]);
const texto = (valor: unknown) => typeof valor === "string" ? valor : "";
const evidencia = (e: RunEvent): Record<string, unknown> =>
  e.data.evidence && typeof e.data.evidence === "object" ? e.data.evidence as Record<string, unknown> : e.data;

/** Pair actual server events, including repeated requests/targets in review cycles. */
export function actividadesPendientes(eventos: RunEvent[]) {
  const pendientes = new Map<string, RunEvent>();
  for (const e of eventos) {
    const kind = String(e.kind);
    if (!INICIOS.has(kind) && !FINALES.has(kind)) continue;
    const familia = kind.startsWith("model_") ? "model" : kind.startsWith("test_") ? "test" : "node";
    const clave = `${familia}:${texto(e.data.node)}:${familia === "test" ? texto(e.data.target) : texto(e.data.role)}`;
    if (INICIOS.has(kind)) pendientes.set(clave, e);
    else {
      pendientes.delete(clave);
      // Completion of the containing node closes any interrupted child activity.
      if (familia === "node") for (const [k, inicio] of pendientes) {
        if (inicio.data.node === e.data.node) pendientes.delete(k);
      }
    }
  }
  return [...pendientes.values()];
}

export function descripcionActividad(e: RunEvent): string {
  const d = e.data;
  if (String(e.kind).startsWith("test_target_")) return `${texto(d.target)} en el sandbox`;
  if (d.mode === "remote" || String(e.kind).startsWith("model_")) {
    return `${texto(d.role) || texto(d.node)} · modelo remoto ${texto(d.model) || "(modelo no declarado)"} · proveedor ${texto(d.provider) || "no declarado"}`;
  }
  return `${texto(d.node)} · ${d.mode === "deterministic" ? "lógica determinista local" : "etapa del motor"}`;
}

export function ActividadPipeline({ eventos, estado, nodo }: { eventos: RunEvent[]; estado: RunState; nodo?: string }) {
  const [ahora, setAhora] = useState(Date.now);
  const activa = estado.status === "running";
  const pendientes = activa ? actividadesPendientes(eventos).filter(e => !nodo || e.data.node === nodo) : [];
  const firma = pendientes.map(e => e.seq).join(",");
  useEffect(() => {
    if (!firma) return;
    setAhora(Date.now());
    const reloj = window.setInterval(() => setAhora(Date.now()), 1000);
    return () => window.clearInterval(reloj);
  }, [firma]);
  const recientes = eventos.filter(e => (!nodo || e.data.node === nodo) &&
    (INICIOS.has(String(e.kind)) || FINALES.has(String(e.kind)))).slice(-12);
  return <Panel titulo="Actividad del motor" nota="Eventos reales del servidor. El cronómetro mide espera transcurrida; no estima un porcentaje de avance.">
    {pendientes.length ? <ul aria-label="Actividad en curso">{pendientes.map(e => <li key={e.seq}>
      <strong>{String(e.kind) === "test_target_started" ? "Ejecutando" : String(e.kind) === "model_request_started" ? "Esperando respuesta de" : "En curso:"} {descripcionActividad(e)}</strong>
      {" · "}<span className="mono">{Math.max(0, Math.floor((ahora - Date.parse(e.at)) / 1000))} s transcurridos</span>
    </li>)}</ul> : <p className="tenue">{activa ? "Esperando el siguiente evento del servidor." : "Sin actividad en curso confirmada."}</p>}
    {recientes.length ? <ol className="registro-actividad" aria-label="Actividad recibida">{recientes.map(e => <li key={e.seq}>
      <span className="mono">#{e.seq} {e.kind}</span><span>{descripcionActividad(e)}</span>
      {typeof e.data.exit_code === "number" ? <strong>Código de salida: {e.data.exit_code}</strong> : null}
      {typeof e.data.duration_ms === "number" ? <span>{e.data.duration_ms} ms</span> : null}
      {typeof e.data.reason === "string" ? <p>{e.data.reason}</p> : null}
      {String(e.kind) === "test_target_completed" ? <details><summary>Salida literal de {texto(e.data.target)}</summary>
        <p>stdout</p><pre className="salida">{texto(evidencia(e).stdout)}</pre><p>stderr</p><pre className="salida">{texto(evidencia(e).stderr)}</pre>
      </details> : null}
    </li>)}</ol> : null}
  </Panel>;
}

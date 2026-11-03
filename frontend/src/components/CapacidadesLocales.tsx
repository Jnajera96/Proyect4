import { useEffect, useRef, useState } from "react";
import { localCapabilities, descargarJson, type LocalCapabilities, type LocalTrace, type ContextGraph } from "../lib/localCapabilities";
import { Panel } from "./ui";

export function CapacidadesLocales({runId}: {runId: string}) {
  const [cap, setCap] = useState<LocalCapabilities | null>(null);
  const [trace, setTrace] = useState<LocalTrace | null>(null);
  const [graph, setGraph] = useState<ContextGraph | null>(null);
  const [selected, setSelected] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const active = useRef(true);
  useEffect(() => {
    active.current = true;
    void localCapabilities.status().then(c => {if (active.current) setCap(c);})
      .catch(() => {if (active.current) setMessage("No se pudo consultar la configuración local.");});
    return () => {active.current = false;};
  }, []);
  async function action(operation: "trace" | "graph" | "export") {
    setBusy(true); setMessage("");
    try {
      if (operation === "trace") {const data = await localCapabilities.trace(runId); if (active.current) setTrace(data);}
      if (operation === "graph") {const data = await localCapabilities.graph(runId); if (active.current) setGraph(data);}
      if (operation === "export") {
        const result = await localCapabilities.export(runId);
        if (active.current) setMessage(`Langfuse confirmó ${result.spans} etapas exportadas.`);
      }
    } catch (error) {if (active.current) setMessage((error as Error).message);}
    finally {if (active.current) setBusy(false);}
  }
  const edges = graph?.edges.filter(e => !selected || e.source === selected || e.target === selected) ?? [];
  return <Panel titulo="Trazas y relaciones locales">
    <p>Consulta metadatos de la ejecución y relaciones extraídas del código. Estas consultas no llaman a los modelos.</p>
    {cap && <p>MCP de lectura: {cap.mcp.enabled ? "habilitado" : "desactivado"}. La memoria asociativa y las trazas locales funcionan sin servicios externos.</p>}
    <div className="fila">
      <button disabled={busy} onClick={() => void action("trace")}>Consultar trazas</button>
      <button disabled={busy} onClick={() => void action("graph")}>Ver relaciones del código</button>
      <button disabled={busy || !cap?.observability.langfuse_enabled || !cap?.observability.langfuse_configured}
        onClick={() => {if (window.confirm("¿Enviar los metadatos de etapas, tokens y costes al Langfuse configurado? No se enviarán prompts ni código.")) void action("export");}}>Exportar a Langfuse</button>
    </div>
    {message && <p role="status">{message}</p>}
    {trace && <section aria-label="Traza local">
      <p>{trace.events.length} eventos. {trace.usage.input_tokens} tokens de entrada y {trace.usage.output_tokens} de salida. {trace.usage.model_calls} llamadas al modelo.</p>
      <p>Coste registrado según la tarifa configurada: {trace.usage.cost_available ? trace.usage.used_cost.toFixed(6) : "No disponible para esta traza"}.</p>
      <p>{trace.errors.length} errores del motor; {trace.verification_failures.length} objetivos de verificación con fallos registrados.</p>
      {trace.truncated && <p>Vista limitada: no representa todo el historial.</p>}
      <button onClick={() => descargarJson(trace, "traza-local.json")}>Descargar traza local</button>
    </section>}
    {graph && <section aria-label="Grafo local de contexto">
      <p>{graph.nodes.length} elementos y {graph.edges.length} relaciones extraídas. Este grafo es nativo; no utiliza Graphify.</p>
      <label>Filtrar relaciones por elemento<select value={selected} onChange={e => setSelected(e.target.value)}>
        <option value="">Todos</option>{graph.nodes.map(n => <option value={n.id} key={n.id}>{n.label}</option>)}
      </select></label>
      <ul>{edges.slice(0, 40).map((e, i) => <li key={`${e.source}:${e.target}:${i}`}>{e.source} → {e.target} ({e.kind})</li>)}</ul>
      {!edges.length && <p>No hay relaciones extraídas para esta selección.</p>}
      {(graph.truncated || edges.length > 40) && <p>Vista acotada; consulta el JSON para revisar las relaciones disponibles.</p>}
      {graph.errors.length > 0 && <p>{graph.errors.length} archivos no pudieron analizarse; el grafo no acredita una revisión completa.</p>}
      <button onClick={() => descargarJson(graph, "grafo-local.json")}>Descargar grafo local</button>
    </section>}
  </Panel>;
}

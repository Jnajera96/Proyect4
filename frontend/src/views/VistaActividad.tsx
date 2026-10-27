import { useState } from "react";
import type { RunEvent, RunState } from "../lib/contracts";
import { ETIQUETA_ESTADO } from "../lib/contracts";
import type { EstadoConexion } from "../hooks/useEventosRun";
import { Chip, EstadoVacio, Panel } from "../components/ui";
import { fechaHora } from "../lib/formato";

export function VistaActividad({ estado, eventos, conexion }: {
  estado: RunState | null; eventos: RunEvent[]; conexion: EstadoConexion;
}) {
  const [filtro, setFiltro] = useState("todos");
  const visibles = eventos.filter(e => filtro === "todos" || (filtro === "decisiones" ? e.kind === "run.awaiting_human" : filtro === "errores" ? e.kind === "run.failed" : e.kind.endsWith(".completed")));
  return <>
    <header className="pagina-titulo"><h1>Actividad en tiempo real</h1><p>Eventos recibidos del motor para la ejecución seleccionada.</p></header>
    <Panel><div className="actividad-estados">
      <div><span className="tenue">Conexión SSE</span><Chip tono={conexion === "error" ? "error" : conexion === "conectado" ? "ok" : ""}>{conexion}</Chip></div>
      <div><span className="tenue">Estado de ejecución</span><strong>{estado ? ETIQUETA_ESTADO[estado.status] : "Sin ejecución"}</strong></div>
      <div><span className="tenue">Eventos recibidos</span><strong>{eventos.length}</strong></div>
    </div><p className="tenue">La conexión y el resultado de la ejecución son independientes. Un flujo cerrado no acredita éxito.</p></Panel>
    <Panel><label htmlFor="actividad-filtro">Filtrar eventos recibidos</label>
      <select id="actividad-filtro" value={filtro} onChange={e => setFiltro(e.target.value)}>
        <option value="todos">Todos</option><option value="decisiones">Decisiones humanas</option><option value="errores">Errores</option><option value="hitos">Hitos completados</option>
      </select>
      {!estado ? <EstadoVacio titulo="Ninguna ejecución seleccionada">Selecciona una ejecución en el historial para consultar su actividad.</EstadoVacio> : visibles.length ? <ol className="registro-actividad" aria-label="Eventos de ejecución">{visibles.map(e => <li key={e.seq}><span className="mono tenue">#{e.seq}</span><strong>{e.kind}</strong><time dateTime={e.at}>{fechaHora(e.at)}</time></li>)}</ol> : <p className="tenue">No hay eventos recibidos que coincidan con este filtro.</p>}
      <p className="tenue">Se muestran los tipos, secuencias y fechas del stream real. La evidencia completa está en el detalle; no se vuelcan payloads privados a esta consola.</p>
    </Panel>
  </>;
}

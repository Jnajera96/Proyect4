/**
 * Ejecuciones: historial completo, filtro por estado y lanzamiento.
 *
 * El filtro es de cliente sobre datos que ya estan en memoria: no hay endpoint de
 * busqueda, y fingir uno que no existe seria peor que filtrar en la vista. Los
 * recuentos del filtro se cuentan sobre la lista real.
 */
import { useMemo, useState } from "react";
import type { EstadoConexion } from "../hooks/useEventosRun";
import type { Project, RunSummary } from "../lib/contracts";
import { ETIQUETA_ESTADO } from "../lib/contracts";
import { fechaHora } from "../lib/formato";
import { AccionesCompositor, Compositor, EstadoCompositor } from "../components/Compositor";
import { Chip, Esqueleto, EstadoVacio, Panel, Seccion } from "../components/ui";
import type { Health } from "../lib/contracts";

function tonoDeEstado(estado: string): "" | "ok" | "aviso" | "error" | "acento" {
  if (estado === "completed") return "ok";
  if (estado === "failed" || estado === "cancelled") return "error";
  if (estado.startsWith("awaiting")) return "aviso";
  if (estado === "needs_human") return "error";
  if (estado === "running") return "acento";
  return "";
}

export function VistaEjecuciones({
  runs,
  cargando,
  conexion,
  proyectos,
  salud,
  compositor,
  accionesCompositor,
  alSeleccionarRun,
  puedeAdministrar,
  puedeOperar,
}: {
  runs: RunSummary[];
  cargando: boolean;
  conexion: EstadoConexion;
  proyectos: Project[];
  salud: Health | null;
  compositor: EstadoCompositor;
  accionesCompositor: AccionesCompositor;
  alSeleccionarRun: (id: string) => void;
  puedeAdministrar: boolean;
  puedeOperar: boolean;
}) {
  const [busqueda, setBusqueda] = useState("");
  const [orden, setOrden] = useState("recientes");
  const [filtro, setFiltro] = useState<"todas" | "pendientes" | "en-curso" | "terminales">(
    "todas",
  );

  const porEstado = useMemo(() => {
    if (filtro === "pendientes") {
      return runs.filter((r) => r.awaiting_approval || r.status.startsWith("awaiting"));
    }
    if (filtro === "en-curso") {
      return runs.filter((r) => !r.awaiting_approval && !r.status.startsWith("awaiting") && r.status === "running");
    }
    if (filtro === "terminales") {
      return runs.filter((r) =>
        ["completed", "failed", "needs_human", "cancelled"].includes(r.status),
      );
    }
    return runs;
  }, [runs, filtro]);
  const filtradas = useMemo(() => {
    const consulta = busqueda.trim().toLocaleLowerCase();
    return porEstado.filter(r => `${r.run_id} ${r.trace_id} ${r.intent ?? ""} ${ETIQUETA_ESTADO[r.status]}`.toLocaleLowerCase().includes(consulta))
      .slice().sort((a, b) => orden === "antiguas" ? a.created_at.localeCompare(b.created_at) : orden === "errores" ? b.error_count - a.error_count : b.created_at.localeCompare(a.created_at));
  }, [porEstado, busqueda, orden]);

  return (
    <>
      <header className="pagina-titulo"><h1>Ejecuciones</h1><p>Trabajo en curso, decisiones humanas y resultados verificables.</p></header>
      <Seccion titulo="Lanzar una ejecución">
        {puedeOperar ? (
          <Compositor
            estado={compositor}
            acciones={accionesCompositor}
            proyectos={proyectos}
            salud={salud}
            puedeAdministrar={puedeAdministrar}
          />
        ) : (
          <Panel>
            <p className="tenue">
              Tu credencial es de solo lectura: no puede lanzar ejecuciones. El
              historial de abajo sí se puede consultar.
            </p>
          </Panel>
        )}
      </Seccion>

      <Seccion
        titulo="Historial"
        nota="Las ejecuciones que el listado del servidor devuelve: una página de 200 como máximo, sin paginación en el cliente."
        acciones={
          <div className="fila" role="group" aria-label="Filtro por estado">
            {(
              [
                ["todas", "todas"],
                ["pendientes", "esperando decisión"],
                ["en-curso", "en curso"],
                ["terminales", "terminadas"],
              ] as const
            ).map(([id, etiqueta]) => (
              <button
                key={id}
                className={filtro === id ? "chip-filtro activo" : "chip-filtro"}
                aria-pressed={filtro === id}
                onClick={() => setFiltro(id)}
              >
                {etiqueta}
              </button>
            ))}
          </div>
        }
      >
        <Panel>
          <div className="historial-herramientas"><div><label htmlFor="historial-busqueda">Buscar en el historial cargado</label><input id="historial-busqueda" type="search" value={busqueda} onChange={e => setBusqueda(e.target.value)} placeholder="ID, intención o estado" /></div>
            <div><label htmlFor="historial-orden">Ordenar por</label><select id="historial-orden" value={orden} onChange={e => setOrden(e.target.value)}><option value="recientes">Más recientes</option><option value="antiguas">Más antiguas</option><option value="errores">Más errores</option></select></div>
            <span className="tenue" role="status">{filtradas.length} de {runs.length} ejecuciones cargadas</span></div>
          {cargando ? (
            <Esqueleto lineas={4} />
          ) : filtradas.length ? (
            <div className="tabla-scroll"><table id="tabla-ejecuciones">
              <thead>
                <tr>
                  <th>run_id</th>
                  <th>intención</th>
                  <th>estado</th>
                  <th>creada</th>
                  <th>actualizada</th>
                  <th>errores</th>
                </tr>
              </thead>
              <tbody>
                {filtradas.map((r) => (
                  <tr
                    key={r.run_id}
                    className="clicable"
                    onClick={() => alSeleccionarRun(r.run_id)}
                    title="Abrir el detalle de esta ejecución"
                  >
                    <td><button className="sutil mono" onClick={e => { e.stopPropagation(); alSeleccionarRun(r.run_id); }}>{r.run_id}</button></td>
                    <td>{r.intent ?? "—"}</td>
                    <td>
                      <Chip tono={tonoDeEstado(r.status)}>{ETIQUETA_ESTADO[r.status]}</Chip>
                    </td>
                    <td className="tenue">{fechaHora(r.created_at)}</td>
                    <td className="tenue">{fechaHora(r.updated_at)}</td>
                    <td>{r.error_count}</td>
                  </tr>
                ))}
              </tbody>
            </table></div>
          ) : runs.length ? (
            <EstadoVacio titulo="Ninguna ejecución coincide con el filtro">
              Hay {runs.length} ejecución(es) guardada(s), pero ninguna está en el
              estado que has elegido.
            </EstadoVacio>
          ) : (
            <EstadoVacio titulo="Todavía no hay ninguna ejecución">
              Lanza una con el formulario de arriba. El progreso llegará por el flujo
              de eventos.
            </EstadoVacio>
          )}
          {conexion === "error" ? (
            <p className="aviso" role="alert">
              El flujo de eventos de la ejecución abierta se interrumpió. El estado se
              sigue releyendo del servidor.
            </p>
          ) : null}
        </Panel>
      </Seccion>
    </>
  );
}

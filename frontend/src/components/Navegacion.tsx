/**
 * Navegacion principal.
 *
 * Botones, no enlaces: no hay rutas ni historial -el estado vive en React-, y
 * fingir una URL que no existe daria un boton "atras" que no funciona. Cada boton
 * es enfocable con el teclado y anuncia cual esta activo con `aria-current`.
 */
import { ETIQUETA_ESTADO, type Project, type RunSummary } from "../lib/contracts";
import { Icono } from "./Icono";

export type VistaId =
  | "general"
  | "proyectos"
  | "ejecuciones"
  | "detalle"
  | "flujo"
  | "actividad"
  | "seguridad"
  | "sesion";

export interface ItemNav {
  id: VistaId;
  etiqueta: string;
  /** Aviso discreto: hay algo que requiere atencion en esa seccion. */
  aviso?: boolean;
}

export function Navegacion({
  vista,
  items,
  alCambiar,
  proyectos = [],
  proyectoActual,
  alProyecto,
  alCrearProyecto,
  runs = [],
  runActual,
  alRun,
}: {
  vista: VistaId;
  items: ItemNav[];
  alCambiar: (v: VistaId) => void;
  proyectos?: Project[];
  proyectoActual?: string;
  alProyecto?: (id: string) => void;
  alCrearProyecto?: () => void;
  runs?: RunSummary[];
  runActual?: string | null;
  alRun?: (id: string) => void;
}) {
  return (
    <div className="sidebar-contenido">
    <div className="marca"><span className="marca-icono"><Icono nombre="flujo" /></span><span>AI Software<span>Engineering System</span></span></div>
    <nav className="navegacion" aria-label="Secciones de la aplicación">
      {items.map((item) => {
        const activo = item.id === vista;
        return (
          <button
            key={item.id}
            type="button"
            aria-label={item.etiqueta}
            className={activo ? "nav-item activo" : "nav-item"}
            aria-current={activo ? "page" : undefined}
            onClick={() => alCambiar(item.id)}
          >
            <Icono nombre={item.id} /><span>{item.etiqueta}</span>
            {item.aviso ? (
              <span className="nav-aviso" title="Requiere tu decisión" aria-label="Requiere tu decisión" />
            ) : null}
          </button>
        );
      })}
    </nav>
    <section className="sidebar-proyectos" aria-label="Proyectos recientes">
      <div className="fila"><h2>Proyectos</h2><button className="sutil" aria-label="Crear proyecto" onClick={alCrearProyecto}>+</button></div>
      {proyectos.length ? proyectos.slice(0, 5).map(p => <button key={p.project_id}
        className={`sidebar-proyecto ${proyectoActual === p.project_id ? "seleccionado" : ""}`}
        onClick={() => alProyecto?.(p.project_id)} aria-pressed={proyectoActual === p.project_id}>
        <span className="punto" /><span>{p.name}</span>
      </button>) : <p className="tenue">Sin proyectos</p>}
      <button className="sutil" onClick={alCrearProyecto}>Ver proyectos</button>
    </section>
    <section className="sidebar-corridas" aria-label="Ejecuciones recientes">
      <h2>Actividad reciente</h2>
      {runs.slice(0, 5).map(run => <button key={run.run_id}
        className={`sidebar-run ${runActual === run.run_id ? "seleccionado" : ""}`}
        aria-label={`Abrir ejecución ${run.run_id}`} aria-pressed={runActual === run.run_id}
        onClick={() => alRun?.(run.run_id)}>
        <span className={`run-indicador ${run.status}`} aria-hidden="true" />
        <span className="sidebar-run-info"><span className="sidebar-run-id">{run.run_id}</span>
          <span className="sidebar-run-estado">{ETIQUETA_ESTADO[run.status]}</span></span>
      </button>)}
      {!runs.length ? <p className="sidebar-vacio">Tus ejecuciones aparecerán aquí.</p> : null}
    </section>
    <p className="sidebar-pie">Tu espacio de ingeniería.<br />Cada cambio, con evidencia.</p>
    </div>
  );
}

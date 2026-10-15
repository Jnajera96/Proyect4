/**
 * Navegacion principal.
 *
 * Botones, no enlaces: no hay rutas ni historial -el estado vive en React-, y
 * fingir una URL que no existe daria un boton "atras" que no funciona. Cada boton
 * es enfocable con el teclado y anuncia cual esta activo con `aria-current`.
 */
import type { Project } from "../lib/contracts";
import { Icono } from "./Icono";

export type VistaId =
  | "general"
  | "proyectos"
  | "ejecuciones"
  | "detalle"
  | "flujo"
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
}: {
  vista: VistaId;
  items: ItemNav[];
  alCambiar: (v: VistaId) => void;
  proyectos?: Project[];
  proyectoActual?: string;
  alProyecto?: (id: string) => void;
  alCrearProyecto?: () => void;
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
    <p className="sidebar-pie">Tu espacio de ingeniería.<br />Cada cambio, con evidencia.</p>
    </div>
  );
}

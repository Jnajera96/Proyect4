/**
 * Proyectos: alta, listado y detalle.
 *
 * Usa las tres capacidades que existen: `GET /projects`, `POST /projects` y
 * `GET /projects/{id}`. El detalle se **pide al servidor** en lugar de reutilizar
 * la fila de la lista: es la unica forma de que el boton "ver" compruebe de verdad
 * que el endpoint responde.
 *
 * **El historial por proyecto no se puede derivar** y no se finge: la lista de
 * ejecuciones (`RunSummary`) no lleva el proyecto con el que se lanzo. Lo que si
 * se puede hacer es lanzar contra un proyecto concreto, y comparar la ruta con la
 * que se ejecuto (eso vive en el detalle de cada ejecucion).
 */
import { useState } from "react";
import { api } from "../lib/api";
import type { Project } from "../lib/contracts";
import { fechaHora, rutaCorta } from "../lib/formato";
import { Chip, Esqueleto, EstadoVacio, Fila, Panel, Seccion } from "../components/ui";

export function VistaProyectos({
  proyectos,
  cargando,
  nombre,
  ruta,
  alCambiarNombre,
  alCambiarRuta,
  alRegistrar,
  alEjecutarContra,
  alEliminar,
  alFallo,
  puedeAdministrar,
  errorRegistro,
  registrando,
}: {
  proyectos: Project[];
  cargando: boolean;
  nombre: string;
  ruta: string;
  alCambiarNombre: (v: string) => void;
  alCambiarRuta: (v: string) => void;
  alRegistrar: (crear?: boolean) => void;
  alEjecutarContra: (projectId: string) => void;
  alEliminar?: (projectId: string) => void;
  alFallo: (causa: unknown) => string;
  puedeAdministrar: boolean;
  errorRegistro: string | null;
  registrando: boolean;
}) {
  const [nuevo, setNuevo] = useState(false);
  const [detalle, setDetalle] = useState<Project | null>(null);
  const [errorDetalle, setErrorDetalle] = useState<string | null>(null);

  async function verDetalle(id: string) {
    setErrorDetalle(null);
    try {
      setDetalle(await api.obtenerProyecto(id));
    } catch (causa) {
      setDetalle(null);
      setErrorDetalle(alFallo(causa));
    }
  }

  return (
    <>
      <header className="pagina-titulo"><h1>Proyectos</h1><p>Repositorios autorizados para tu próximo cambio.</p></header>
      {errorRegistro ? <p className="aviso" role="alert">{errorRegistro}</p> : null}
      {puedeAdministrar ? (
        <Seccion
          titulo="Registrar un proyecto"
          nota="El proyecto fija la ruta del repositorio y se valida al registrarlo, no al ejecutar."
        >
          <Panel>
            <button type="button" disabled={registrando} onClick={() => setNuevo(!nuevo)}>{nuevo ? "Usar repositorio existente" : "Nuevo proyecto Git"}</button>
            {nuevo ? <p role="note">Al crear autorizas crear esta carpeta local vacía, inicializar Git y escribir README.md y un commit inicial. Indica una ruta local absoluta, no una URL.</p> : null}
            <div className="rejilla rejilla-doble">
              <div>
                <label htmlFor="proy-nombre">Nombre</label>
                <input
                  id="proy-nombre"
                  type="text"
                  value={nombre}
                  onChange={(e) => alCambiarNombre(e.target.value)}
                  placeholder="mi-repositorio"
                />
              </div>
              <div>
                <label htmlFor="proy-ruta">Ruta del repositorio</label>
                <input
                  id="proy-ruta"
                  type="text"
                  value={ruta}
                  onChange={(e) => alCambiarRuta(e.target.value)}
                  placeholder="C:\\ruta\\al\\repositorio"
                />
              </div>
            </div>
            <Fila sep>
              <button
                className="primario"
                disabled={registrando || !nombre.trim() || !ruta.trim()}
                onClick={() => alRegistrar(nuevo)}
              >
                {registrando ? "Registrando…" : nuevo ? "Crear proyecto Git" : "Registrar"}
              </button>
              <span className="tenue">
                Registrar un proyecto es una acción de administración.
              </span>
            </Fila>
          </Panel>
        </Seccion>
      ) : (
        <div className="banner aviso" role="status">
          <span>
            Tu credencial no puede registrar proyectos: hace falta el rol
            administrador. Puedes consultar los que ya existen.
          </span>
        </div>
      )}

      <Seccion titulo="Proyectos registrados" nota="Página devuelta por el servidor (hasta 50 por defecto). No representa necesariamente el total.">
        {cargando ? (
          <Panel>
            <Esqueleto lineas={3} />
          </Panel>
        ) : proyectos.length ? (
          <div className="rejilla rejilla-doble">
            {proyectos.map((p) => (
              <Panel key={p.project_id}>
                <div className="fila">
                  <strong>{p.name}</strong>
                  <span className="tenue" style={{ marginLeft: "auto" }}>
                    {fechaHora(p.created_at)}
                  </span>
                </div>
                <p className="mono tenue" title={p.repo_path}>
                  {rutaCorta(p.repo_path)}
                </p>
                <Fila sep>
                  <button className="primario" onClick={() => alEjecutarContra(p.project_id)}>
                    Ejecutar contra este proyecto
                  </button>
                  <button className="sutil" onClick={() => void verDetalle(p.project_id)}>
                    Ver detalle
                  </button>
                  {alEliminar && puedeAdministrar ? (
                    <button
                      className="sutil"
                      style={{ color: "var(--color-peligro, #ef4444)" }}
                      title="Quita el proyecto del registro sin borrar archivos del disco"
                      onClick={() => alEliminar(p.project_id)}
                    >
                      Quitar de la lista
                    </button>
                  ) : null}
                </Fila>
              </Panel>
            ))}
          </div>
        ) : (
          <Panel>
            <EstadoVacio titulo="Sin proyectos registrados">
              Registra uno para fijar la ruta del repositorio contra la que se
              ejecuta. Sin proyecto, la ejecución usa la ruta por defecto.
            </EstadoVacio>
          </Panel>
        )}
      </Seccion>

      {detalle ? (
        <Seccion titulo="Detalle del proyecto" acciones={
          <button className="sutil" onClick={() => setDetalle(null)}>Cerrar</button>
        }>
          <Panel nota="Leído de GET /projects/{id}, no de la fila de la lista.">
            <dl className="datos">
              <dt>identificador</dt>
              <dd className="mono">{detalle.project_id}</dd>
              <dt>nombre</dt>
              <dd>{detalle.name}</dd>
              <dt>ruta</dt>
              <dd className="mono">{detalle.repo_path}</dd>
              <dt>registrado</dt>
              <dd>{fechaHora(detalle.created_at)}</dd>
            </dl>
            <Chip tono="ok">el servidor devolvió el proyecto</Chip>
          </Panel>
        </Seccion>
      ) : null}

      {errorDetalle ? (
        <p className="aviso" role="alert">
          No se pudo leer el proyecto: {errorDetalle}
        </p>
      ) : null}
    </>
  );
}

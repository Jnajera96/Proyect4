/**
 * Vista general: el panel de mando.
 *
 * Todo lo que ensena sale de datos reales: `/health`, la lista de proyectos, la
 * lista de ejecuciones y el estado de la ejecucion seleccionada. No hay metricas
 * inventadas -ni "salud del sistema" calculada, ni porcentajes de exito que nadie
 * mide-: hay cifras contadas y estados derivados de respuestas.
 */
import { useState } from "react";
import type { EstadoConexion } from "../hooks/useEventosRun";
import type { EstadoSesion } from "../lib/auth";
import type { Health, Project, RunEvent, RunState, RunSummary } from "../lib/contracts";
import { fechaHora, numero } from "../lib/formato";
import { ETIQUETA_ESTADO } from "../lib/contracts";
import { AccionesCompositor, Compositor, EstadoCompositor } from "../components/Compositor";
import { calcular, DiagramaFlujo } from "../components/DiagramaFlujo";
import { InspectorEtapa } from "../components/InspectorEtapa";
import { HistorialAprobaciones, PanelPresupuesto } from "../components/evidencia";
import { PuertaAprobacion } from "../components/PuertaAprobacion";
import { PuertaRequisitos } from "../components/PuertaRequisitos";
import { Timeline } from "../components/Timeline";
import { Chip, Esqueleto, EstadoVacio, Panel, Seccion, Tarjeta } from "../components/ui";
import { Icono } from "../components/Icono";
import { AvisoProveedor } from "../components/EstadoProveedor";
import type { VistaId } from "../components/Navegacion";

function tonoDeEstado(estado: string): "" | "ok" | "aviso" | "error" | "acento" {
  if (estado === "completed") return "ok";
  if (estado === "failed" || estado === "cancelled") return "error";
  if (estado.startsWith("awaiting")) return "aviso";
  if (estado === "needs_human") return "error";
  if (estado === "running") return "acento";
  return "";
}

export function VistaGeneral({
  salud,
  saludError,
  sesion,
  rol,
  conexion,
  proyectos,
  runs,
  estado,
  eventos = [],
  hitos,
  cargando,
  compositor,
  accionesCompositor,
  alSeleccionarRun,
  alRefrescar,
  alFallo,
  alIrA,
  puedeAdministrar,
  puedeOperar,
}: {
  salud: Health | null;
  saludError: boolean;
  sesion: EstadoSesion;
  rol: string | null;
  conexion: EstadoConexion;
  proyectos: Project[];
  runs: RunSummary[];
  estado: RunState | null;
  eventos?: RunEvent[];
  hitos: { kind: string; seq: number; at: string }[];
  cargando: boolean;
  compositor: EstadoCompositor;
  accionesCompositor: AccionesCompositor;
  alSeleccionarRun: (id: string) => void;
  alRefrescar: (id: string) => void;
  alFallo: (causa: unknown) => string;
  alIrA: (v: VistaId) => void;
  puedeAdministrar: boolean;
  puedeOperar: boolean;
}) {
  const [inspeccion, setInspeccion] = useState<{ runId: string; etapaId: string } | null>(null);
  const etapa = estado && inspeccion?.runId === estado.run_id
    ? calcular(estado, eventos).find(e => e.id === inspeccion.etapaId) : null;
  const esperando = runs.filter(r => r.awaiting_approval || r.status.startsWith("awaiting"));
  const proyecto = proyectos.find(p => p.project_id === compositor.projectId);
  return <>
    <section className="hero" aria-labelledby="hero-titulo">
      <div className="hero-formas" aria-hidden="true"><i /><i /><i /></div>
      <div className="hero-principal">
        <p className="hero-antetitulo">Convierte una idea en software</p>
        <h1 id="hero-titulo">Describe qué quieres<br className="desktop-br" /> <span className="hero-destacado">construir.</span><span className="hero-cursor" aria-hidden="true" /></h1>
        <p className="hero-texto">De la idea al cambio verificado. Analizamos los requisitos, planificamos y proponemos código. Tú decides antes de promoverlo.</p>
        {puedeOperar ? <Compositor estado={compositor} acciones={accionesCompositor}
          proyectos={proyectos} salud={salud} puedeAdministrar={puedeAdministrar} />
          : <Panel><p>Tu credencial es de solo lectura. Puedes consultar las ejecuciones.</p></Panel>}
      </div>
      <div className="hero-proceso-contenedor">
        <p className="hero-proceso-titulo">Tu idea en 3 pasos</p>
        <ol className="hero-proceso" aria-label="Cómo funciona">
          <li className="paso-violeta">
            <span className="paso-numero">1</span>
            <div className="paso-cuerpo">
              <strong>Captura tu idea</strong>
              <p>Texto o voz, siempre bajo tu control.</p>
              <div className="paso-preview paso-preview-burbuja" aria-hidden="true">
                <span className="preview-burbuja-icono"><Icono nombre="burbuja" /></span>
                <div className="preview-lineas">
                  <span className="linea-corta" />
                  <span className="linea-larga" />
                  <span className="linea-media" />
                </div>
              </div>
            </div>
          </li>
          <li className="paso-cian">
            <span className="paso-numero">2</span>
            <div className="paso-cuerpo">
              <strong>Analiza y confirma</strong>
              <p>Requisitos estructurados y validación humana.</p>
              <div className="paso-preview paso-preview-checks" aria-hidden="true">
                <div className="preview-check-fila">
                  <span className="check-circulo">✓</span>
                  <div className="preview-lineas">
                    <span className="linea-larga" />
                    <span className="linea-corta" />
                  </div>
                </div>
                <div className="preview-check-fila">
                  <span className="check-circulo">✓</span>
                  <div className="preview-lineas">
                    <span className="linea-larga" />
                    <span className="linea-corta" />
                  </div>
                </div>
              </div>
            </div>
          </li>
          <li className="paso-rosa">
            <span className="paso-numero">3</span>
            <div className="paso-cuerpo">
              <strong>El equipo trabaja</strong>
              <p>Investigación, código, pruebas y revisión.</p>
              <div className="paso-preview paso-preview-codigo" aria-hidden="true">
                <span className="code-tag">&lt;/&gt;</span>
                <div className="preview-lineas">
                  <span className="linea-media" />
                  <span className="linea-corta" />
                  <span className="linea-larga" />
                  <span className="linea-acento" />
                </div>
              </div>
            </div>
          </li>
        </ol>
      </div>
    </section>
    <AvisoProveedor configuracion={salud?.provider_configuration} />

    <section className="franja" aria-label="Estado del sistema">
      <Tarjeta rotulo="Ejecución seleccionada" valor={estado ? ETIQUETA_ESTADO[estado.status] : "Sin ejecución"}
        pie={estado ? estado.run_id : `${numero(runs.length)} en la página consultada`} tono={estado ? tonoDeEstado(estado.status) : ""} />
      <Tarjeta rotulo="Proyecto" valor={proyecto?.name ?? "Sin proyecto seleccionado"} pie={`${numero(proyectos.length)} en la página consultada`} />
      <Tarjeta rotulo="Presupuesto" valor={estado ? `${numero(estado.budget.used_tokens)} tokens` : "Sin consumo seleccionado"}
        pie={estado ? `${estado.budget.used_model_calls} llamadas al modelo` : "Se registra por ejecución"} tono="acento" />
      <Tarjeta rotulo="Acceso" valor={sesion === "autenticado" ? "Autenticado" : "Modo local sin auth"}
        pie={rol ? `Rol: ${rol}` : "El rol se muestra cuando el servidor lo informa"} tono={sesion === "autenticado" ? "ok" : ""} />
    </section>
    {saludError ? <p role="alert" className="banner error">No se pudo consultar la salud del servidor. Revisa la conexión antes de ejecutar.</p> : null}
    {esperando.length ? <div className="banner aviso" role="status"><span>{esperando.length} ejecución(es) de esta página necesitan una decisión humana.</span>
      <button className="sutil" onClick={() => alIrA("ejecuciones")}>Revisar ejecuciones</button></div> : null}

    <div className="overview-trabajo">
      <section className="panel workflow-panel" aria-label="Workflow multiagente">
        <header className="panel-cabecera"><div><h2><Icono nombre="flujo" /> Workflow multiagente</h2>
          <p className="tenue">Roles especializados. Evidencia en cada etapa.</p></div>
          {estado ? <Chip tono={tonoDeEstado(estado.status)}>{ETIQUETA_ESTADO[estado.status]}</Chip> : null}</header>
        <DiagramaFlujo estado={estado} eventos={eventos} alEtapa={e => estado && setInspeccion({ runId: estado.run_id, etapaId: e.id })} />
        {estado && etapa ? <InspectorEtapa key={estado.run_id + etapa.id} etapa={etapa} estado={estado}
          eventos={eventos} alCerrar={() => setInspeccion(null)}
          alPuerta={() => { setInspeccion(null); alIrA("detalle"); }} /> : null}
        {estado ? <button className="sutil" onClick={() => alIrA("detalle")}>Abrir detalle de la ejecución</button> : null}
      </section>
      <section className="panel actividad-panel" aria-label="Actividad de ejecución">
        <header className="panel-cabecera"><h2><Icono nombre="detalle" /> Actividad de ejecución</h2>
          <Chip tono={conexion === "conectado" ? "ok" : ""}>{conexion === "conectado" ? "En vivo" : conexion}</Chip></header>
        <Timeline hitos={hitos} />
        <p className="tenue">Solo hitos recibidos del servidor. Los ciclos completos están en el detalle.</p>
      </section>
    </div>

    {estado?.status === "awaiting_human_requirements_confirmation" ? <PuertaRequisitos key={estado.run_id}
      estado={estado} alDecidir={() => alRefrescar(estado.run_id)} alFallo={alFallo} /> : null}
    {estado?.status === "awaiting_approval" ? <PuertaAprobacion key={estado.run_id}
      estado={estado} alDecidir={() => alRefrescar(estado.run_id)} alFallo={alFallo} /> : null}
    {estado ? <div className="rejilla rejilla-doble"><PanelPresupuesto budget={estado.budget} />
      <HistorialAprobaciones aprobaciones={estado.approvals} /></div> : null}

    <Seccion titulo="Ejecuciones recientes" acciones={<button className="sutil" onClick={() => alIrA("ejecuciones")}>Ver historial</button>}>
      <Panel>{cargando ? <Esqueleto /> : runs.length ? <div className="tabla-scroll"><table id="tabla-ejecuciones">
        <thead><tr><th>Ejecución</th><th>Intención</th><th>Estado</th><th>Actualizada</th><th>Errores</th></tr></thead>
        <tbody>{runs.slice(0, 5).map(r => <tr key={r.run_id} className="clicable" onClick={() => alSeleccionarRun(r.run_id)}>
          <td><button className="sutil mono" onClick={e => { e.stopPropagation(); alSeleccionarRun(r.run_id); }}>{r.run_id}</button></td>
          <td>{r.intent ?? "Sin clasificar"}</td><td><Chip tono={tonoDeEstado(r.status)}>{ETIQUETA_ESTADO[r.status]}</Chip></td>
          <td>{fechaHora(r.updated_at)}</td><td>{r.error_count}</td></tr>)}</tbody></table></div>
        : <EstadoVacio titulo="Tu primera ejecución empieza con una idea">Escribe una instrucción arriba. Aquí podrás volver a su evidencia y resultado.</EstadoVacio>}</Panel>
    </Seccion>
  </>;
}

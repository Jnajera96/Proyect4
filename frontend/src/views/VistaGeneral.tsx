/**
 * Vista general: el panel de mando.
 *
 * Todo lo que ensena sale de datos reales: `/health`, la lista de proyectos, la
 * lista de ejecuciones y el estado de la ejecucion seleccionada. No hay metricas
 * inventadas -ni "salud del sistema" calculada, ni porcentajes de exito que nadie
 * mide-: hay cifras contadas y estados derivados de respuestas.
 */
import type { EstadoConexion } from "../hooks/useEventosRun";
import type { EstadoSesion } from "../lib/auth";
import type { Health, Project, RunState, RunSummary } from "../lib/contracts";
import { fechaHora, numero, rutaCorta } from "../lib/formato";
import { ETIQUETA_ESTADO } from "../lib/contracts";
import { AccionesCompositor, Compositor, EstadoCompositor } from "../components/Compositor";
import { DiagramaFlujo } from "../components/DiagramaFlujo";
import { HistorialAprobaciones, PanelPresupuesto } from "../components/evidencia";
import { PuertaAprobacion } from "../components/PuertaAprobacion";
import { PuertaRequisitos } from "../components/PuertaRequisitos";
import { Timeline } from "../components/Timeline";
import { Chip, Esqueleto, EstadoVacio, Panel, Seccion, Tarjeta } from "../components/ui";
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
  const esperando = runs.filter((r) => r.awaiting_approval || r.status.startsWith("awaiting"));
  const recientes = runs.slice(0, 6);

  return (
    <>
      {/* -------------------------------------------------- Franja de estado */}
      <section className="franja" aria-label="Estado del sistema">
        <Tarjeta
          rotulo="Servidor"
          valor={saludError ? "sin respuesta" : salud ? `fase ${salud.fase}` : "…"}
          pie={salud ? `${numero(salud.ejecuciones)} ejecución(es)` : "comprobando"}
          tono={saludError ? "error" : salud ? "ok" : ""}
        />
        <Tarjeta
          rotulo="Autenticación"
          valor={
            sesion === "autenticado"
              ? "activa"
              : sesion === "sin-autenticacion"
                ? "desactivada en el servidor"
                : "sin credencial"
          }
          pie={rol ? `rol: ${rol}` : sesion === "autenticado" ? "rol no expuesto por la API" : undefined}
          tono={sesion === "autenticado" ? "ok" : sesion === "sin-autenticacion" ? "" : "aviso"}
        />
        <Tarjeta
          rotulo="Flujo de eventos"
          valor={
            conexion === "conectado"
              ? "conectado"
              : conexion === "error"
                ? "interrumpido"
                : conexion === "inactivo"
                  ? "sin ejecución"
                  : conexion
          }
          pie="SSE por ejecución"
          tono={conexion === "conectado" ? "ok" : conexion === "error" ? "error" : ""}
        />
        <Tarjeta
          rotulo="Dictado por voz"
          valor={salud ? (salud.stt ? "disponible" : "no disponible") : "…"}
          pie={salud ? (salud.stt ? "adaptador listo" : "falta el extra de voz") : ""}
          tono={salud?.stt ? "ok" : ""}
        />
        <Tarjeta
          rotulo="Proyectos"
          valor={numero(proyectos.length)}
          pie={proyectos.length ? "registrados" : "ninguno todavía"}
        />
        <Tarjeta
          rotulo="Ejecuciones"
          valor={numero(runs.length)}
          pie={esperando.length ? `${esperando.length} esperando decisión` : "ninguna pendiente"}
          tono={esperando.length ? "aviso" : ""}
        />
      </section>

      {/* ------------------------------------------------------------ Avisos */}
      {esperando.length ? (
        <div className="banner aviso" role="status">
          <span>
            Hay {esperando.length} ejecución(es) detenida(s) esperando una decisión
            humana. El flujo no continúa hasta que alguien decida.
          </span>
          <button className="sutil" onClick={() => alIrA("ejecuciones")}>
            Ver las ejecuciones
          </button>
        </div>
      ) : null}
      {saludError ? (
        <div className="banner error" role="alert">
          <span>
            El servidor no responde. Lo que se ve a continuación es lo último que se
            leyó; no se puede lanzar nada nuevo.
          </span>
        </div>
      ) : null}

      {/* -------------------------------------------------------- Compositor */}
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
              Tu credencial es de solo lectura: no puede lanzar ejecuciones. Puedes
              consultar las que ya existen y su progreso.
            </p>
          </Panel>
        )}
      </Seccion>

      {/* --------------------------------------------------- Ejecución viva */}
      {estado ? (
        <Seccion
          titulo="Ejecución seleccionada"
          acciones={
            <>
              <Chip tono={tonoDeEstado(estado.status)}>
                {ETIQUETA_ESTADO[estado.status]}
              </Chip>
              <button className="sutil" onClick={() => alIrA("detalle")}>
                Ver el detalle completo
              </button>
            </>
          }
        >
          <Panel>
            <div className="fila" style={{ marginBottom: "0.75rem" }}>
              <strong className="mono">{estado.run_id}</strong>
              <span className="tenue">actualizada {fechaHora(estado.updated_at)}</span>
            </div>
            <Timeline hitos={hitos} />
          </Panel>

          {estado.status === "awaiting_human_requirements_confirmation" ? (
            <PuertaRequisitos
              estado={estado}
              alDecidir={() => alRefrescar(estado.run_id)}
              alFallo={alFallo}
            />
          ) : null}
          {estado.status === "awaiting_approval" ? (
            <PuertaAprobacion
              estado={estado}
              alDecidir={() => alRefrescar(estado.run_id)}
              alFallo={alFallo}
            />
          ) : null}

          <div className="rejilla rejilla-doble">
            <PanelPresupuesto budget={estado.budget} />
            <HistorialAprobaciones aprobaciones={estado.approvals} />
          </div>
        </Seccion>
      ) : null}

      {/* ------------------------------------------------------- Recientes */}
      <Seccion
        titulo="Ejecuciones recientes"
        acciones={
          <button className="sutil" onClick={() => alIrA("ejecuciones")}>
            Ver todas
          </button>
        }
      >
        <Panel>
          {cargando ? (
            <Esqueleto lineas={3} />
          ) : recientes.length ? (
            <table id="tabla-ejecuciones">
              <thead>
                <tr>
                  <th>run_id</th>
                  <th>intención</th>
                  <th>estado</th>
                  <th>actualizado</th>
                  <th>errores</th>
                </tr>
              </thead>
              <tbody>
                {recientes.map((r) => (
                  <tr
                    key={r.run_id}
                    className="clicable"
                    onClick={() => alSeleccionarRun(r.run_id)}
                    title="Ver esta ejecución"
                  >
                    <td className="mono">{r.run_id}</td>
                    <td>{r.intent ?? "—"}</td>
                    <td>
                      <Chip tono={tonoDeEstado(r.status)}>{ETIQUETA_ESTADO[r.status]}</Chip>
                    </td>
                    <td className="tenue">{fechaHora(r.updated_at)}</td>
                    <td>{r.error_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <EstadoVacio titulo="Todavía no hay ninguna ejecución">
              Lanza una con el formulario de arriba: aparecerá aquí con su estado y su
              progreso en vivo.
            </EstadoVacio>
          )}
        </Panel>
      </Seccion>

      {/* ------------------------------------------------------- Proyectos */}
      <Seccion
        titulo="Proyectos"
        acciones={
          <button className="sutil" onClick={() => alIrA("proyectos")}>
            Gestionar
          </button>
        }
      >
        <Panel>
          {proyectos.length ? (
            <ul className="limpia">
              {proyectos.slice(0, 5).map((p) => (
                <li key={p.project_id}>
                  <strong>{p.name}</strong>{" "}
                  <span className="tenue mono" title={p.repo_path}>
                    {rutaCorta(p.repo_path)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <EstadoVacio titulo="Sin proyectos registrados">
              Un proyecto fija la ruta del repositorio sobre el que se ejecuta. Sin
              ninguno, la ejecución usa la ruta por defecto.
            </EstadoVacio>
          )}
        </Panel>
      </Seccion>

      {/* ----------------------------------------------------------- Flujo */}
      <Seccion titulo="Flujo de la ejecución" nota="Las etapas reales del grafo, con lo que ya está hecho.">
        <Panel>
          <DiagramaFlujo estado={estado} />
        </Panel>
      </Seccion>
    </>
  );
}

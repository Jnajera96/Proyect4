/**
 * Detalle de una ejecucion: la vista mas completa del sistema.
 *
 * Organiza **todo** lo que el estado guarda, en el orden en que se necesita para
 * decidir: que se pidio, por donde va el flujo, que se propone, que se comprobo,
 * que dijo el revisor, que riesgos hay y que se decidio. Nada de lo que se ensena
 * aqui se calcula en el cliente salvo las restas de presupuesto, que son
 * aritmetica sobre campos reales.
 */
import { useState } from "react";
import { api } from "../lib/api";
import type { EstadoConexion } from "../hooks/useEventosRun";
import type { Project, RunState } from "../lib/contracts";
import { ETIQUETA_ESTADO } from "../lib/contracts";
import { fechaHora, hashCorto, rutaCorta } from "../lib/formato";
import { DiagramaFlujo } from "../components/DiagramaFlujo";
import {
  HistorialAprobaciones,
  PanelErrores,
  PanelPlan,
  PanelPresupuesto,
  PanelPruebas,
  PanelReviewer,
  PanelSeguridadRun,
  ListaHallazgos,
} from "../components/evidencia";
import { PuertaAprobacion } from "../components/PuertaAprobacion";
import { PuertaRequisitos } from "../components/PuertaRequisitos";
import { Timeline } from "../components/Timeline";
import { Chip, EstadoVacio, Panel, Seccion } from "../components/ui";
import { VisorDiff } from "../components/VisorDiff";

function tonoDeEstado(estado: string): "" | "ok" | "aviso" | "error" | "acento" {
  if (estado === "completed") return "ok";
  if (estado === "failed" || estado === "cancelled") return "error";
  if (estado.startsWith("awaiting")) return "aviso";
  if (estado === "needs_human") return "error";
  if (estado === "running") return "acento";
  if (estado === "paused") return "aviso";
  return "";
}

export function VistaDetalle({
  estado,
  hitos,
  conexion,
  proyectos,
  alRefrescar,
  alReanudar,
  alFallo,
}: {
  estado: RunState | null;
  hitos: { kind: string; seq: number; at: string }[];
  conexion: EstadoConexion;
  proyectos: Project[];
  alRefrescar: (id: string) => void;
  alReanudar: (id: string) => void;
  alFallo: (causa: unknown) => string;
}) {
  const [revirtiendo, setRevirtiendo] = useState(false);
  const [errorRollback, setErrorRollback] = useState<string | null>(null);

  if (!estado) {
    return (
      <Panel>
        <EstadoVacio titulo="Ninguna ejecución seleccionada">
          Elige una en la vista general o en el historial de ejecuciones para ver su
          detalle completo: el plan, los cambios, la evidencia de las pruebas y el
          veredicto del revisor.
        </EstadoVacio>
      </Panel>
    );
  }

  const cambio = estado.outputs.coder_output;
  const diff = estado.artifacts.diff ?? cambio?.diff ?? "";
  const proyecto = proyectos.find((p) => p.repo_path === estado.options.repo_path);

  // **Cuando la ejecucion esta en la puerta, la puerta es la vista.** La puerta ya
  // ensena el diff, la evidencia de las pruebas y el veredicto del revisor; repetir
  // esas tres secciones debajo alargaba la pagina y ponia lo mismo dos veces -lo
  // detecto la verificacion de la puerta, que contaba cuatro ejecuciones de pruebas
  // donde hay dos-. Cuando la ejecucion no esta esperando, las secciones se
  // ensenan por separado, que es cuando hacen falta.
  const enPuerta =
    estado.status === "awaiting_approval" ||
    estado.status === "awaiting_human_requirements_confirmation";

  return (
    <>
      <header className="pagina-titulo"><h1>Detalle de ejecución</h1><p>El cambio propuesto y la evidencia para decidir.</p></header>
      <nav className="detalle-nav" aria-label="Contenido de ejecución">
        {[["Resumen", "resumen"], ["Flujo", "flujo"], ["Plan", "plan"], ["Seguridad", "seguridad"], ["Presupuesto", "presupuesto"], ["Errores", "errores"]]
          .filter(([, id]) => id !== "plan" || estado.plan)
          .map(([texto, id]) => <a key={id} href={`#seccion-${id}`}>{texto}</a>)}
        {estado.final_report ? <a href="#seccion-resultado-final">Resultado</a> : null}
      </nav>
      {/* --------------------------------------------------------- Cabecera */}
      <Panel>
        <div className="fila">
          <strong className="mono">{estado.run_id}</strong>
          <Chip tono={tonoDeEstado(estado.status)}>{ETIQUETA_ESTADO[estado.status]}</Chip>
          {conexion === "conectado" ? (
            <Chip tono="acento" pulsa>
              en vivo
            </Chip>
          ) : conexion === "error" ? (
            <Chip tono="error">conexión perdida</Chip>
          ) : null}
          {estado.next_step ? (
            <span className="tenue">
              siguiente paso: <span className="mono">{estado.next_step}</span>
            </span>
          ) : null}
          {estado.status === "running" || estado.status === "planned" ? (
            <button
              id="btn-pausar"
              className="sutil"
              onClick={async () => {
                try {
                  await api.pausarRun(estado.run_id);
                  alRefrescar(estado.run_id);
                } catch (causa) {
                  setErrorRollback(alFallo(causa));
                }
              }}
            >
              Pausar ejecución
            </button>
          ) : null}
          {estado.status === "paused" ? (
            <button
              id="btn-reanudar-pausa"
              className="primario"
              onClick={async () => {
                try {
                  await api.reanudarRunPausado(estado.run_id);
                  alReanudar(estado.run_id);
                } catch (causa) {
                  setErrorRollback(alFallo(causa));
                }
              }}
            >
              Reanudar ejecución
            </button>
          ) : null}
          <button className="sutil" style={{ marginLeft: "auto" }} onClick={() => alRefrescar(estado.run_id)}>
            Releer del servidor
          </button>
        </div>
        <p className="tenue">
          creada {fechaHora(estado.created_at)} · actualizada {fechaHora(estado.updated_at)}
        </p>
      </Panel>

      {/* -------------------------------------------------------- Puertas */}
      {estado.status === "awaiting_human_requirements_confirmation" ? (
        <PuertaRequisitos
          estado={estado}
          alDecidir={() => alReanudar(estado.run_id)}
          alFallo={alFallo}
        />
      ) : null}
      {estado.status === "awaiting_approval" ? (
        <PuertaAprobacion
          estado={estado}
          alDecidir={() => alReanudar(estado.run_id)}
          alFallo={alFallo}
        />
      ) : null}

      {/* -------------------------------------------------------- Resumen */}
      <Seccion titulo="Resumen">
        <Panel>
          <dl className="datos">
            <dt>petición</dt>
            <dd className="mono">{estado.instruction.text}</dd>
            <dt>origen</dt>
            <dd>
              {estado.instruction.source}
              {estado.instruction.transcript_meta
                ? ` · dictada (${estado.instruction.transcript_meta.provider}, confianza ${(
                    estado.instruction.transcript_meta.confidence * 100
                  ).toFixed(0)}%)`
                : ""}
            </dd>
            <dt>confirmada</dt>
            <dd>{estado.instruction.confirmed_by_user ? "sí" : "todavía no"}</dd>
            <dt>intención</dt>
            <dd>
              {estado.interpretation?.intent ?? "—"}{" "}
              {estado.interpretation ? (
                <span className="tenue">
                  (confianza {(estado.interpretation.confidence * 100).toFixed(0)}%)
                </span>
              ) : null}
            </dd>
            <dt>proyecto</dt>
            <dd>
              {proyecto ? (
                <>
                  {proyecto.name}{" "}
                  <span className="tenue mono" title={proyecto.repo_path}>
                    {rutaCorta(proyecto.repo_path)}
                  </span>
                </>
              ) : estado.options.repo_path ? (
                <span className="mono" title={estado.options.repo_path}>
                  {rutaCorta(estado.options.repo_path)}{" "}
                  <span className="tenue">(sin proyecto registrado con esta ruta)</span>
                </span>
              ) : (
                "—"
              )}
            </dd>
            <dt>modo</dt>
            <dd className="mono">{estado.options.mode ?? "FULL_PROPOSAL"}</dd>
            <dt>trace</dt>
            <dd className="mono" title={estado.trace_id}>
              {hashCorto(estado.trace_id)}
            </dd>
          </dl>
        </Panel>
      </Seccion>

      {/* ---------------------------------------------------------- Flujo */}
      <Seccion titulo="Flujo">
        <Panel>
          <DiagramaFlujo estado={estado} />
        </Panel>
      </Seccion>

      {/* ------------------------------------------------------- Timeline */}
      <Seccion titulo="Progreso">
        <Panel>
          <Timeline hitos={hitos} />
        </Panel>
      </Seccion>

      {/* ----------------------------------------------------------- Plan */}
      {estado.plan ? (
        <Seccion titulo="Plan">
          <PanelPlan
            plan={estado.plan}
            indice={estado.plan_index}
            status={estado.status}
            siguiente={estado.next_step}
          />
        </Seccion>
      ) : null}

      {/* -------------------------------------------------------- Cambios */}
      {!enPuerta ? (
        <Seccion titulo="Cambios de código">
          <Panel>
            {diff.trim() ? (
              <VisorDiff texto={diff} ficheros={estado.artifacts.changed_files} />
            ) : (
              <EstadoVacio titulo="No hay ningún cambio propuesto">
                El Coder no ha producido un diff para esta ejecución.
              </EstadoVacio>
            )}
            {estado.artifacts.base_commit ? (
              <p className="tenue fila-sep">
                base: <span className="mono">{hashCorto(estado.artifacts.base_commit)}</span>
              </p>
            ) : null}
          </Panel>
        </Seccion>
      ) : null}

      {/* ------------------------------------------------------- Pruebas */}
      {!enPuerta ? (
        <Seccion titulo="Pruebas">
          <PanelPruebas pruebas={estado.evidence.test_runs} />
        </Seccion>
      ) : null}

      {/* ------------------------------------------------------- Revisor */}
      {!enPuerta && estado.outputs.reviewer_output ? (
        <Seccion titulo="Revisor">
          <PanelReviewer veredicto={estado.outputs.reviewer_output} />
        </Seccion>
      ) : null}

      {/* --------------------------------------------------- Memoria MADRE */}
      {estado.historical_context?.length ? (
        <Seccion
          titulo="Memoria contextual MADRE (FTS5 local)"
          nota="Precedentes locales del mismo perfil y repositorio recuperados con BM25 sin llamadas remotas."
        >
          <Panel>
            <ul className="limpia">
              {estado.historical_context.map((hit, i) => (
                <li key={`${hit.run_id}-${hit.kind}-${i}`}>
                  <strong className="mono">{hit.run_id}</strong> · <span className="mono">{hit.kind}</span>{" "}
                  <span className="tenue">(BM25 {hit.score.toFixed(2)})</span>
                  <pre className="mono" style={{ whiteSpace: "pre-wrap", marginTop: "0.35rem" }}>
                    {hit.text}
                  </pre>
                </li>
              ))}
            </ul>
          </Panel>
        </Seccion>
      ) : null}

      {/* --------------------------------------- Auditoria Coder vs Reviewer */}
      {estado.outputs.coder_output || estado.outputs.code_proposal || estado.outputs.reviewer_output ? (
        <Seccion
          titulo="Auditoría cruzada Coder vs Reviewer"
          nota="Propuesta del Coder frente al juicio del Reviewer. Aceptar una revisión no promueve cambios sin aprobación humana explícita."
        >
          <div className="rejilla rejilla-doble">
            <Panel titulo="Propuesta del Coder">
              <p>{estado.outputs.code_proposal?.rationale ?? estado.outputs.coder_output?.rationale ?? "Sin propuesta estructurada."}</p>
              {estado.outputs.code_proposal?.files?.length ? (
                <ul className="limpia">
                  {estado.outputs.code_proposal.files.map((f, i) => (
                    <li key={`${f.path}-${i}`}>
                      <span className="mono">{f.operation}</span> · <strong className="mono">{f.path}</strong>:{" "}
                      {f.rationale}
                    </li>
                  ))}
                </ul>
              ) : estado.artifacts.changed_files.length ? (
                <ul className="limpia">
                  {estado.artifacts.changed_files.map((f) => (
                    <li key={f.path}>
                      <strong className="mono">{f.path}</strong> (+{f.added} / -{f.removed})
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="tenue">Ningún archivo modificado.</p>
              )}
            </Panel>
            <Panel titulo="Veredicto del Reviewer">
              {estado.outputs.reviewer_output ? (
                <>
                  <p>
                    Decisión: <strong className="mono">{estado.outputs.reviewer_output.decision}</strong>{" "}
                    <span className="tenue">
                      ({estado.promotion_receipt?.status === "promoted"
                        ? "promovido tras aprobación humana"
                        : "pendiente o no promovido al repositorio"})
                    </span>
                  </p>
                  <p>{estado.outputs.reviewer_output.summary}</p>
                  {estado.outputs.reviewer_output.required_fixes.length ? (
                    <>
                      <p className="rotulo">Correcciones requeridas</p>
                      <ul className="limpia">
                        {estado.outputs.reviewer_output.required_fixes.map((fix, i) => (
                          <li key={i}>{fix}</li>
                        ))}
                      </ul>
                    </>
                  ) : null}
                </>
              ) : (
                <p className="tenue">El Reviewer aún no ha emitido veredicto.</p>
              )}
            </Panel>
          </div>
        </Seccion>
      ) : null}

      {/* ----------------------------------------- Recibo y Rollback 1-Clic */}
      {estado.promotion_receipt ? (
        <Seccion
          titulo="Recibo de promoción y Rollback seguro"
          nota="Árboles Git capturados sobre las rutas promovidas sin alterar HEAD ni el índice del usuario."
        >
          <Panel>
            <dl className="datos">
              <dt>estado</dt>
              <dd className="mono">{estado.promotion_receipt.status}</dd>
              <dt>HEAD base</dt>
              <dd className="mono">{hashCorto(estado.promotion_receipt.head)}</dd>
              <dt>árbol previo</dt>
              <dd className="mono">{hashCorto(estado.promotion_receipt.pre_promotion_sha)}</dd>
              <dt>árbol promovido</dt>
              <dd className="mono">{hashCorto(estado.promotion_receipt.promoted_sha)}</dd>
              <dt>rutas</dt>
              <dd className="mono">{estado.promotion_receipt.paths.join(", ")}</dd>
            </dl>
            {estado.promotion_receipt.status === "promoted" ? (
              <div className="fila" style={{ marginTop: "0.75rem" }}>
                <button
                  id="btn-rollback"
                  disabled={revirtiendo}
                  onClick={async () => {
                    setRevirtiendo(true);
                    setErrorRollback(null);
                    try {
                      await api.revertirRun(estado.run_id);
                      alRefrescar(estado.run_id);
                    } catch (causa) {
                      setErrorRollback(alFallo(causa));
                    } finally {
                      setRevirtiendo(false);
                    }
                  }}
                >
                  {revirtiendo ? "Revirtiendo…" : "Revertir promoción en 1 clic"}
                </button>
              </div>
            ) : null}
            {errorRollback ? (
              <p className="aviso" role="alert">
                {errorRollback}
              </p>
            ) : null}
          </Panel>
        </Seccion>
      ) : null}

      {/* --------------------------------------------------- Investigador */}
      {estado.outputs.researcher_output?.findings?.length ? (
        <Seccion titulo="Investigación" nota="Evidencia reunida antes de proponer el cambio.">
          <Panel>
            <ListaHallazgos hallazgos={estado.outputs.researcher_output.findings} />
            {estado.outputs.researcher_output.unknowns?.length ? (
              <>
                <p className="rotulo">Lo que el investigador no pudo determinar</p>
                <ul className="limpia">
                  {estado.outputs.researcher_output.unknowns.map((u, i) => (
                    <li key={i}>{u}</li>
                  ))}
                </ul>
              </>
            ) : null}
          </Panel>
        </Seccion>
      ) : null}

      {/* ------------------------------------------------------ Seguridad */}
      {/* El aislamiento y los limites con los que trabajo la ejecucion. Se ensena
          **siempre**, tambien en la puerta de aprobacion -que es donde mas importa
          saberlo-, porque es informacion que la puerta no repite. */}
      <Seccion
        titulo="Seguridad"
        nota="Los límites con los que trabajó la ejecución y lo que el motor anotó sobre ellos."
      >
        <PanelSeguridadRun estado={estado} />
      </Seccion>

      {/* ----------------------------------------------------- Presupuesto */}
      <Seccion titulo="Presupuesto">
        <div className="rejilla rejilla-doble">
          <PanelPresupuesto budget={estado.budget} />
          <HistorialAprobaciones aprobaciones={estado.approvals} />
        </div>
      </Seccion>

      {/* --------------------------------------------------------- Errores */}
      <Seccion titulo="Errores">
        <PanelErrores errores={estado.errors} />
      </Seccion>

      {/* -------------------------------------------------- Resultado final */}
      {estado.final_report ? (
        <Seccion titulo="Resultado final">
          <Panel>
            <p>{estado.final_report.summary}</p>
            {estado.final_report.changes_applied?.length ? (
              <>
                <p className="rotulo">Cambios aplicados</p>
                <ul className="limpia">
                  {estado.final_report.changes_applied.map((c, i) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
              </>
            ) : null}
            {estado.final_report.tests_executed?.length ? (
              <>
                <p className="rotulo">Pruebas ejecutadas</p>
                <ul className="limpia">
                  {estado.final_report.tests_executed.map((t, i) => (
                    <li key={i}>{t}</li>
                  ))}
                </ul>
              </>
            ) : null}
            {estado.final_report.review ? (
              <>
                <p className="rotulo">Revisión</p>
                <p>{estado.final_report.review}</p>
              </>
            ) : null}
            {estado.final_report.pending?.length ? (
              <>
                <p className="rotulo">Pendiente</p>
                <ul className="limpia">
                  {estado.final_report.pending.map((p, i) => (
                    <li key={i}>{p}</li>
                  ))}
                </ul>
              </>
            ) : null}
          </Panel>
        </Seccion>
      ) : null}

      {/* --------------------------------------------------------- Avisos */}
      {estado.human_feedback?.length ? (
        <Seccion titulo="Indicaciones humanas" nota="Lo que una persona pidió al pedir cambios.">
          <Panel>
            <ul className="limpia">
              {estado.human_feedback.map((h, i) => (
                <li key={i}>{h}</li>
              ))}
            </ul>
          </Panel>
        </Seccion>
      ) : null}

      <p className="tenue">
        La cancelación de una ejecución en curso no está disponible: el endpoint
        existe pero responde 501 (no implementado), así que no se ofrece un botón que
        no puede funcionar.
      </p>
    </>
  );
}

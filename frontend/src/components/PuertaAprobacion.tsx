/**
 * Puerta 2 — aprobacion del cambio (`approval_gate`).
 *
 * Es la revision que precede a una decision humana. Muestra, en este orden, las
 * tres piezas que permiten decidir con criterio:
 *
 *   1. **El diff** del cambio propuesto (que se va a hacer).
 *   2. **La evidencia de tests** (`TestRun`): si se ejecuto, con que comando, con
 *      que codigo de salida y que imprimio. Sin evidencia, aprobar es un acto de fe.
 *   3. **El veredicto del Reviewer** (`ReviewVerdict`): que encontro y que exige.
 *
 * Los tres botones se corresponden con las tres decisiones del contrato:
 * APROBAR, SOLICITAR CAMBIOS y RECHAZAR. Se mapean a `approved`, `modified` y
 * `rejected`, que es el `ApprovalDecision` que espera `POST /runs/{id}/approve`.
 */
import { useState } from "react";
import { api, ErrorApi } from "../lib/api";
import { type RunState, type TestRun } from "../lib/contracts";
import { CabeceraFichero, Diff } from "./Diff";
import { Fila } from "./ui";

const ETIQUETA_DECISION: Record<string, string> = {
  accept: "aceptado",
  request_changes: "pide cambios",
  escalate: "escalado",
};

function EvidenciaTest({ test }: { test: TestRun }) {
  const ok = test.exit_code === 0;
  const salida = [test.stdout, test.stderr].filter(Boolean).join("\n").trim();
  return (
    <div className="test">
      <div className="test-cabecera">
        <span className={ok ? "chip ok" : "chip error"}>
          <span className="punto" />
          {ok ? "pasó" : `falló (exit ${test.exit_code})`}
        </span>
        <span className="mono">{test.target}</span>
        <span className="tenue">{test.duration_s.toFixed(2)}s</span>
      </div>
      {test.argv?.length ? (
        <p className="comando">$ {test.argv.join(" ")}</p>
      ) : null}
      {salida ? <pre className="salida">{salida}</pre> : null}
    </div>
  );
}

export function PuertaAprobacion({
  estado,
  alDecidir,
}: {
  estado: RunState;
  alDecidir: () => void;
}) {
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const diff = estado.artifacts.diff ?? estado.outputs.coder_output?.diff ?? "";
  const verdicto = estado.outputs.reviewer_output;
  const tests = estado.evidence.test_runs ?? [];

  async function decidir(decision: string) {
    setOcupado(true);
    setError(null);
    try {
      await api.aprobar(estado.run_id, decision);
      alDecidir();
    } catch (e) {
      const mensaje =
        e instanceof ErrorApi
          ? e.errorClass
            ? `${e.errorClass}: ${e.message}`
            : e.message
          : String(e);
      setError(mensaje);
    } finally {
      setOcupado(false);
    }
  }

  return (
    <section className="panel">
      <h2 className="panel-titulo">Aprobación del cambio</h2>
      <p className="panel-nota">
        Revisa el cambio propuesto, la evidencia de las pruebas y el veredicto del
        revisor antes de decidir.
      </p>

      {/* ------------------------------------------------------ Veredicto */}
      {verdicto ? (
        <>
          <h3 className="seccion-titulo">Veredicto del revisor</h3>
          <div className={`veredicto ${verdicto.decision}`}>
            <div className="fila">
              <strong>{ETIQUETA_DECISION[verdicto.decision] ?? verdicto.decision}</strong>
              <span className="tenue mono">{verdicto.decision}</span>
            </div>
            <p style={{ margin: "0.5rem 0 0" }}>{verdicto.summary}</p>
          </div>
          {verdicto.required_fixes?.length ? (
            <>
              <p className="tenue">Correcciones exigidas</p>
              <ul className="limpia">
                {verdicto.required_fixes.map((f, i) => (
                  <li key={i}>{f}</li>
                ))}
              </ul>
            </>
          ) : null}
          {verdicto.findings?.length ? (
            <>
              <p className="seccion-titulo">Hallazgos</p>
              {verdicto.findings.map((f, i) => (
                <div className="hallazgo" key={i}>
                  <span className={`sev ${f.severity}`}>{f.severity}</span>
                  <span>
                    <span className="ruta-hallazgo">
                      {f.path}
                      {f.line ? `:${f.line}` : ""}
                    </span>
                    {" — "}
                    {f.explanation}
                  </span>
                </div>
              ))}
            </>
          ) : null}
        </>
      ) : null}

      {/* ---------------------------------------------------------- Tests */}
      <h3 className="seccion-titulo">Evidencia de pruebas</h3>
      {tests.length ? (
        tests.map((t, i) => <EvidenciaTest key={i} test={t} />)
      ) : (
        <p className="vacio">No se registró ninguna ejecución de pruebas.</p>
      )}

      {/* ----------------------------------------------------------- Diff */}
      <h3 className="seccion-titulo">Cambio propuesto</h3>
      {diff ? (
        <>
          {estado.artifacts.changed_files?.length ? (
            estado.artifacts.changed_files.map((f) => (
              <div className="fichero-diff" key={f.path}>
                <CabeceraFichero ruta={f.path} added={f.added} removed={f.removed} />
              </div>
            ))
          ) : null}
          {estado.outputs.coder_output?.rationale ? (
            <p className="panel-nota" style={{ marginTop: "0.5rem" }}>
              <strong>Motivo del coder:</strong> {estado.outputs.coder_output.rationale}
            </p>
          ) : null}
          <Diff texto={diff} />
        </>
      ) : (
        <p className="vacio">No hay diff registrado para este cambio.</p>
      )}

      {/* ------------------------------------------------------- Botones */}
      <Fila sep>
        <button id="btn-aprobar" className="primario" disabled={ocupado} onClick={() => void decidir("approved")}>
          Aprobar
        </button>
        <button disabled={ocupado} onClick={() => void decidir("modified")}>
          Solicitar cambios
        </button>
        <button className="peligro" disabled={ocupado} onClick={() => void decidir("rejected")}>
          Rechazar
        </button>
      </Fila>

      {error ? (
        <p className="aviso" role="alert">
          No se pudo responder a la puerta: {error}
        </p>
      ) : null}
    </section>
  );
}

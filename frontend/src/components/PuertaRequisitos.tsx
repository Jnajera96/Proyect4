/**
 * Puerta 1 — confirmacion de requisitos (`confirm_requirements_gate`).
 *
 * Muestra lo que el sistema **entendio** de la peticion (`TaskInterpretation`) y
 * permite confirmarlo o **corregirlo**. La correccion es la razon de que esta
 * puerta exista: sin ella, el sistema planifica sobre una lectura erronea y el
 * usuario solo puede aprobar o rechazar el resultado, ya construido.
 *
 * Al corregir se envian solo los campos que cambian. El backend acepta
 * `{decision, intent?, constraints?, rationale?}`; mandar `intent` y `constraints`
 * juntos es lo que permite arreglar una clasificacion equivocada sin reescribir la
 * peticion entera.
 */
import { useState } from "react";
import { api, ErrorApi } from "../lib/api";
import { ETIQUETA_ESTADO, type Intent, type RunState } from "../lib/contracts";
import { Fila } from "./ui";

const ETIQUETA_INTENT: Record<Intent, string> = {
  question: "pregunta",
  inspect: "inspección",
  modify: "modificación",
  out_of_scope: "fuera de alcance",
};

const INTENTS: Intent[] = ["question", "inspect", "modify", "out_of_scope"];

export function PuertaRequisitos({
  estado,
  alDecidir,
}: {
  estado: RunState;
  alDecidir: () => void;
}) {
  const interp = estado.interpretation;
  const [modo, setModo] = useState<"revisar" | "corregir">("revisar");
  const [intent, setIntent] = useState<Intent>(interp?.intent ?? "inspect");
  const [constraints, setConstraints] = useState((interp?.constraints ?? []).join("\n"));
  const [rationale, setRationale] = useState(interp?.rationale ?? "");
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function enviar(
    decision: string,
    correcciones?: { intent?: string; constraints?: string[]; rationale?: string },
  ) {
    setOcupado(true);
    setError(null);
    try {
      await api.confirmarRequisitos(estado.run_id, decision, correcciones);
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

  function corregir() {
    const lista = constraints
      .split("\n")
      .map((c) => c.trim())
      .filter(Boolean);
    const correcciones: { intent?: string; constraints?: string[]; rationale?: string } = {};
    // Solo se envian los campos que **cambian**. Mandar todos convertiria una
    // correccion de la intencion en una reescritura de los requisitos, que no es
    // lo mismo.
    if (intent !== interp?.intent) correcciones.intent = intent;
    if (JSON.stringify(lista) !== JSON.stringify(interp?.constraints ?? [])) {
      correcciones.constraints = lista;
    }
    if (rationale !== (interp?.rationale ?? "")) correcciones.rationale = rationale;
    if (Object.keys(correcciones).length === 0) {
      void enviar("approved");
      return;
    }
    void enviar("modified", correcciones);
  }

  return (
    <section className="panel">
      <h2 className="panel-titulo">Confirmación de requisitos</h2>
      <p className="panel-nota">
        El sistema ha interpretado tu petición. Confirma que es correcta o corrígela
        antes de que se planifique nada.
      </p>

      {!interp ? (
        <p className="vacio">Aún no hay interpretación registrada.</p>
      ) : modo === "revisar" ? (
        <>
          <dl className="datos">
            <dt>extraído</dt>
            <dd className="mono">{estado.instruction.text}</dd>
            <dt>intención</dt>
            <dd>
              {ETIQUETA_INTENT[interp.intent]} ({interp.intent})
            </dd>
            <dt>confianza</dt>
            <dd>{(interp.confidence * 100).toFixed(0)}%</dd>
            <dt>repositorio</dt>
            <dd className="mono">{interp.scope.repo_path}</dd>
            <dt>rutas libres</dt>
            <dd className="mono">
              {interp.scope.allowed_paths.length
                ? interp.scope.allowed_paths.join(", ")
                : "(todo el repositorio)"}
            </dd>
            <dt>rutas protegidas</dt>
            <dd className="mono">
              {interp.scope.protected_paths.length
                ? interp.scope.protected_paths.join(", ")
                : "—"}
            </dd>
            <dt>restricciones</dt>
            <dd>
              {interp.constraints.length ? (
                <ul className="limpia">
                  {interp.constraints.map((c, i) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
              ) : (
                "—"
              )}
            </dd>
            <dt>por qué</dt>
            <dd>{interp.rationale}</dd>
          </dl>

          <Fila sep>
            <button
              id="btn-confirmar-requisitos"
              className="primario"
              disabled={ocupado}
              onClick={() => void enviar("approved")}
            >
              Confirmar requisitos
            </button>
            <button disabled={ocupado} onClick={() => setModo("corregir")}>
              Corregir
            </button>
            <button
              className="peligro"
              disabled={ocupado}
              onClick={() => void enviar("rejected")}
            >
              Rechazar
            </button>
          </Fila>
        </>
      ) : (
        <>
          <div className="stack">
            <div>
              <label htmlFor="g1-intent">Intención</label>
              <select
                id="g1-intent"
                value={intent}
                onChange={(e) => setIntent(e.target.value as Intent)}
                style={{
                  width: "100%",
                  font: "inherit",
                  padding: "0.55rem 0.75rem",
                  borderRadius: "var(--radio-sm)",
                  border: "1px solid var(--borde)",
                  background: "var(--superficie-2)",
                  color: "var(--texto)",
                }}
              >
                {INTENTS.map((i) => (
                  <option key={i} value={i}>
                    {ETIQUETA_INTENT[i]} ({i})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="g1-constraints">Restricciones (una por línea)</label>
              <textarea
                id="g1-constraints"
                value={constraints}
                onChange={(e) => setConstraints(e.target.value)}
                placeholder="no toques el esquema de la base de datos"
              />
            </div>
            <div>
              <label htmlFor="g1-rationale">Por qué (razonamiento)</label>
              <textarea
                id="g1-rationale"
                value={rationale}
                onChange={(e) => setRationale(e.target.value)}
              />
            </div>
          </div>

          <Fila sep>
            <button className="primario" disabled={ocupado} onClick={corregir}>
              Enviar correcciones
            </button>
            <button disabled={ocupado} onClick={() => setModo("revisar")}>
              Volver
            </button>
          </Fila>
        </>
      )}

      {error ? (
        <p className="aviso" role="alert">
          No se pudo responder a la puerta: {error}
        </p>
      ) : null}
      <p className="tenue fila-sep">
        Estado de la ejecución: {ETIQUETA_ESTADO[estado.status]}
      </p>
    </section>
  );
}

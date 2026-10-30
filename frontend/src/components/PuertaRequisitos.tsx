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
 *
 * La puerta se presenta como lo que es: **una parada**. El flujo no sigue hasta
 * que alguien decida, y eso se dice en voz alta en la cabecera.
 */
import { useState } from "react";
import { api } from "../lib/api";
import { rutaCorta } from "../lib/formato";
import { ETIQUETA_ESTADO, type Intent, type RunState } from "../lib/contracts";
import { Chip, Fila, Seccion } from "./ui";

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
  alFallo,
}: {
  estado: RunState;
  alDecidir: () => void;
  /** Anota el fallo en el shell y devuelve el mensaje que hay que enseñar. */
  alFallo: (causa: unknown) => string;
}) {
  const interp = estado.interpretation;
  const construye = (estado.options.mode ?? "FULL_PROPOSAL") === "FULL_PROPOSAL";
  const caracteristicas = (interp?.rationale ?? "").split(/\r?\n/)
    .filter(linea => /^\s*(?:[-*•]|\d+[.)])\s+/.test(linea))
    .map(linea => linea.replace(/^\s*(?:[-*•]|\d+[.)])\s+/, ""));
  const [modo, setModo] = useState<"revisar" | "corregir">("revisar");
  const [intent, setIntent] = useState<Intent>(interp?.intent ?? "inspect");
  const [constraints, setConstraints] = useState((interp?.constraints ?? []).join("\n"));
  const [rationale, setRationale] = useState(interp?.rationale ?? "");
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sinRepositorio = !estado.options.repo_path || estado.options.repo_path.startsWith("(");
  const requiereRepositorio = sinRepositorio && (modo === "corregir" ? intent : interp?.intent) === "modify";

  async function enviar(
    decision: string,
    correcciones?: { intent?: string; constraints?: string[]; rationale?: string },
  ) {
    setOcupado(true);
    setError(null);
    try {
      await api.confirmarRequisitos(estado.run_id, decision, correcciones);
      alDecidir();
    } catch (causa) {
      setError(alFallo(causa));
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
    <section className="puerta" aria-labelledby="titulo-puerta-requisitos">
      <header className="puerta-cabecera">
        <div>
          <p className="puerta-aviso" role="status">
            El flujo está detenido esperando tu decisión
          </p>
          <h2 className="puerta-titulo" id="titulo-puerta-requisitos">
            Confirmación de requisitos
          </h2>
          <p className="puerta-nota">
            Nada se planifica hasta que confirmes que lo entendido es lo que pediste.
          </p>
        </div>
        <Chip tono="aviso">{ETIQUETA_ESTADO[estado.status]}</Chip>
      </header>
      {estado.instruction.source === "text" ? <p>Fidelidad de captura: <strong>100%</strong> · texto escrito conservado literalmente. La comprensión de intención se revisa por separado.</p> : null}
      {requiereRepositorio ? <p className="aviso" role="alert">Para modificar archivos necesitas un repositorio Git autorizado. Selecciona un proyecto registrado en el compositor e inicia una nueva ejecución; esta solicitud no tiene repositorio.</p> : null}

      {!interp ? (
        <p className="vacio">Aún no hay interpretación registrada.</p>
      ) : modo === "revisar" ? (
        <>
          {caracteristicas.length > 0 && <Seccion titulo="Características planificadas para tu aplicación">
            <p>Esta es una propuesta para que la revises. Puedes ajustar o quitar funciones antes de construir.</p>
            <ul>{caracteristicas.map((texto, i) => <li key={i}>{texto}</li>)}</ul>
          </Seccion>}
          <Seccion titulo="Lo que el sistema entendió">
            <dl className="datos">
              <dt>Tu petición</dt>
              <dd className="mono">{estado.instruction.text}</dd>
              <dt>Intención</dt>
              <dd>
                {ETIQUETA_INTENT[interp.intent]}{" "}
                <span className="tenue mono">({interp.intent})</span>
              </dd>
              <dt>Puntuación de intención</dt>
              <dd>
                {(interp.confidence * 100).toFixed(0)}%
                <span className="tenue"> · heurística declarada por el analista, no calibrada; no mide la fidelidad de captura ni la transcripción</span>
              </dd>
              <dt>Repositorio</dt>
              <dd className="mono" title={interp.scope.repo_path}>
                {rutaCorta(interp.scope.repo_path)}
              </dd>
              <dt>Rutas libres</dt>
              <dd className="mono">
                {interp.scope.allowed_paths.length
                  ? interp.scope.allowed_paths.join(", ")
                  : "(todo el repositorio)"}
              </dd>
              <dt>Rutas protegidas</dt>
              <dd className="mono">
                {interp.scope.protected_paths.length
                  ? interp.scope.protected_paths.join(", ")
                  : "—"}
              </dd>
              <dt>Restricciones</dt>
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
              <dt>Por qué</dt>
              <dd>{caracteristicas.length ? <details><summary>Ver interpretación completa</summary>
                <p style={{ whiteSpace: "pre-wrap" }}>{interp.rationale}</p></details> : interp.rationale}</dd>
            </dl>
          </Seccion>

          <Fila sep>
            <button
              id="btn-confirmar-requisitos"
              className="primario"
              disabled={ocupado || requiereRepositorio}
              onClick={() => void enviar("approved")}
            >
              {interp.intent === "modify" && construye ? "Confirmar y construir" : "Confirmar"}
            </button>
            <button disabled={ocupado} onClick={() => {
              setIntent(interp.intent); setConstraints(interp.constraints.join("\n"));
              setRationale(interp.rationale); setModo("corregir");
            }}>
              Ajustar propuesta
            </button>
            <button
              className="peligro"
              disabled={ocupado}
              onClick={() => void enviar("rejected")}
            >
              Rechazar
            </button>
            <span className="tenue">
              Rechazar detiene la ejecución: no se planifica nada.
            </span>
          </Fila>
        </>
      ) : (
        <>
          <Seccion titulo="Corregir lo entendido" nota="Solo se envía lo que cambies.">
            <div className="stack">
              <div>
                <label htmlFor="g1-intent">Intención</label>
                <select
                  id="g1-intent"
                  value={intent}
                  onChange={(e) => setIntent(e.target.value as Intent)}
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
                <label htmlFor="g1-rationale">Características y alcance propuestos</label>
                <textarea
                  id="g1-rationale"
                  value={rationale}
                  maxLength={2000}
                  rows={10}
                  onChange={(e) => setRationale(e.target.value)}
                />
              </div>
            </div>
          </Seccion>

          <Fila sep>
            <button className="primario" disabled={ocupado || requiereRepositorio} onClick={corregir}>
              {intent === "modify" && construye ? "Guardar ajustes y construir" : "Guardar ajustes y confirmar"}
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
    </section>
  );
}

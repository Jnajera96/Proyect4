/**
 * Puerta 2 — aprobacion del cambio (`approval_gate`, F12).
 *
 * Es la decision mas consecuente del sistema: **aprobar escribe en el repositorio
 * del usuario**. Por eso la pantalla ensena todo lo que se sabe antes de pedir la
 * decision -el diff literal, la evidencia de las pruebas, el veredicto del revisor
 * y los riesgos declarados- y lo dice en voz alta, sin adornos.
 *
 * **Ninguna opcion viene marcada.** El backend exige `decision` sin valor por
 * defecto precisamente por esto: un cuerpo mal formado no puede convertirse en una
 * promocion silenciosa. Aqui no hay una opcion preseleccionada que se pueda enviar
 * sin querer.
 *
 * `comments` solo tiene sentido al **solicitar cambios**: son las instrucciones que
 * quedan para la siguiente iteracion. El backend lo ignora en las otras dos
 * decisiones, y aqui se dice para que no parezca que se pierde.
 */
import { useState } from "react";
import { api } from "../lib/api";
import { hashCorto, rutaCorta } from "../lib/formato";
import type { ApprovalDecision, RunState } from "../lib/contracts";
import { ContenidoReviewer, ListaPruebas } from "./evidencia";
import { Chip, EstadoVacio, Fila, Seccion } from "./ui";
import { VisorDiff } from "./VisorDiff";

export function PuertaAprobacion({
  estado,
  alDecidir,
  alFallo,
}: {
  estado: RunState;
  alDecidir: () => void;
  alFallo: (causa: unknown) => string;
}) {
  const [comentarios, setComentarios] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cambio = estado.outputs.coder_output;
  const diff = estado.artifacts.diff || cambio?.diff || "";
  const ficheros = estado.artifacts.changed_files ?? [];
  const pruebas = estado.evidence.test_runs ?? [];
  const veredicto = estado.outputs.reviewer_output;

  // Riesgos **declarados**: lo que el revisor marco como grave y lo que el propio
  // sistema registro como error. No se calcula una "puntuacion de riesgo" que
  // nadie ha pedido ni se inventa una categoria que el backend no emite.
  const riesgos = [
    ...(veredicto?.findings ?? []),
    ...(estado.evidence.findings ?? []),
  ].filter((f) => f.severity === "high" || f.severity === "critical");

  const pruebasFallidas = pruebas.filter((p) => p.exit_code !== 0);

  async function decidir(decision: ApprovalDecision) {
    setOcupado(true);
    setError(null);
    try {
      await api.aprobar(estado.run_id, decision, comentarios);
      alDecidir();
    } catch (causa) {
      setError(alFallo(causa));
    } finally {
      setOcupado(false);
    }
  }

  return (
    <section className="puerta" aria-labelledby="titulo-puerta-aprobacion">
      <header className="puerta-cabecera">
        <div>
          <p className="puerta-aviso" role="status">
            El flujo está detenido esperando tu decisión
          </p>
          <h2 className="puerta-titulo" id="titulo-puerta-aprobacion">
            Aprobación del cambio
          </h2>
          <p className="puerta-nota">
            Nada sale del sandbox hasta que decidas. El cambio ya está aplicado
            allí y las pruebas ya corrieron sobre él.
          </p>
        </div>
        <Chip tono="aviso">esperando aprobación</Chip>
      </header>

      {/* ------------------------------------------------------- Cambios */}
      <Seccion
        titulo="Cambios propuestos"
        nota="El diff es literal: es exactamente lo que se promovería al repositorio."
      >
        {ficheros.length ? (
          <ul className="ficheros">
            {ficheros.map((f) => (
              <li key={f.path}>
                <span className="mono" title={f.path}>
                  {rutaCorta(f.path)}
                </span>
                <span className="mas">+{f.added}</span>
                <span className="menos">−{f.removed}</span>
                <span className="tenue mono" title={f.sha256}>
                  {hashCorto(f.sha256)}
                </span>
              </li>
            ))}
          </ul>
        ) : null}
        {diff.trim() ? (
          <details><summary>Ver cambios técnicos</summary><VisorDiff texto={diff} ficheros={ficheros} /></details>
        ) : (
          <EstadoVacio titulo="El cambio no incluye diff">
            {cambio?.rationale
              ? cambio.rationale
              : "El Coder no produjo cambios que promover."}
          </EstadoVacio>
        )}
        {cambio?.rationale ? (
          <>
            <p className="rotulo">Por qué propone esto el Coder</p>
            <p>{cambio.rationale}</p>
          </>
        ) : null}
      </Seccion>

      {/* ------------------------------------------------------ Pruebas */}
      <Seccion
        titulo="Evidencia de pruebas"
        nota="Lo que el ejecutor de pruebas devolvió dentro del sandbox."
      >
        <ListaPruebas pruebas={pruebas} />
      </Seccion>

      {/* ----------------------------------------------------- Revisor */}
      {veredicto ? (
        <Seccion titulo="Veredicto del revisor">
          <ContenidoReviewer veredicto={veredicto} />
        </Seccion>
      ) : null}

      {/* ------------------------------------------------------ Riesgos */}
      <Seccion
        titulo="Riesgos"
        nota="Hallazgos de severidad alta o crítica, y errores registrados por el sistema."
      >
        {riesgos.length || estado.errors.length || pruebasFallidas.length ? (
          <ul className="limpia">
            {pruebasFallidas.map((p, i) => (
              <li key={`t-${i}`}>
                <span className="sev high">pruebas</span> el objetivo{" "}
                <span className="mono">{p.target}</span> terminó con salida{" "}
                {p.exit_code}.
              </li>
            ))}
            {riesgos.map((f, i) => (
              <li key={`r-${i}`}>
                <span className={`sev ${f.severity}`}>{f.severity}</span>{" "}
                <span className="mono">{rutaCorta(f.path)}</span> — {f.explanation}
              </li>
            ))}
            {estado.errors.map((e, i) => (
              <li key={`e-${i}`}>
                <span className="sev medium">error</span>{" "}
                <span className="mono">{e.error_class}</span> — {e.message}
              </li>
            ))}
          </ul>
        ) : (
          <p className="tenue">
            Ni hallazgos graves, ni pruebas fallidas, ni errores registrados.
          </p>
        )}
      </Seccion>

      {/* -------------------------------------------------- Comentarios */}
      <Seccion
        titulo="Comentarios"
        nota="Solo se envían al solicitar cambios: son las instrucciones para la siguiente iteración."
      >
        <label htmlFor="g2-comentarios">Qué habría que cambiar</label>
        <textarea
          id="g2-comentarios"
          value={comentarios}
          onChange={(e) => setComentarios(e.target.value)}
          placeholder="por ejemplo: añade una prueba que cubra el caso vacío"
        />
      </Seccion>

      {/* ----------------------------------------------------- Decisión */}
      <div className="puerta-decision">
        <p className="puerta-consecuencia">
          <strong>Al aprobar, los cambios verificados se promoverán al repositorio
          real.</strong>{" "}
          Es la única acción del sistema que escribe fuera del sandbox.
        </p>
        <Fila>
          <button
            id="btn-aprobar"
            className="primario"
            disabled={ocupado}
            onClick={() => void decidir("approved")}
          >
            Aprobar
          </button>
          <button disabled={ocupado} onClick={() => void decidir("modified")}>
            Solicitar cambios
          </button>
          <button
            className="peligro"
            disabled={ocupado}
            onClick={() => void decidir("rejected")}
          >
            Rechazar
          </button>
        </Fila>
        <p className="tenue">
          Ninguna opción viene marcada: la decisión la tomas tú y el servidor no
          supone ninguna.
        </p>
      </div>

      {error ? (
        <p className="aviso" role="alert">
          No se pudo registrar la decisión: {error}
        </p>
      ) : null}
    </section>
  );
}

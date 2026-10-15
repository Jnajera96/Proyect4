/**
 * Paneles de evidencia de una ejecucion.
 *
 * Cada panel pinta **un campo real** de `RunState` y nada mas. La regla que los
 * gobierna: si el backend no lo manda, no se dibuja -ni un cero, ni un
 * "desconocido" que parezca un dato, ni una insignia que nunca se encienda-. Los
 * contratos tienen ejemplos de campos retirados por eso mismo (`reproducible`,
 * `dry_run`), y este fichero no va a reintroducir el problema desde la interfaz.
 */
import { useState } from "react";
import type {
  Approval,
  Budget,
  Finding,
  RunError,
  RunPlan,
  RunState,
  TestRun,
} from "../lib/contracts";
import { duracion, fechaHora, hashCorto, numero, porcentaje, rutaCorta } from "../lib/formato";
import { Barra, Chip, EstadoVacio, Panel } from "./ui";

const ETIQUETA_DECISION: Record<string, string> = {
  accept: "Aceptado",
  request_changes: "Cambios solicitados",
  escalate: "Escalado",
  approved: "Aprobado",
  rejected: "Rechazado",
  modified: "Modificado",
};

const ETIQUETA_SUBTAREA: Record<string, string> = {
  pending: "pendiente",
  running: "en curso",
  completed: "hecha",
  failed: "fallida",
  skipped: "omitida",
};

/* ------------------------------------------------------------------- Plan */

export function PanelPlan({ plan, indice }: { plan: RunPlan; indice: number }) {
  return (
    <Panel
      titulo="Plan"
      nota="Subtareas asignadas por el Supervisor. La marca indica por cual va la ejecucion."
    >
      <ol className="subtareas">
        {plan.subtasks.map((s, i) => {
          const actual = i === indice;
          return (
            <li key={s.id} className={actual ? "actual" : ""}>
              <span className="subtarea-marca mono">{s.id}</span>
              <span className="subtarea-cuerpo">
                <span className="subtarea-desc">{s.description}</span>
                <span className="tenue">
                  {s.agent} · {ETIQUETA_SUBTAREA[s.status] ?? s.status}
                  {s.done_criteria ? ` · criterio: ${s.done_criteria}` : ""}
                </span>
              </span>
              {actual ? <Chip tono="acento">en curso</Chip> : null}
            </li>
          );
        })}
      </ol>
      {plan.rationale ? <p className="tenue fila-sep">{plan.rationale}</p> : null}
      <p className="tenue">Ciclos de revisión permitidos: {plan.max_review_cycles}</p>
    </Panel>
  );
}

/* --------------------------------------------------------------- Pruebas */

/**
 * Evidencia de pruebas.
 *
 * **El veredicto se deriva del `exit_code`**, porque el contrato no tiene un campo
 * `status`: 0 es correcto y cualquier otra cosa es fallo. Se ensena el codigo al
 * lado para que la derivacion sea visible y no una afirmacion de la interfaz.
 */
export function PanelPruebas({ pruebas }: { pruebas: TestRun[] }) {
  return (
    <Panel titulo="Pruebas" nota="Salida literal del ejecutor de pruebas del servidor.">
      <ListaPruebas pruebas={pruebas} />
    </Panel>
  );
}

/** La lista de pruebas, sin la tarjeta: la reutilizan las puertas humanas. */
export function ListaPruebas({ pruebas }: { pruebas: TestRun[] }) {
  const [abierta, setAbierta] = useState<number | null>(null);

  if (!pruebas.length) {
    return (
      <EstadoVacio titulo="Sin evidencia de pruebas">
        El servidor no ha registrado ninguna ejecución de pruebas para esta
        ejecución. Un cambio sin pruebas no es un cambio verificado.
      </EstadoVacio>
    );
  }

  return (
    <ul className="pruebas">
      {pruebas.map((p, i) => {
        const correcta = p.exit_code === 0;
        return (
          <li key={`${p.target}-${i}`} className={correcta ? "ok" : "error"}>
            <div className="prueba-cabecera">
              <Chip tono={correcta ? "ok" : "error"}>{correcta ? "PASS" : "FAIL"}</Chip>
              <span className="mono">{p.target}</span>
              <span className="tenue">
                salida {p.exit_code} · {duracion(p.duration_s)}
              </span>
              <button
                className="sutil"
                onClick={() => setAbierta(abierta === i ? null : i)}
                aria-expanded={abierta === i}
              >
                {abierta === i ? "Ocultar salida" : "Ver salida"}
              </button>
            </div>
            {abierta === i ? (
              <div className="prueba-detalle">
                {p.argv?.length ? <p className="tenue mono">{p.argv.join(" ")}</p> : null}
                {p.stdout ? (
                  <>
                    <p className="tenue">stdout</p>
                    <pre className="salida">{p.stdout}</pre>
                  </>
                ) : null}
                {p.stderr ? (
                  <>
                    <p className="tenue">stderr</p>
                    <pre className="salida">{p.stderr}</pre>
                  </>
                ) : null}
                {!p.stdout && !p.stderr ? (
                  <p className="tenue">El ejecutor no devolvió salida.</p>
                ) : null}
              </div>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

/* -------------------------------------------------------------- Reviewer */

export function PanelReviewer({
  veredicto,
}: {
  veredicto: {
    decision: string;
    summary: string;
    findings: Finding[];
    required_fixes: string[];
  };
}) {
  return (
    <Panel titulo="Revisor" nota="Veredicto del agente revisor sobre el cambio propuesto.">
      <ContenidoReviewer veredicto={veredicto} />
    </Panel>
  );
}

/** El veredicto sin la tarjeta: lo reutiliza la puerta de aprobacion. */
export function ContenidoReviewer({
  veredicto,
}: {
  veredicto: {
    decision: string;
    summary: string;
    findings: Finding[];
    required_fixes: string[];
  };
}) {
  return (
    <>
      <div className={`veredicto ${veredicto.decision}`}>
        <div className="fila">
          <strong>{ETIQUETA_DECISION[veredicto.decision] ?? veredicto.decision}</strong>
          <span className="tenue mono">{veredicto.decision}</span>
        </div>
        <p style={{ margin: "0.5rem 0 0" }}>{veredicto.summary}</p>
      </div>

      {veredicto.required_fixes?.length ? (
        <>
          <p className="rotulo">Correcciones exigidas</p>
          <ul className="limpia">
            {veredicto.required_fixes.map((f, i) => (
              <li key={i}>{f}</li>
            ))}
          </ul>
        </>
      ) : null}

      {veredicto.findings?.length ? (
        <>
          <p className="rotulo">Hallazgos</p>
          <ListaHallazgos hallazgos={veredicto.findings} />
        </>
      ) : null}
    </>
  );
}

/** Lista de hallazgos con severidad, ruta, linea y evidencia. */
export function ListaHallazgos({ hallazgos }: { hallazgos: Finding[] }) {
  return (
    <ul className="hallazgos">
      {hallazgos.map((f, i) => (
        <li key={i}>
          <span className={`sev ${f.severity}`}>{f.severity}</span>
          <span className="hallazgo-cuerpo">
            <span className="ruta-hallazgo" title={f.path}>
              {rutaCorta(f.path)}
              {f.line ? `:${f.line}` : ""}
            </span>
            {" — "}
            {f.explanation}
            {f.evidence ? <span className="hallazgo-evidencia">{f.evidence}</span> : null}
          </span>
        </li>
      ))}
    </ul>
  );
}

/* ---------------------------------------------------------- Presupuesto */

/**
 * Presupuesto consumido frente a los limites declarados.
 *
 * **El coste se declara cuando se sabe.** El contrato lo modela como
 * `max_cost: float | None`; con la tabla de tarifas vacia no hay forma de saber
 * cuanto costo nada, y `used_cost` vale cero sin significar "gratis". Cuando no hay
 * limite de coste declarado se dice "tarifas no configuradas" y **no se ensena un
 * cero**: un `$0,00` ahi seria una afirmacion falsa sobre el gasto.
 */
export function PanelPresupuesto({ budget }: { budget: Budget }) {
  const filas: { rotulo: string; usado: number; maximo: number }[] = [
    { rotulo: "tokens", usado: budget.used_tokens, maximo: budget.max_tokens },
    { rotulo: "llamadas al modelo", usado: budget.used_model_calls, maximo: budget.max_model_calls },
    { rotulo: "llamadas a herramientas", usado: budget.used_tool_calls, maximo: budget.max_tool_calls },
    { rotulo: "ciclos de revisión", usado: budget.review_cycles_used, maximo: budget.max_review_cycles },
  ];

  return (
    <Panel titulo="Presupuesto" nota="Consumo real frente a los límites con los que arrancó la ejecución.">
      <dl className="datos">
        <dt>tokens de entrada</dt>
        <dd>{numero(budget.used_input_tokens)}</dd>
        <dt>tokens de salida</dt>
        <dd>{numero(budget.used_output_tokens)}</dd>
        <dt>tiempo transcurrido</dt>
        <dd>{duracion(budget.elapsed_seconds)}</dd>
      </dl>

      <div className="presupuesto">
        {filas.map((f) => (
          <div className="presupuesto-fila" key={f.rotulo}>
            <span className="presupuesto-rotulo">{f.rotulo}</span>
            <Barra
              valor={f.usado}
              maximo={f.maximo}
              tono={porcentaje(f.usado, f.maximo) >= 90 ? "aviso" : ""}
              etiqueta={`${f.rotulo}: ${f.usado} de ${f.maximo}`}
            />
            <span className="mono tenue">
              {numero(f.usado)} / {numero(f.maximo)}
            </span>
          </div>
        ))}
      </div>

      <p className="tenue fila-sep">
        {budget.max_cost === null
          ? "Coste: tarifas no configuradas, no hay importe que mostrar."
          : `Coste: ${budget.used_cost.toFixed(4)} de ${budget.max_cost.toFixed(4)}.`}
      </p>
    </Panel>
  );
}

/* ------------------------------------------------------- Aprobaciones */

/**
 * Registro de decisiones humanas (RNF-T2): quien, cuando, que y sobre que
 * contenido exacto. El `content_sha256` es lo que ata la decision al diff que se
 * aprobo, y por eso se ensena aunque sea ilegible: es la prueba de trazabilidad.
 */
export function HistorialAprobaciones({ aprobaciones }: { aprobaciones: Approval[] }) {
  if (!aprobaciones.length) {
    return (
      <Panel titulo="Aprobaciones">
        <EstadoVacio titulo="Todavía no hay ninguna decisión humana registrada">
          Cuando alguien confirme los requisitos o apruebe el cambio, aquí quedará
          el registro con el actor, la fecha y el hash del contenido decidido.
        </EstadoVacio>
      </Panel>
    );
  }
  return (
    <Panel titulo="Aprobaciones" nota="Registro de trazabilidad de las decisiones humanas.">
      <ul className="aprobaciones">
        {aprobaciones.map((a, i) => (
          <li key={i}>
            <div className="fila">
              <Chip tono={a.decision === "approved" ? "ok" : a.decision === "rejected" ? "error" : "aviso"}>
                {ETIQUETA_DECISION[a.decision] ?? a.decision}
              </Chip>
              <span className="mono tenue">{a.action}</span>
              <span className="tenue" style={{ marginLeft: "auto" }}>
                {fechaHora(a.decided_at)}
              </span>
            </div>
            <dl className="datos">
              <dt>actor</dt>
              <dd>{a.actor}</dd>
              <dt>contenido</dt>
              <dd className="mono" title={a.content_sha256}>
                sha256 {hashCorto(a.content_sha256)}
              </dd>
              {a.reason ? (
                <>
                  <dt>motivo</dt>
                  <dd>{a.reason}</dd>
                </>
              ) : null}
            </dl>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

/* ------------------------------------------------------------- Seguridad */

/**
 * Los limites con los que trabajo la ejecucion y lo que el motor anoto sobre
 * ellos: el aislamiento declarado (repositorio, rutas permitidas y protegidas, el
 * sandbox y el commit base) y el recuento de incidencias por clase de error.
 *
 * **No se ensena nada que pueda ser un secreto**: ni la credencial, ni la URL del
 * flujo de eventos -que la lleva en la query-, ni cabeceras. La ruta del sandbox
 * es un dato del aislamiento y va acortada.
 *
 * Vive aqui, y no en la vista de seguridad, porque la usan dos sitios: la vista de
 * seguridad, donde el aislamiento es el tema, y el detalle de la ejecucion, donde
 * es una de las cosas que hay que saber antes de aprobar un cambio. Con dos copias
 * habria bastado tocar una para que dijeran cosas distintas.
 */
export function PanelSeguridadRun({ estado }: { estado: RunState }) {
  const politicos = estado.errors.filter((e) =>
    ["POLICY_DENIED", "SANDBOX_PATH_DENIED", "PROMOTION_DENIED"].includes(e.error_class),
  );
  const degradaciones = estado.errors.filter((e) => e.error_class === "MODEL_FALLBACK");
  const presupuesto = estado.errors.filter((e) => e.error_class === "BUDGET_EXCEEDED");

  return (
    <>
      <Panel nota="Lo que la ejecución declaró y el sandbox donde trabajó.">
        <dl className="datos">
          <dt>repositorio autorizado</dt>
          <dd className="mono" title={estado.options.repo_path ?? ""}>
            {estado.options.repo_path ? rutaCorta(estado.options.repo_path) : "—"}
          </dd>
          <dt>rutas permitidas</dt>
          <dd className="mono">
            {estado.options.allowed_paths.length
              ? estado.options.allowed_paths.join(", ")
              : "(todo el repositorio)"}
          </dd>
          <dt>rutas protegidas</dt>
          <dd className="mono">
            {estado.options.protected_paths.length
              ? estado.options.protected_paths.join(", ")
              : "—"}
          </dd>
          <dt>worktree del sandbox</dt>
          <dd className="mono" title={estado.artifacts.worktree_path ?? ""}>
            {estado.artifacts.worktree_path ? rutaCorta(estado.artifacts.worktree_path) : "—"}
          </dd>
          <dt>commit base</dt>
          <dd className="mono" title={estado.artifacts.base_commit ?? ""}>
            {estado.artifacts.base_commit ? hashCorto(estado.artifacts.base_commit) : "—"}
          </dd>
        </dl>
        <p className="tenue">
          Los cambios se aplican en el sandbox. El repositorio no se toca hasta que una
          persona aprueba en la puerta de aprobación.
        </p>
      </Panel>

      <Panel
        titulo="Incidencias de política y presupuesto"
        nota="Se cuentan las clases de error que el motor emite de verdad; una ejecución sin ninguna no tuvo incidencias."
      >
        <div className="fila">
          <Chip tono={politicos.length ? "error" : "ok"}>
            {politicos.length} de política o aislamiento
          </Chip>
          <Chip tono={degradaciones.length ? "acento" : "ok"}>
            {degradaciones.length} de degradación a determinista
          </Chip>
          <Chip tono={presupuesto.length ? "aviso" : "ok"}>
            {presupuesto.length} de presupuesto
          </Chip>
        </div>
      </Panel>
    </>
  );
}

/* --------------------------------------------------------------- Errores */

/**
 * Familia de un `error_class`. Solo se etiquetan las clases que el sistema emite
 * de verdad; cualquier otra se ensena como "otro" con su nombre literal, en lugar
 * de forzarla dentro de una categoria que no le corresponde.
 */
const FAMILIA: Record<string, { etiqueta: string; tono: "error" | "aviso" | "acento" }> = {
  POLICY_DENIED: { etiqueta: "política", tono: "error" },
  SANDBOX_PATH_DENIED: { etiqueta: "aislamiento", tono: "error" },
  PROMOTION_DENIED: { etiqueta: "promoción", tono: "error" },
  BUDGET_EXCEEDED: { etiqueta: "presupuesto", tono: "aviso" },
  MODEL_FALLBACK: { etiqueta: "degradación a determinista", tono: "acento" },
};

export function PanelErrores({ errores }: { errores: RunError[] }) {
  if (!errores.length) {
    return (
      <Panel titulo="Errores">
        <EstadoVacio titulo="Sin errores registrados">
          La ejecución no ha declarado ningún error. Los errores se registran con
          su clase, el agente que los produjo y si son recuperables.
        </EstadoVacio>
      </Panel>
    );
  }
  return (
    <Panel titulo="Errores" nota="Taxonomía declarada por el sistema; el mensaje es literal.">
      <ul className="errores">
        {errores.map((e, i) => {
          const familia = FAMILIA[e.error_class];
          return (
            <li key={i}>
              <div className="fila">
                <Chip tono={familia?.tono ?? "aviso"}>
                  {familia?.etiqueta ?? "otro"}
                </Chip>
                <span className="mono">{e.error_class}</span>
                <span className="tenue" style={{ marginLeft: "auto" }}>
                  {e.agent} · {fechaHora(e.occurred_at)}
                </span>
              </div>
              <p className="error-mensaje">{e.message}</p>
              <p className="tenue">
                {e.recoverable ? "recuperable" : "no recuperable"}
                {e.subtask_id ? ` · subtarea ${e.subtask_id}` : ""}
              </p>
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}

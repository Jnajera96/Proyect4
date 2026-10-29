/**
 * Diagrama del flujo real.
 *
 * Las etapas son los **nodos del grafo** (`graph/workflow.py`), en su orden:
 * `interpret` -> `plan` -> `researcher` -> `coder` -> `run_tests` -> `reviewer` ->
 * `approval_gate` -> `promote_changes` -> `finalize`. El diagrama no inventa
 * ninguna: si el grafo cambia, cambia aqui.
 *
 * **El estado de cada etapa sale de evidencia, nunca de una suposicion.** No hay
 * un "en curso" pintado por temporizador: se marca lo que ya existe en el estado
 * (`interpretation`, `plan`, `outputs.*`, `evidence.test_runs`, `approvals`,
 * `final_report`) y lo que el `next_step` declara como siguiente. Un hito que el
 * flujo no ha emitido se queda pendiente, que es la verdad.
 *
 * Solo cuatro nodos emiten evento propio (`interpret`, `plan`, `coder`,
 * `run_tests`): el investigador y el revisor no. Por eso su avance se lee del
 * estado y no del flujo de eventos.
 */
import { ESTADOS_TERMINALES, type RunEvent, type RunState } from "../lib/contracts";
import { actividadesPendientes } from "./ActividadPipeline";
import { Chip } from "./ui";
import { Icono } from "./Icono";

type EstadoEtapa = "hecha" | "en-curso" | "esperando" | "fallida" | "pendiente" | "omitida" | "bloqueada";

export interface Etapa {
  id: string;
  nodo: string;
  nombre: string;
  detalle: string;
  estado: EstadoEtapa;
}

const ETIQUETA_ESTADO: Record<EstadoEtapa, string> = {
  hecha: "completada",
  "en-curso": "en curso",
  esperando: "espera decisión humana",
  fallida: "fallida",
  pendiente: "pendiente",
  omitida: "No aplica",
  bloqueada: "bloqueada / no ejecutada",
};

const TONO: Record<EstadoEtapa, "" | "ok" | "aviso" | "error" | "acento"> = {
  hecha: "ok",
  "en-curso": "acento",
  esperando: "aviso",
  fallida: "error",
  pendiente: "",
  omitida: "",
  bloqueada: "aviso",
};

export function calcular(estado: RunState, eventos: RunEvent[] = []): Etapa[] {
  const siguiente = (estado.next_step ?? "").toLowerCase();
  const plan = estado.plan;
  const pruebas = estado.evidence.test_runs ?? [];
  const pruebasVigentes = [...new Map(pruebas.map(p => [p.target, p])).values()];
  const aprobaciones = estado.approvals ?? [];
  // El historial es append-only: una solicitud de cambios anterior no sustituye
  // la decision de la ultima revision. Una aprobacion autoriza, no prueba exito.
  const promocion = [...aprobaciones].reverse().find((a) => a.action === "promote_changes");
  const falloPromocion = estado.errors.some((e) => e.error_class.startsWith("PROMOTION_"));
  // No hay un campo promotion_success: la evidencia disponible es el resultado
  // terminal del grafo con informe de cambios aplicados, sin error de promocion.
  const promocionCompletada =
    promocion?.decision === "approved" &&
    estado.status === "completed" &&
    (estado.final_report?.changes_applied.length ?? 0) > 0 &&
    !falloPromocion;

  const etapa = (
    id: string,
    nodo: string,
    nombre: string,
    detalle: string,
    hecha: boolean,
    extra?: { esperando?: boolean; fallida?: boolean; detalleHecho?: string },
  ): Etapa => {
    let valor: EstadoEtapa = "pendiente";
    if (extra?.fallida) valor = "fallida";
    else if (extra?.esperando) valor = "esperando";
    else if (hecha) valor = "hecha";
    else if (estado.status === "running" && siguiente === nodo) valor = "en-curso";
    const omitida = [...eventos].reverse().find(e => e.data.node === nodo && String(e.kind) === "node_skipped");
    const soloInspeccion = estado.options.mode === "INSPECT_ONLY" || (estado.interpretation && estado.interpretation.intent !== "modify");
    const soloPlan = estado.options.mode === "PLAN_ONLY";
    const sinCambios = ["coder", "run_tests", "reviewer", "approval_gate", "promote_changes"].includes(nodo);
    if (valor === "pendiente" && (omitida || (sinCambios && (soloInspeccion || soloPlan)))) {
      valor = "omitida";
      detalle = typeof omitida?.data.reason === "string" ? omitida.data.reason : soloPlan ? "No aplica en modo solo plan." : "No aplica en modo inspección o consulta.";
    } else if (valor === "pendiente" && (ESTADOS_TERMINALES.has(estado.status) || estado.status === "needs_human")) {
      valor = "bloqueada";
      detalle = "La ejecución se detuvo sin completar esta etapa. Revisa las incidencias y la decisión humana.";
    }
    if (estado.status === "running" && actividadesPendientes(eventos).some(e => e.data.node === nodo)) valor = "en-curso";
    return { id, nodo, nombre, detalle: hecha && extra?.detalleHecho ? extra.detalleHecho : detalle, estado: valor };
  };

  const esperaRequisitos = estado.status === "awaiting_human_requirements_confirmation";
  const esperaAprobacion = estado.status === "awaiting_approval";

  return [
    etapa(
      "requisitos",
      "interpret",
      "Analista de requisitos",
      "Lee la petición y declara qué entendió, con su alcance y sus restricciones.",
      estado.interpretation !== null,
      {
        esperando: esperaRequisitos,
        detalleHecho: estado.instruction.confirmed_by_user
          ? "Interpretación confirmada por una persona."
          : "Interpretación registrada.",
      },
    ),
    etapa(
      "supervisor",
      "plan",
      "Supervisor",
      "Descompone la petición en subtareas y las asigna a un agente.",
      plan !== null,
      { detalleHecho: plan ? `${plan.subtasks.length} subtarea(s) planificada(s).` : undefined },
    ),
    etapa(
      "investigador",
      "researcher",
      "Investigador",
      "Reúne evidencia del repositorio. Solo lectura: no modifica nada.",
      estado.outputs.researcher_output !== null,
      {
        detalleHecho: estado.outputs.researcher_output
          ? `${estado.outputs.researcher_output.findings?.length ?? 0} hallazgo(s), ` +
            `${estado.outputs.researcher_output.unknowns?.length ?? 0} incógnita(s) declarada(s).`
          : undefined,
      },
    ),
    etapa(
      "coder",
      "coder",
      "Coder",
      "Propone y aplica cambios en un worktree con confinamiento de escritura.",
      Boolean((estado.artifacts.diff || estado.outputs.coder_output?.diff || "").trim()),
      {
        fallida: estado.outputs.coder_output !== null && !(estado.artifacts.diff || estado.outputs.coder_output?.diff || "").trim(),
        detalleHecho: estado.artifacts.changed_files?.length
          ? `${estado.artifacts.changed_files.length} fichero(s) en el sandbox.`
          : undefined,
      },
    ),
    etapa(
      "pruebas",
      "run_tests",
      "Pruebas",
      "Ejecuta los objetivos permitidos dentro del sandbox y guarda la salida.",
      pruebas.length > 0,
      {
        fallida: pruebasVigentes.some((p) => p.exit_code !== 0),
        detalleHecho: pruebasVigentes.length
          ? `${pruebasVigentes.filter((p) => p.exit_code === 0).length} de ${pruebasVigentes.length} objetivo(s) correctos en su última ejecución.`
          : undefined,
      },
    ),
    etapa(
      "revisor",
      "reviewer",
      "Revisor",
      "Emite un veredicto sobre el cambio con la evidencia de las pruebas delante.",
      estado.outputs.reviewer_output !== null,
      {
        detalleHecho: estado.outputs.reviewer_output
          ? `Veredicto: ${estado.outputs.reviewer_output.decision}.`
          : undefined,
      },
    ),
    etapa(
      "aprobacion",
      "approval_gate",
      "Aprobación humana",
      "Una persona decide. Hasta que decide, los cambios no salen del sandbox.",
      promocion !== undefined,
      {
        esperando: esperaAprobacion,
        detalleHecho: promocion ? `Decisión: ${promocion.decision}.` : undefined,
      },
    ),
    etapa(
      "promocion",
      "promote_changes",
      "Promoción al repositorio",
      "El parche aprobado se aplica al repositorio real.",
      promocionCompletada,
      { fallida: falloPromocion },
    ),
  ];
}

export function DiagramaFlujo({ estado, alEtapa, eventos = [] }: { estado: RunState | null; alEtapa?: (etapa: Etapa) => void; eventos?: RunEvent[] }) {
  const etapas: Etapa[] = estado ? calcular(estado, eventos) : [
    ["requisitos", "interpret", "Analista de requisitos", "Interpreta la petición y espera tu confirmación."],
    ["supervisor", "plan", "Supervisor", "Organiza el trabajo en subtareas."],
    ["investigador", "researcher", "Investigador", "Reúne evidencia determinista del repositorio."],
    ["coder", "coder", "Coder", "Propone cambios dentro del worktree."],
    ["pruebas", "run_tests", "Pruebas", "Guarda evidencia de los objetivos permitidos."],
    ["revisor", "reviewer", "Revisor", "Contrasta cambios con evidencia."],
    ["aprobacion", "approval_gate", "Aprobación humana", "Tú decides sobre el cambio propuesto."],
    ["promocion", "promote_changes", "Promoción", "Aplica el parche autorizado al repositorio."],
  ].map(([id, nodo, nombre, detalle]) => ({ id, nodo, nombre, detalle, estado: "pendiente" }));

  return (
    <ol className="flujo" aria-label="Etapas del flujo de ejecución">
      {etapas.map((e) => (
        <li key={e.id} className={`flujo-etapa ${e.estado}`}>
          <div className="flujo-marca" aria-hidden="true">
            <Icono nombre={e.id === "coder" ? "codigo" : e.id === "investigador" ? "buscar" : e.id === "pruebas" ? "pruebas" : e.id === "promocion" ? "flecha" : e.id === "supervisor" ? "flujo" : e.id === "revisor" ? "seguridad" : "detalle"} />
          </div>
          <div className="flujo-cuerpo">
            <div className="fila">
              <span className="flujo-nombre">{e.nombre}</span>
              <Chip tono={TONO[e.estado]}>{estado ? ETIQUETA_ESTADO[e.estado] : "Sin ejecución"}</Chip>
            </div>
            <p className="flujo-detalle">{e.detalle}</p>
            {estado && alEtapa ? <button type="button" className="sutil etapa-inspeccionar" onClick={() => alEtapa(e)} aria-label={`Inspeccionar etapa: ${e.nombre}`}>Ver evidencia</button> : null}
          </div>
        </li>
      ))}
    </ol>
  );
}

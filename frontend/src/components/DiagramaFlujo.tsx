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
import type { RunState } from "../lib/contracts";
import { Chip } from "./ui";

type EstadoEtapa = "hecha" | "en-curso" | "esperando" | "fallida" | "pendiente";

interface Etapa {
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
};

const TONO: Record<EstadoEtapa, "" | "ok" | "aviso" | "error" | "acento"> = {
  hecha: "ok",
  "en-curso": "acento",
  esperando: "aviso",
  fallida: "error",
  pendiente: "",
};

function calcular(estado: RunState): Etapa[] {
  const siguiente = (estado.next_step ?? "").toLowerCase();
  const plan = estado.plan;
  const pruebas = estado.evidence.test_runs ?? [];
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
      "Propone el cambio y lo aplica en un sandbox aislado, nunca en tu repositorio.",
      estado.outputs.coder_output !== null,
      {
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
        fallida: pruebas.length > 0 && pruebas.every((p) => p.exit_code !== 0),
        detalleHecho: pruebas.length
          ? `${pruebas.filter((p) => p.exit_code === 0).length} de ${pruebas.length} objetivo(s) correctos.`
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

export function DiagramaFlujo({ estado }: { estado: RunState | null }) {
  if (!estado) {
    return (
      <p className="vacio">
        Selecciona una ejecución para ver por qué punto del flujo va.
      </p>
    );
  }

  const etapas = calcular(estado);

  return (
    <ol className="flujo" aria-label="Etapas del flujo de ejecución">
      {etapas.map((e, i) => (
        <li key={e.id} className={`flujo-etapa ${e.estado}`}>
          <div className="flujo-marca" aria-hidden="true">
            <span className="flujo-indice">{i + 1}</span>
          </div>
          <div className="flujo-cuerpo">
            <div className="fila">
              <span className="flujo-nombre">{e.nombre}</span>
              <Chip tono={TONO[e.estado]}>{ETIQUETA_ESTADO[e.estado]}</Chip>
              <span className="mono tenue">{e.nodo}</span>
            </div>
            <p className="flujo-detalle">{e.detalle}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}

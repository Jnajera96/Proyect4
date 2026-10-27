/**
 * Tipos del contrato backend.
 *
 * **Fuente unica de verdad: `frontend/contracts.json`.** Ese fichero lo genera
 * `tools/export_contracts.py` a partir de los modelos Pydantic y una prueba
 * comprueba que esta al dia. Los tipos de aqui **no se escriben a mano**: los
 * enumerados se derivan del JSON importado, de modo que anadir un evento o un
 * estado en el backend aparece aqui sin tocar nada -y si no aparece, el
 * `typecheck` falla en lugar de dejar pasar un `undefined` al navegador.
 *
 * Los tipos de los estados y los eventos se derivan con `typeof enum[number]`,
 * que es la forma de convertir una lista literal de cadenas en una union de
 * cadenas sin repetirla.
 */
import contratos from "../../contracts.json";

export const schemas = contratos.schemas;

/** Los eventos que el backend puede emitir, como union de cadenas. */
export type EventKind = (typeof schemas.EventKind.enum)[number];

/** Los estados de una ejecucion. */
export type RunStatus = (typeof schemas.RunStatus.enum)[number];

/** La clasificacion de la instruccion. */
export type Intent = (typeof schemas.Intent.enum)[number];

/** La decision de una puerta humana. */
export type ApprovalDecision =
  (typeof schemas.ApprovalDecision.enum)[number];

// ---------------------------------------------------------------------------
// Los conjuntos canonicos de F10.
// ---------------------------------------------------------------------------

/**
 * Los eventos **canonicos** de F10: los hitos del ciclo de vida por nodo.
 *
 * Son un conjunto cerrado y el frontend hace un `switch` exhaustivo sobre ellos.
 * Un tipo nuevo no se cuela sin que alguien lo note: el `never` del final del
 * `switch` deja de compilar.
 */
export const EVENTOS_HITO = [
  "requirements.completed",
  "plan.completed",
  "coder.completed",
  "tests.completed",
] as const;

/**
 * Los eventos de **puerta humana y de resultado** de F10.
 *
 * `run.awaiting_human` es la senal de que la ejecucion pauso en una de las dos
 * puertas; **cual** se lee del estado (`RunStatus`) o del `next_step`, no del
 * nombre del nodo, que es un dato y no un tipo.
 */
export const EVENTOS_PUERTA = [
  "run.awaiting_human",
  "run.completed",
  "run.failed",
] as const;

/**
 * `run.done` **no es un hito ni un resultado**: es la senal de que el flujo SSE se
 * cierra. Se sigue consumiendo porque es lo que cierra la conexion; se retiro del
 * resto de sitios en F11 (AUD-11).
 */
export const EVENTO_CIERRE: EventKind = "run.done";

/** Todos los eventos que el cliente se suscribe a escuchar. */
export const EVENTOS_ESCUCHADOS: EventKind[] = [
  ...EVENTOS_HITO,
  ...EVENTOS_PUERTA,
  EVENTO_CIERRE,
];

// ---------------------------------------------------------------------------
// Formas de las respuestas.
// ---------------------------------------------------------------------------

/** Un evento del progreso, con el sobre completo (`seq`/`at`/`kind`/`data`). */
export interface RunEvent {
  seq: number;
  at: string;
  kind: EventKind;
  data: Record<string, unknown>;
}

/** Vista ligera de una ejecucion, para el listado. */
export interface RunSummary {
  run_id: string;
  trace_id: string;
  status: RunStatus;
  intent: string | null;
  created_at: string;
  updated_at: string;
  error_count: number;
  awaiting_approval: boolean;
}

/** Un proyecto registrado, contra el que se puede ejecutar. */
export interface Project {
  project_id: string;
  name: string;
  repo_path: string;
  created_at: string;
}

/** Un fichero tocado por el cambio, con su recuento de lineas. */
export interface FileChange {
  path: string;
  added: number;
  removed: number;
  sha256: string;
}

/** Una linea de la transcripcion, con su tramo de tiempo. */
export interface Segment {
  start_s: number;
  end_s: number;
  text: string;
}

/**
 * Resultado de `POST /transcriptions`. **No crea ninguna ejecucion**: el audio se
 * convierte en texto y el texto se le ensena a la persona para que lo confirme.
 */
export interface Transcript {
  text: string;
  language: string;
  confidence: number;
  duration_s: number;
  provider: string;
  segments: Segment[];
  low_confidence: boolean;
}

/**
 * Lo que el usuario **pidio** (`RunOptions`), distinto de lo que el Supervisor
 * **entendio** (`TaskInterpretation`). Se muestran por separado a proposito: es lo
 * que permite ver una interpretacion que se desvio de la peticion.
 */
export interface RunOptions {
  repo_path: string | null;
  allowed_paths: string[];
  protected_paths: string[];
}

/**
 * Presupuesto de la ejecucion. Los limites y lo consumido; lo que queda se
 * calcula restando, no se inventa un campo que el backend no manda.
 */
export interface Budget {
  max_tokens: number;
  used_tokens: number;
  used_input_tokens: number;
  used_output_tokens: number;
  max_tool_calls: number;
  used_tool_calls: number;
  max_model_calls: number;
  used_model_calls: number;
  max_seconds: number;
  elapsed_seconds: number;
  max_cost: number | null;
  used_cost: number;
  max_review_cycles: number;
  review_cycles_used: number;
}

/**
 * Registro de una decision humana (RNF-T2): quien, cuando, que accion, con que
 * motivo y sobre que contenido exacto (`content_sha256`).
 */
export interface Approval {
  action: string;
  actor: string;
  decided_at: string;
  content_sha256: string;
  decision: ApprovalDecision;
  reason: string;
}

/** La propuesta del Coder. */
export interface CodeChange {
  rationale: string;
  diff: string;
  diff_sha256: string;
  files_changed: FileChange[];
}

/** Evidencia de una ejecucion de pruebas. */
export interface TestRun {
  target: string;
  exit_code: number;
  duration_s: number;
  stdout: string;
  stderr: string;
  argv: string[];
}

/** Un hallazgo del Reviewer o del Researcher. */
export interface Finding {
  severity: "info" | "low" | "medium" | "high" | "critical";
  path: string;
  line: number | null;
  explanation: string;
  evidence: string;
}

/** El veredicto del Reviewer. */
export interface ReviewVerdict {
  decision: "accept" | "request_changes" | "escalate";
  summary: string;
  findings: Finding[];
  required_fixes: string[];
}

/** Lo que el Supervisor **entendio** de la peticion. */
export interface TaskInterpretation {
  intent: Intent;
  scope: {
    repo_path: string;
    allowed_paths: string[];
    protected_paths: string[];
    max_files_changed: number;
    max_lines_changed: number;
  };
  confidence: number;
  rationale: string;
  constraints: string[];
}

/** El plan de ejecucion del Supervisor. */
export interface RunPlan {
  subtasks: {
    id: string;
    description: string;
    agent: string;
    status: string;
    done_criteria: string;
  }[];
  rationale: string;
  max_review_cycles: number;
}

/** Un error tipado dentro de la ejecucion. */
export interface RunError {
  error_class: string;
  agent: string;
  message: string;
  recoverable: boolean;
  occurred_at: string;
  subtask_id: string | null;
}

/** El informe final. Las cuatro secciones de RF-13. */
export interface FinalReport {
  summary: string;
  changes_applied: string[];
  tests_executed: string[];
  pending: string[];
  review: string;
}

/** El estado completo de una ejecucion. */
export interface RunState {
  run_id: string;
  trace_id: string;
  status: RunStatus;
  created_at: string;
  updated_at: string;
  instruction: {
    text: string;
    source: string;
    confirmed_by_user: boolean;
    transcript_meta: {
      provider: string;
      language: string;
      confidence: number;
      duration_s: number;
      low_confidence_warned: boolean;
    } | null;
  };
  options: RunOptions;
  interpretation: TaskInterpretation | null;
  plan: RunPlan | null;
  plan_index: number;
  artifacts: {
    diff: string | null;
    changed_files: FileChange[];
    base_commit: string | null;
    worktree_path: string | null;
  };
  outputs: {
    coder_output: CodeChange | null;
    researcher_output: { findings: Finding[]; unknowns: string[] } | null;
    reviewer_output: ReviewVerdict | null;
  };
  evidence: { test_runs: TestRun[]; findings: Finding[] };
  approvals: Approval[];
  budget: Budget;
  errors: RunError[];
  human_feedback: string[];
  final_report: FinalReport | null;
  next_step: string | null;
}

/** Respuesta de `/health`. */
export interface Health {
  status: string;
  fase: string;
  stt: boolean;
  provider_configuration?: {
    status: "not_configured" | "configured" | "offline";
    remote_enabled: boolean;
    missing_fields: string[];
    credential_validated: boolean;
    inference_verified: boolean;
    message: string;
  };
  ejecuciones: number;
  proyectos: number;
}

/** Error estructurado que devuelve la API con `error_class`. */
export interface ApiError {
  detail: string | unknown;
  error_class?: string;
}

export const ESTADOS_TERMINALES: ReadonlySet<RunStatus> = new Set<RunStatus>([
  "completed",
  "failed",
  "needs_human",
  "cancelled",
]);

/** Etiquetas legibles de los estados, para la interfaz (en castellano). */
export const ETIQUETA_ESTADO: Record<RunStatus, string> = {
  planned: "en cola",
  running: "ejecutando",
  awaiting_human_requirements_confirmation: "esperando confirmación de requisitos",
  awaiting_approval: "esperando aprobación",
  completed: "completada",
  failed: "fallida",
  needs_human: "requiere intervención",
  cancelled: "cancelada",
};

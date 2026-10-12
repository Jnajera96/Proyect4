/**
 * Cliente HTTP de la API de `ai_swe`.
 *
 * Una sola capa para todas las llamadas, por tres razones:
 *   - Los errores de dominio llegan estructurados (`error_class`). Centralizarlos
 *     permite convertirlos en un tipo propio y que la interfaz ramifique por clase
 *     en lugar de leer el texto del mensaje.
 *   - Un error de red y un 4xx se distinguen aqui, no en cada llamada.
 *   - Las rutas viven en un solo sitio.
 */
import type {
  ApiError,
  FinalReport,
  Health,
  Project,
  RunState,
  RunSummary,
} from "./contracts";

/** Error de la API con la clase de dominio, si la trae. */
export class ErrorApi extends Error {
  readonly status: number;
  readonly errorClass: string | null;

  constructor(status: number, mensaje: string, errorClass: string | null) {
    super(mensaje);
    this.name = "ErrorApi";
    this.status = status;
    this.errorClass = errorClass;
  }
}

/** Convierte el cuerpo de error del backend en un mensaje legible. */
function mensajeDeError(cuerpo: unknown, status: number): string {
  if (cuerpo && typeof cuerpo === "object" && "detail" in cuerpo) {
    const detalle = (cuerpo as ApiError).detail;
    if (typeof detalle === "string") return detalle;
    // 422 de Pydantic: `detail` es una lista de errores. Se resume.
    if (Array.isArray(detalle)) {
      return detalle
        .map((d) => {
          const e = d as { loc?: unknown[]; msg?: string };
          const campo = Array.isArray(e.loc) ? e.loc.join(".") : "";
          return campo ? `${campo}: ${e.msg ?? ""}` : (e.msg ?? "");
        })
        .join("; ");
    }
  }
  return `la petición falló con HTTP ${status}`;
}

async function pedir<T>(ruta: string, init?: RequestInit): Promise<T> {
  let respuesta: Response;
  try {
    respuesta = await fetch(ruta, init);
  } catch (causa) {
    // Fallo de red: no hay respuesta. Se distingue de un 4xx para que la interfaz
    // pueda decir "servidor inaccesible" en lugar de "peticion rechazada".
    throw new ErrorApi(0, `no se pudo contactar con el servidor: ${String(causa)}`, null);
  }

  const texto = await respuesta.text();
  let cuerpo: unknown = null;
  if (texto) {
    try {
      cuerpo = JSON.parse(texto);
    } catch {
      cuerpo = texto;
    }
  }

  if (!respuesta.ok) {
    const clase =
      cuerpo && typeof cuerpo === "object" && "error_class" in cuerpo
        ? String((cuerpo as ApiError).error_class)
        : null;
    throw new ErrorApi(respuesta.status, mensajeDeError(cuerpo, respuesta.status), clase);
  }
  return cuerpo as T;
}

export const api = {
  health: () => pedir<Health>("/health"),

  listarRuns: () => pedir<RunSummary[]>("/runs"),

  obtenerRun: (runId: string) => pedir<RunState>(`/runs/${encodeURIComponent(runId)}`),

  listarProyectos: () => pedir<Project[]>("/projects"),

  crearProyecto: (name: string, repoPath: string) =>
    pedir<Project>("/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, repo_path: repoPath }),
    }),

  crearRun: (instruccion: string, projectId?: string) =>
    pedir<RunState>("/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        instruction: instruccion,
        ...(projectId ? { project_id: projectId } : {}),
      }),
    }),

  /** Responde a la puerta de requisitos. Admite confirmar, rechazar o corregir. */
  confirmarRequisitos: (
    runId: string,
    decision: string,
    correcciones?: { intent?: string; constraints?: string[]; rationale?: string },
  ) =>
    pedir<RunState>(`/runs/${encodeURIComponent(runId)}/confirm-requirements`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision, ...correcciones }),
    }),

  /** Responde a la puerta de aprobacion del cambio. */
  aprobar: (runId: string, decision: string) =>
    pedir<RunState>(`/runs/${encodeURIComponent(runId)}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision }),
    }),

  /** El informe final de una ejecucion, si ya existe. */
  informe: async (runId: string): Promise<FinalReport | null> => {
    const estado = await api.obtenerRun(runId);
    return estado.final_report;
  },
};

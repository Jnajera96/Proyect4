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
  Transcript,
} from "./contracts";
import { claveActiva } from "./auth";

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

/**
 * Mensaje de interfaz para un fallo de acceso.
 *
 * Los 401 y 403 **no** muestran el detalle del backend. Ese detalle viene en el
 * idioma del servidor, habla de cabeceras y -en el 403- nombra el rol que la
 * credencial tiene: nada de eso ayuda a quien esta delante y parte de eso es
 * informacion de mas. Los demas fallos si conservan su mensaje, porque un 422 de
 * validacion existe precisamente para decir que campo esta mal.
 *
 * Cual de los dos 401 es se decide por un hecho del **cliente**, no del servidor:
 * si se presento una credencial y la rechazo, es que no vale; si no se presento
 * ninguna, es que hace falta una. Nunca se repite lo que se envio.
 */
export function mensajeVisible(causa: unknown, habiaCredencial: boolean): string {
  if (causa instanceof ErrorApi) {
    if (causa.status === 401) {
      return habiaCredencial ? "Clave API no válida." : "Autenticación requerida.";
    }
    if (causa.status === 403) return "No tienes permisos para realizar esta acción.";
  }
  return causa instanceof Error ? causa.message : String(causa);
}

/**
 * Rol que el backend atribuye a la credencial, si lo dice al rechazar.
 *
 * **De donde sale, y por que es best-effort.** La API no expone el rol en ningun
 * endpoint: no hay un `/me` ni nada equivalente, y la unica respuesta que lo
 * nombra es el 403, cuyo detalle dice que rol pide la accion y cual tiene la
 * credencial. Se lee de ahi -es informacion real sobre la propia credencial, no
 * un invento- y se usa solo para dejar de ofrecer acciones que van a ser
 * rechazadas. Mientras no haya un rechazo no se conoce el rol, y entonces la
 * interfaz no oculta nada: la autorizacion la hace el backend de todas formas.
 *
 * Si el backend cambia la redaccion esto devuelve `null` y la interfaz vuelve a
 * no conocer el rol: se pierde la comodidad, no la seguridad. Lo limpio seria un
 * endpoint de solo lectura que declare la identidad; es una decision del backend
 * y no se toma desde el rediseno del frontend.
 */
export function rolDelRechazo(causa: unknown): string | null {
  if (!(causa instanceof ErrorApi) || causa.status !== 403) return null;
  const coincidencia = /tiene '([a-z]+)'/.exec(causa.message);
  return coincidencia ? coincidencia[1] : null;
}

async function pedir<T>(ruta: string, init?: RequestInit): Promise<T> {
  // La clave se lee **en cada peticion**, no al cargar el modulo: guardarla
  // mientras la pagina esta abierta debe aplicarse a las siguientes llamadas sin
  // recargar. Con la autenticacion desactivada el servidor ignora la cabecera.
  const clave = claveActiva();
  const conClave: RequestInit = clave
    ? { ...init, headers: { ...init?.headers, "X-API-Key": clave } }
    : (init ?? {});
  let respuesta: Response;
  try {
    respuesta = await fetch(ruta, conClave);
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

  /**
   * Lista de ejecuciones.
   *
   * Se pide la pagina maxima que el servidor admite por defecto (`limit=200`,
   * contra los 50 que devuelve sin parametro): sin eso el historial se cortaba en
   * 50 filas sin que la interfaz lo dijera, y el panel de estado contabilizaba el
   * total real de `/health`. Si un servidor tiene `max_page_size` por debajo de
   * 200 el listado responde 422 -es un limite suyo, no un fallo de la interfaz-,
   * y se vuelve a pedir la pagina por defecto antes que quedarse sin historial.
   */
  listarRuns: async (): Promise<RunSummary[]> => {
    try {
      return await pedir<RunSummary[]>("/runs?limit=200");
    } catch (causa) {
      if (causa instanceof ErrorApi && causa.status === 422) {
        return await pedir<RunSummary[]>("/runs");
      }
      throw causa;
    }
  },

  obtenerRun: (runId: string) => pedir<RunState>(`/runs/${encodeURIComponent(runId)}`),

  listarProyectos: () => pedir<Project[]>("/projects"),

  obtenerProyecto: (projectId: string) =>
    pedir<Project>(`/projects/${encodeURIComponent(projectId)}`),

  /**
   * Sube audio y devuelve la transcripcion. **No crea ninguna ejecucion**
   * (`RF-02`): el texto vuelve a la persona, que lo revisa y decide.
   *
   * El `Content-Type` no se fija a mano: lo pone el navegador con el `boundary`
   * del formulario, y fijarlo rompe la peticion.
   */
  transcribir: (audio: Blob, nombre: string, vocabulario?: string) => {
    const cuerpo = new FormData();
    cuerpo.append("audio", audio, nombre);
    if (vocabulario?.trim()) cuerpo.append("vocabulary", vocabulario.trim());
    return pedir<Transcript>("/transcriptions", { method: "POST", body: cuerpo });
  },

  crearProyecto: (name: string, repoPath: string) =>
    pedir<Project>("/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, repo_path: repoPath }),
    }),

  /**
   * Crea una ejecucion.
   *
   * `meta` es la transcripcion de origen cuando la instruccion viene de un
   * dictado. **Mando `meta` la ejecucion se registra como de voz** y el backend
   * exige entonces los metadatos del reconocimiento (`RF-03`): sin ellos, la
   * peticion es rechazada, y sin ellos la ejecucion pierde el rastro de que la
   * instruccion se dicto -que es justo lo que el campo `transcript_meta` del
   * estado guarda-. Sin `meta`, la instruccion es de texto y el campo no se
   * envia, que es lo que el contrato pide.
   */
  crearRun: (instruccion: string, projectId?: string, meta?: Transcript) =>
    pedir<RunState>("/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        instruction: instruccion,
        ...(projectId ? { project_id: projectId } : {}),
        ...(meta
          ? {
              source: "voice",
              transcript_meta: {
                provider: meta.provider,
                language: meta.language,
                confidence: meta.confidence,
                duration_s: meta.duration_s,
                // La interfaz ensena el aviso de confianza baja antes de dejar
                // confirmar el texto, asi que esto describe lo que ocurrio.
                low_confidence_warned: meta.low_confidence,
              },
            }
          : {}),
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

  /**
   * Responde a la puerta de aprobacion del cambio (F12).
   *
   * `comments` solo tiene sentido al **solicitar cambios** -son las instrucciones
   * para la siguiente iteracion- y el backend los ignora en las otras decisiones.
   * Se envian solo si hay algo escrito: mandar una cadena vacia no anade nada.
   */
  aprobar: (runId: string, decision: string, comments?: string) =>
    pedir<RunState>(`/runs/${encodeURIComponent(runId)}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        decision,
        ...(comments?.trim() ? { comments: comments.trim() } : {}),
      }),
    }),

  /** El informe final de una ejecucion, si ya existe. */
  informe: async (runId: string): Promise<FinalReport | null> => {
    const estado = await api.obtenerRun(runId);
    return estado.final_report;
  },
};

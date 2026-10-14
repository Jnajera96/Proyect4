/**
 * Raiz de la aplicacion.
 *
 * Orquesta el ciclo completo: comprobar el servidor, registrar un proyecto,
 * lanzar una ejecucion, seguir su progreso en vivo, responder a las dos puertas
 * humanas y leer el informe final. El estado de la ejecucion se **relee del
 * servidor** cuando llega una senal relevante, en lugar de reconstruirse en el
 * cliente: el servidor es la fuente autoritativa de donde esta la ejecucion, y el
 * SSE es la senal de que algo ha cambiado.
 *
 * La etiqueta de fase se lee de `/health`, nunca de un literal. Es lo que resuelve
 * AUD-13 de raiz: si la fase cambia en el backend, la interfaz la refleja sola.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, ErrorApi } from "./lib/api";
import { borrarClave, claveGuardada, guardarClave, useClaveApi } from "./lib/auth";
import {
  ESTADOS_TERMINALES,
  ETIQUETA_ESTADO,
  type Health,
  type Project,
  type RunState,
  type RunSummary,
} from "./lib/contracts";
import { hitosDe, useEventosRun } from "./hooks/useEventosRun";
import { PuertaAprobacion } from "./components/PuertaAprobacion";
import { PuertaRequisitos } from "./components/PuertaRequisitos";
import { Timeline } from "./components/Timeline";
import { Chip, Fila, Panel, Vacio, hora } from "./components/ui";

function tonoDeEstado(estado: string): "" | "ok" | "aviso" | "error" | "acento" {
  if (estado === "completed") return "ok";
  if (estado === "failed" || estado === "cancelled") return "error";
  if (estado.startsWith("awaiting")) return "aviso";
  if (estado === "needs_human") return "error";
  if (estado === "running") return "acento";
  return "";
}

export function App() {
  const [salud, setSalud] = useState<Health | null>(null);
  const [saludError, setSaludError] = useState(false);
  const [proyectos, setProyectos] = useState<Project[]>([]);
  const [runs, setRuns] = useState<RunSummary[]>([]);

  const [instruccion, setInstruccion] = useState(
    "Analiza el proyecto e identifica los errores principales.",
  );
  const [projectId, setProjectId] = useState<string>("");
  const [nombreProyecto, setNombreProyecto] = useState("");
  const [rutaProyecto, setRutaProyecto] = useState("");

  const [runId, setRunId] = useState<string | null>(null);
  const [estado, setEstado] = useState<RunState | null>(null);
  const [lanzando, setLanzando] = useState(false);
  const [errorAccion, setErrorAccion] = useState<string | null>(null);

  // Clave de API. Se lee del almacen con el hook para que la interfaz reaccione
  // a guardarla u olvidarla; el borrador es solo el campo de texto.
  const claveApi = useClaveApi();
  const [borradorClave, setBorradorClave] = useState("");
  const [mensajeClave, setMensajeClave] = useState<string | null>(null);

  const { eventos, conexion } = useEventosRun(runId);

  // Puente de diagnostico para el verificador (`tools/verify_frontend.py`).
  //
  // Expone **lectura del estado real** de la aplicacion. No simula nada ni
  // escribe estado: el verificador lo que hace es **pulsar los botones de verdad**
  // y luego leer aqui lo que la interfaz tiene, en lugar de reimplementar la
  // logica y comprobarse a si mismo. En un shim de DOM este puente no existiria, y
  // por eso la verificacion corre en un motor real.
  useEffect(() => {
    (window as unknown as { __AISWE__?: unknown }).__AISWE__ = {
      runId,
      status: estado?.status ?? null,
      eventos: eventos.length,
      conexion,
      // Los tipos recibidos, en orden: es lo que prueba que el cliente consume el
      // conjunto canonico de F10 y no los nombres heredados.
      tipos: eventos.map((e) => e.kind),
      hitos: hitosDe(eventos).map((h) => h.kind),
    };
  }, [runId, estado, eventos, conexion]);


  // Se releen el estado y la lista cuando cambia el numero de eventos: cada
  // evento es la senal de que algo se movio. El ref evita reejecutar cuando el
  // recuento no cambia.
  const nEventos = eventos.length;
  const ultimoRef = useRef(-1);
  const refrescar = useCallback(async (id: string) => {
    try {
      setEstado(await api.obtenerRun(id));
    } catch {
      /* el estado puede no estar aun; se reintenta con el proximo evento */
    }
    try {
      setRuns(await api.listarRuns());
    } catch {
      /* idem */
    }
  }, []);

  useEffect(() => {
    if (!runId || nEventos === ultimoRef.current) return;
    ultimoRef.current = nEventos;
    void refrescar(runId);
  }, [runId, nEventos, refrescar]);

  // El estado inicial de la ejecucion se carga una vez al fijarla, para no esperar
  // al primer evento.
  useEffect(() => {
    if (runId) void refrescar(runId);
  }, [runId, refrescar]);

  // **Sondeo mientras la ejecucion no es terminal.**
  //
  // Por que no basta con reaccionar a los eventos. Una ejecucion puede **cambiar de
  // estado sin emitir un evento**: al confirmar los requisitos, el grafo pasa de
  // `awaiting_human_requirements_confirmation` a `running` sin que el motor escriba
  // nada entre medias. Un cliente que solo releyera el estado al recibir un evento
  // se quedaria mostrando la puerta ya respondida hasta que llegara el siguiente
  // hito -o para siempre si el hito tarda-. El sintoma se detecto en la verificacion
  // del frontend: la interfaz no reflejaba que la ejecucion habia avanzado.
  //
  // El sondeo es la red de seguridad: mientras el estado no sea terminal, se relee
  // cada 900 ms. Los eventos siguen siendo la via rapida; esto garantiza que la
  // vista no se queda atras.
  useEffect(() => {
    if (!runId || !estado || ESTADOS_TERMINALES.has(estado.status)) return;
    const temporizador = window.setInterval(() => void refrescar(runId), 900);
    return () => window.clearInterval(temporizador);
  }, [runId, estado, refrescar]);

  const cargarInicial = useCallback(async () => {
    try {
      setSalud(await api.health());
      setSaludError(false);
    } catch {
      setSaludError(true);
    }
    try {
      setProyectos(await api.listarProyectos());
    } catch {
      /* sin proyectos se puede ejecutar contra la ruta por defecto */
    }
    try {
      setRuns(await api.listarRuns());
    } catch {
      /* idem */
    }
  }, []);

  useEffect(() => {
    void cargarInicial();
  }, [cargarInicial]);

  const hitos = useMemo(() => hitosDe(eventos), [eventos]);

  async function registrarProyecto() {
    setErrorAccion(null);
    try {
      const p = await api.crearProyecto(nombreProyecto, rutaProyecto);
      setProyectos((previos) => [p, ...previos]);
      setProjectId(p.project_id);
      setNombreProyecto("");
      setRutaProyecto("");
    } catch (e) {
      setErrorAccion(e instanceof ErrorApi ? e.message : String(e));
    }
  }

  async function lanzar() {
    const texto = instruccion.trim();
    if (!texto) return;
    setLanzando(true);
    setErrorAccion(null);
    setEstado(null);
    try {
      const creado = await api.crearRun(texto, projectId || undefined);
      setRunId(creado.run_id);
      setEstado(creado);
    } catch (e) {
      setErrorAccion(e instanceof ErrorApi ? e.message : String(e));
    } finally {
      setLanzando(false);
    }
  }

  // La puerta pendiente se deriva del **estado**, no del ultimo evento: el estado
  // es la fuente autoritativa de donde esta la ejecucion, y sobrevive a una recarga.
  const puerta: "requisitos" | "aprobacion" | null =
    estado?.status === "awaiting_human_requirements_confirmation"
      ? "requisitos"
      : estado?.status === "awaiting_approval"
        ? "aprobacion"
        : null;

  const conectado = conexion === "conectado";
  const terminado = estado ? ESTADOS_TERMINALES.has(estado.status) : false;

  return (
    <main className="app">
      <header className="cabecera">
        <div>
          <h1 className="titulo">AI Software Engineering System</h1>
          <p className="subtitulo" style={{ margin: "0.15rem 0 0" }}>
            Proyecto 4 · Equipo 4
          </p>
        </div>
        {saludError ? (
          <Chip tono="error">servidor inaccesible</Chip>
        ) : salud ? (
          <Chip tono="ok">
            servidor ok · fase {salud.fase} · {salud.ejecuciones} ejecución(es)
          </Chip>
        ) : (
          <Chip pulsa>comprobando…</Chip>
        )}
      </header>

      {/* -------------------------------------------------------- Acceso */}
      <div className="seccion-titulo">Acceso</div>
      <Panel nota="La clave solo hace falta si el servidor tiene la autenticación activada (AI_SWE_API_KEYS con al menos una clave). Se guarda en este navegador y se envía con cada petición; con la autenticación desactivada el servidor la ignora.">
        <label htmlFor="api-key">Clave de API</label>
        <Fila sep>
          <input
            id="api-key"
            type="password"
            value={borradorClave}
            onChange={(e) => setBorradorClave(e.target.value)}
            placeholder="pegar aquí la clave"
            autoComplete="off"
            style={{ flex: 1 }}
          />
          <button
            id="btn-guardar-clave"
            className="primario"
            disabled={!borradorClave.trim()}
            onClick={() => {
              guardarClave(borradorClave.trim());
              setBorradorClave("");
              setMensajeClave("clave guardada");
            }}
          >
            Guardar
          </button>
          {claveGuardada() ? (
            <button
              onClick={() => {
                borrarClave();
                setMensajeClave("clave borrada");
              }}
            >
              Olvidar
            </button>
          ) : null}
        </Fila>
        <p className="tenue">
          {claveApi
            ? "hay una clave guardada; se envía con cada petición, incluido el flujo de eventos."
            : "no hay ninguna clave guardada en este navegador."}
          {mensajeClave ? ` · ${mensajeClave}` : ""}
        </p>
      </Panel>

      {/* -------------------------------------------------------- Entrada */}
      <div className="seccion-titulo">Nueva ejecución</div>
      <Panel
        nota="La ejecución corre en el servidor. El progreso llega por eventos: esta página no espera a que termine."
      >
        <label htmlFor="instruccion">Instrucción</label>
        <textarea
          id="instruccion"
          value={instruccion}
          onChange={(e) => setInstruccion(e.target.value)}
          placeholder="Analiza este proyecto, identifica los errores principales y corrige el código."
        />

        <div className="rejilla">
          <div>
            <label htmlFor="proyecto">Proyecto</label>
            <select
              id="proyecto"
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
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
              <option value="">(sin proyecto · ruta por defecto)</option>
              {proyectos.map((p) => (
                <option key={p.project_id} value={p.project_id}>
                  {p.name} — {p.repo_path}
                </option>
              ))}
            </select>
          </div>
        </div>

        <Fila sep>
          <button id="btn-crear" className="primario" disabled={lanzando} onClick={() => void lanzar()}>
            {lanzando ? "Lanzando…" : "Ejecutar"}
          </button>
          <span className="tenue">La ejecución devuelve el identificador al instante</span>
        </Fila>

        <details style={{ marginTop: "0.85rem" }}>
          <summary className="sutil" style={{ cursor: "pointer" }}>
            Registrar un proyecto
          </summary>
          <div className="stack" style={{ marginTop: "0.75rem" }}>
            <div>
              <label htmlFor="p-nombre">Nombre</label>
              <input
                id="p-nombre"
                type="text"
                value={nombreProyecto}
                onChange={(e) => setNombreProyecto(e.target.value)}
                placeholder="mi-repositorio"
              />
            </div>
            <div>
              <label htmlFor="p-ruta">Ruta del repositorio</label>
              <input
                id="p-ruta"
                type="text"
                value={rutaProyecto}
                onChange={(e) => setRutaProyecto(e.target.value)}
                placeholder="C:\\ruta\\al\\repositorio"
              />
            </div>
            <Fila>
              <button
                disabled={!nombreProyecto.trim() || !rutaProyecto.trim()}
                onClick={() => void registrarProyecto()}
              >
                Registrar
              </button>
              <span className="tenue">La ruta se valida al registrar, no al ejecutar</span>
            </Fila>
          </div>
        </details>

        {errorAccion ? (
          <p className="aviso" role="alert">
            {errorAccion}
          </p>
        ) : null}
      </Panel>

      {/* --------------------------------------------------- Ejecución viva */}
      {runId ? (
        <>
          <div className="seccion-titulo">Progreso</div>
          <div className="rejilla rejilla-doble">
            <Panel>
              <div className="fila" style={{ marginBottom: "0.75rem" }}>
                <strong className="mono">{runId}</strong>
                {estado ? (
                  <Chip tono={tonoDeEstado(estado.status)}>
                    {ETIQUETA_ESTADO[estado.status]}
                  </Chip>
                ) : null}
                {conectado ? (
                  <Chip tono="acento" pulsa>
                    en vivo
                  </Chip>
                ) : conexion === "cerrado" ? (
                  <Chip>flujo cerrado</Chip>
                ) : conexion === "error" ? (
                  <Chip tono="error">conexión perdida</Chip>
                ) : null}
              </div>
              <Timeline hitos={hitos} />
            </Panel>

            {estado ? (
              <Panel titulo="Detalles" nota="Leídos del estado que el servidor tiene guardado.">
                <dl className="datos">
                  <dt>intención</dt>
                  <dd>{estado.interpretation?.intent ?? "—"}</dd>
                  <dt>subtareas</dt>
                  <dd>{estado.plan ? `${estado.plan.subtasks.length} (índice ${estado.plan_index})` : "—"}</dd>
                  <dt>ficheros</dt>
                  <dd>{estado.artifacts.changed_files?.length ?? 0}</dd>
                  <dt>pruebas</dt>
                  <dd>{estado.evidence.test_runs?.length ?? 0}</dd>
                  <dt>errores</dt>
                  <dd>{estado.errors.length}</dd>
                </dl>
                {estado.plan ? (
                  <>
                    <p className="seccion-titulo">Plan</p>
                    <ul className="limpia">
                      {estado.plan.subtasks.map((s) => (
                        <li key={s.id}>
                          <span className="mono">{s.id}</span> · {s.description}{" "}
                          <span className="tenue">({s.agent})</span>
                        </li>
                      ))}
                    </ul>
                  </>
                ) : null}
              </Panel>
            ) : null}
          </div>

          {/* -------------------------------------------------- Puertas */}
          {puerta === "requisitos" && estado ? (
            <PuertaRequisitos estado={estado} alDecidir={() => void refrescar(runId)} />
          ) : null}
          {puerta === "aprobacion" && estado ? (
            <PuertaAprobacion estado={estado} alDecidir={() => void refrescar(runId)} />
          ) : null}

          {/* -------------------------------------------------- Informe */}
          {terminado && estado?.final_report ? (
            <>
              <div className="seccion-titulo">Informe final</div>
              <Panel>
                <p>{estado.final_report.summary}</p>
                {estado.final_report.changes_applied?.length ? (
                  <>
                    <p className="seccion-titulo">Cambios aplicados</p>
                    <ul className="limpia">
                      {estado.final_report.changes_applied.map((c, i) => (
                        <li key={i}>{c}</li>
                      ))}
                    </ul>
                  </>
                ) : null}
                {estado.final_report.tests_executed?.length ? (
                  <>
                    <p className="seccion-titulo">Pruebas ejecutadas</p>
                    <ul className="limpia">
                      {estado.final_report.tests_executed.map((t, i) => (
                        <li key={i}>{t}</li>
                      ))}
                    </ul>
                  </>
                ) : null}
                {estado.final_report.pending?.length ? (
                  <>
                    <p className="seccion-titulo">Pendiente</p>
                    <ul className="limpia">
                      {estado.final_report.pending.map((p, i) => (
                        <li key={i}>{p}</li>
                      ))}
                    </ul>
                  </>
                ) : null}
                {estado.final_report.review ? (
                  <>
                    <p className="seccion-titulo">Revisión</p>
                    <p>{estado.final_report.review}</p>
                  </>
                ) : null}
              </Panel>
            </>
          ) : null}

          {/* --------------------------------------------------- Errores */}
          {estado?.errors.length ? (
            <>
              <div className="seccion-titulo">Errores</div>
              <Panel>
                <ul className="limpia">
                  {estado.errors.map((e, i) => (
                    <li key={i}>
                      <span className="mono">{e.error_class}</span>{" "}
                      <span className="tenue">({e.agent})</span> — {e.message}
                    </li>
                  ))}
                </ul>
              </Panel>
            </>
          ) : null}
        </>
      ) : null}

      {/* -------------------------------------------------------- Listado */}
      <div className="seccion-titulo">Ejecuciones</div>
      <Panel>
        {runs.length ? (
          <table>
            <thead>
              <tr>
                <th>run_id</th>
                <th>intención</th>
                <th>estado</th>
                <th>actualizado</th>
                <th>errores</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr
                  key={r.run_id}
                  className="clicable"
                  onClick={() => setRunId(r.run_id)}
                  title="Ver esta ejecución"
                >
                  <td className="mono">{r.run_id}</td>
                  <td>{r.intent ?? "—"}</td>
                  <td>
                    <Chip tono={tonoDeEstado(r.status)}>{ETIQUETA_ESTADO[r.status]}</Chip>
                  </td>
                  <td className="tenue">{hora(r.updated_at)}</td>
                  <td>{r.error_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Vacio>Sin ejecuciones todavía.</Vacio>
        )}
      </Panel>
    </main>
  );
}

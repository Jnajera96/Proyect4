/**
 * Raiz de la aplicacion.
 *
 * Orquesta el ciclo completo: comprobar el servidor, autenticarse si hace falta,
 * registrar un proyecto, lanzar una ejecucion, seguir su progreso en vivo,
 * responder a las dos puertas humanas y leer el informe final. El estado de la
 * ejecucion se **relee del servidor** cuando llega una senal relevante, en lugar
 * de reconstruirse en el cliente: el servidor es la fuente autoritativa de donde
 * esta la ejecucion, y el SSE es la senal de que algo ha cambiado.
 *
 * La etiqueta de fase se lee de `/health`, nunca de un literal. Es lo que resuelve
 * AUD-13 de raiz: si la fase cambia en el backend, la interfaz la refleja sola.
 *
 * **El acceso se deduce de respuestas reales.** El servidor puede exigir
 * credencial o no, y el cliente no lo sabe de antemano: lo averigua con la
 * primera lectura de datos protegidos -401 = la exige, 200 = esta abierta-.
 * `/health` no sirve para esto porque esta abierto en los dos modos a proposito.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, ErrorApi, mensajeVisible, rolDelRechazo } from "./lib/api";
import {
  borrarClave,
  enmascarar,
  guardarClave,
  hayClave,
  useClaveApi,
  type EstadoSesion,
} from "./lib/auth";
import {
  ESTADOS_TERMINALES,
  ETIQUETA_ESTADO,
  type Health,
  type Project,
  type RunState,
  type RunSummary,
} from "./lib/contracts";
import { hitosDe, useEventosRun } from "./hooks/useEventosRun";
import { PantallaAcceso } from "./components/PantallaAcceso";
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

/** Que respondio el servidor a las peticiones protegidas. */
type ResultadoCarga = "ok" | "401" | "fallo";

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

  // ---------------------------------------------------------------- acceso
  // `useClaveApi` suscribe este componente a la credencial: cambiarla o
  // olvidarla repinta. El flujo SSE hace lo mismo por su cuenta.
  const claveApi = useClaveApi();
  const [sesion, setSesion] = useState<EstadoSesion>("comprobando");
  const [mensajeAcceso, setMensajeAcceso] = useState<string | null>(null);
  const [cambiandoClave, setCambiandoClave] = useState(false);
  // El rol solo se conoce si el backend lo dijo al rechazar una accion; ver
  // `rolDelRechazo`. `null` = no se sabe, y entonces no se oculta nada.
  const [rol, setRol] = useState<string | null>(null);

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
      sesion,
    };
  }, [runId, estado, eventos, conexion, sesion]);


  // Se releen el estado y la lista cuando cambia el numero de eventos: cada
  // evento es la senal de que algo se movio. El ref evita reejecutar cuando el
  // recuento no cambia.
  const nEventos = eventos.length;
  const ultimoRef = useRef(-1);

  /**
   * Anota un fallo de acceso en el sitio que le corresponde.
   *
   * **401: la sesion se cae.** La credencial que valia dejo de valer -revocada,
   * cambiada en el servidor- o nunca valio. Se olvida y se vuelve a pedir; la
   * vista de la ejecucion se cierra porque sin credencial no se puede releer.
   *
   * **403: falta permiso.** La sesion sigue siendo valida; lo que no alcanza es
   * el rol. Se aprende cual es -el backend lo dice al rechazar- para dejar de
   * ofrecer acciones que van a ser rechazadas. Quien llama pone el mensaje.
   */
  const anotarFallo = useCallback((causa: unknown): void => {
    if (!(causa instanceof ErrorApi)) return;
    if (causa.status === 401) {
      borrarClave();
      setRol(null);
      setRunId(null);
      setEstado(null);
      setSesion("sesion-caida");
      setMensajeAcceso("Tu credencial dejó de ser válida. Introdúcela de nuevo.");
    } else if (causa.status === 403) {
      const detectado = rolDelRechazo(causa);
      if (detectado) setRol(detectado);
    }
  }, []);

  const refrescar = useCallback(
    async (id: string) => {
      try {
        setEstado(await api.obtenerRun(id));
      } catch (causa) {
        anotarFallo(causa);
      }
      try {
        setRuns(await api.listarRuns());
      } catch (causa) {
        anotarFallo(causa);
      }
    },
    [anotarFallo],
  );

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

  /**
   * Lee lo que el servidor tiene. `/health` esta abierto en los dos modos, asi
   * que **no** distingue si hace falta credencial: eso lo dicen las peticiones
   * protegidas, y por eso su resultado es el que devuelve esta funcion.
   */
  const cargarInicial = useCallback(async (): Promise<ResultadoCarga> => {
    try {
      setSalud(await api.health());
      setSaludError(false);
    } catch {
      setSaludError(true);
    }
    try {
      const proyectosLeidos = await api.listarProyectos();
      const runsLeidos = await api.listarRuns();
      setProyectos(proyectosLeidos);
      setRuns(runsLeidos);
      return "ok";
    } catch (causa) {
      if (causa instanceof ErrorApi && causa.status === 401) return "401";
      // Un fallo que no es de credencial no convierte esto en una pantalla de
      // acceso: la sesion puede estar bien y el servidor tener otro problema.
      return "fallo";
    }
  }, []);

  // **El modo del servidor se deduce, no se adivina.** Primera lectura de datos
  // protegidos: 401 = exige credencial; 200 = esta abierta.
  useEffect(() => {
    void (async () => {
      const resultado = await cargarInicial();
      if (resultado === "401") {
        const habia = hayClave();
        setSesion(habia ? "clave-invalida" : "sin-credencial");
        setMensajeAcceso(habia ? "Clave de API invalida." : null);
      } else if (resultado === "ok") {
        setSesion(hayClave() ? "autenticado" : "sin-autenticacion");
      } else {
        setSesion("sin-servidor");
      }
    })();
  }, [cargarInicial]);

  const hitos = useMemo(() => hitosDe(eventos), [eventos]);

  /**
   * Comprueba una credencial introducida contra el servidor.
   *
   * La credencial se guarda **antes** de comprobarla, porque es la unica forma de
   * que la peticion de comprobacion la lleve; si el servidor la rechaza se olvida
   * acto seguido. No se afirma que una credencial sea invalida por un fallo de
   * red: eso es un fallo, no un veredicto.
   */
  async function entrarConClave(clave: string) {
    setMensajeAcceso(null);
    setSesion("validando");
    guardarClave(clave);
    const resultado = await cargarInicial();
    if (resultado === "401") {
      borrarClave();
      setSesion("clave-invalida");
      setMensajeAcceso("Clave de API invalida.");
      return;
    }
    if (resultado === "fallo") {
      borrarClave();
      setSesion("sin-credencial");
      setMensajeAcceso("No se pudo comprobar la credencial. Inténtalo de nuevo.");
      return;
    }
    // Credencial nueva: el rol aprendido con la anterior ya no dice nada.
    setRol(null);
    setCambiandoClave(false);
    setSesion("autenticado");
  }

  /**
   * Cierra la sesion del frontend. No hay peticion de por medio porque no hay
   * nada que pedirle al servidor: una credencial es una clave, no una sesion con
   * estado. Olvidarla aqui **es** cerrar la sesion.
   */
  function cerrarSesion() {
    borrarClave();
    setRol(null);
    setCambiandoClave(false);
    setMensajeAcceso(null);
    setProyectos([]);
    setRuns([]);
    setRunId(null);
    setEstado(null);
    setSesion("sin-credencial");
  }

  async function registrarProyecto() {
    setErrorAccion(null);
    try {
      const p = await api.crearProyecto(nombreProyecto, rutaProyecto);
      setProyectos((previos) => [p, ...previos]);
      setProjectId(p.project_id);
      setNombreProyecto("");
      setRutaProyecto("");
    } catch (causa) {
      // `habiaCredencial` se lee **antes** de anotar el fallo: anotar un 401
      // olvida la credencial, y despues ya no se sabria si el mensaje correcto es
      // "no mandaste nada" o "esa no vale".
      const habiaCredencial = hayClave();
      anotarFallo(causa);
      setErrorAccion(mensajeVisible(causa, habiaCredencial));
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
    } catch (causa) {
      const habiaCredencial = hayClave();
      anotarFallo(causa);
      setErrorAccion(mensajeVisible(causa, habiaCredencial));
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

  // El rol, cuando se conoce, ordena la jerarquia que el backend aplica de
  // verdad: `reader` < `operator` < `admin`. Se usa **solo** para no ofrecer lo
  // que va a ser rechazado; la autorizacion la sigue haciendo el servidor, y
  // ocultar un boton no la sustituye.
  const puedeOperar = rol === null || rol !== "reader";
  const puedeAdministrar = rol === null || rol === "admin";

  // El chip de salud tiene que seguir siendo el **primero** de la cabecera: es el
  // que el verificador lee para comprobar que la fase sale de `/health`.
  const cabecera = (
    <header className="cabecera">
      <div>
        <h1 className="titulo">AI Software Engineering System</h1>
        <p className="subtitulo" style={{ margin: "0.15rem 0 0" }}>
          Proyecto 4 · Equipo 4
        </p>
      </div>
      <div className="fila">
        {saludError ? (
          <Chip tono="error">servidor inaccesible</Chip>
        ) : salud ? (
          <Chip tono="ok">
            servidor ok · fase {salud.fase} · {salud.ejecuciones} ejecución(es)
          </Chip>
        ) : (
          <Chip pulsa>comprobando…</Chip>
        )}
        {sesion === "autenticado" ? <Chip tono="ok">sesión autenticada</Chip> : null}
        {sesion === "sin-credencial" ||
        sesion === "clave-invalida" ||
        sesion === "sesion-caida" ? (
          <Chip tono="aviso">sin credencial</Chip>
        ) : null}
      </div>
    </header>
  );

  // **Mientras no se sabe, no se ofrece nada.** Hasta que la primera lectura
  // protegida responde no se sabe si el servidor exige credencial, y pintar la
  // aplicacion entera en ese hueco ofrece botones que van a fallar con 401: quien
  // los pulse antes de tiempo recibe un error que no entiende. Se probo de
  // verdad: la verificacion del navegador pulsaba "Ejecutar" en ese hueco.
  if (sesion === "comprobando") {
    return (
      <main className="app">
        {cabecera}
        <Panel>
          <p className="tenue">Comprobando el estado del servidor…</p>
        </Panel>
      </main>
    );
  }

  // La pantalla de acceso **sustituye** al contenido: sin credencial no hay nada
  // que enseñar que no sea un panel vacio. La cabecera se queda -el chip de salud
  // demuestra que el servidor responde-.
  if (
    sesion === "sin-credencial" ||
    sesion === "clave-invalida" ||
    sesion === "sesion-caida" ||
    sesion === "validando" ||
    cambiandoClave
  ) {
    return (
      <main className="app">
        {cabecera}
        <PantallaAcceso
          validando={sesion === "validando"}
          mensaje={mensajeAcceso}
          onEntrar={(clave) => void entrarConClave(clave)}
          onCancelar={
            cambiandoClave && sesion === "autenticado"
              ? () => setCambiandoClave(false)
              : undefined
          }
        />
      </main>
    );
  }

  return (
    <main className="app">
      {cabecera}

      {/* -------------------------------------------------------- Acceso */}
      {sesion === "autenticado" ? (
        <>
          <div className="seccion-titulo">Acceso</div>
          <Panel nota="La credencial vive en memoria, solo en esta pestaña: no se guarda en el navegador y al recargar la página se pide otra vez.">
            <Fila>
              <span className="mono" title="Credencial enmascarada">
                {enmascarar(claveApi)}
              </span>
              <button id="btn-cambiar-clave" onClick={() => setCambiandoClave(true)}>
                Cambiar
              </button>
              <button id="btn-cerrar-sesion" onClick={cerrarSesion}>
                Cerrar sesión
              </button>
            </Fila>
            <p className="tenue">
              Autenticación: activada
              {rol ? ` · Rol: ${rol}` : ""}
              {` · SSE: ${conectado ? "conectado" : conexion === "error" ? "sin conexión" : "inactivo"}`}
            </p>
          </Panel>
        </>
      ) : null}

      {/* -------------------------------------------------------- Entrada */}
      {puedeOperar ? (
        <>
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
              <button
                id="btn-crear"
                className="primario"
                disabled={lanzando}
                onClick={() => void lanzar()}
              >
                {lanzando ? "Lanzando…" : "Ejecutar"}
              </button>
              <span className="tenue">La ejecución devuelve el identificador al instante</span>
            </Fila>

            {puedeAdministrar ? (
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
            ) : null}

            {errorAccion ? (
              <p className="aviso" role="alert">
                {errorAccion}
              </p>
            ) : null}
          </Panel>
        </>
      ) : (
        <>
          <div className="seccion-titulo">Nueva ejecución</div>
          <Panel>
            <p className="tenue">
              Tu credencial es de solo lectura: no puede lanzar ejecuciones ni
              responder a las puertas humanas. Lo que sí puedes hacer es consultar
              las ejecuciones y su progreso.
            </p>
          </Panel>
        </>
      )}

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
          {puedeOperar && puerta === "requisitos" && estado ? (
            <PuertaRequisitos estado={estado} alDecidir={() => void refrescar(runId)} />
          ) : null}
          {puedeOperar && puerta === "aprobacion" && estado ? (
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

/**
 * Raiz de la aplicacion: el armazon.
 *
 * Sostiene tres cosas y delega el resto:
 *
 *   1. **El acceso.** La credencial vive en memoria; el modo del servidor se
 *      deduce de la primera lectura protegida (401 = la exige, 200 = esta
 *      abierta). Mientras no se sabe, no se ofrece nada.
 *   2. **Los datos.** `/health`, los proyectos, las ejecuciones y el estado de la
 *      ejecucion seleccionada. Todo se relee del servidor: el cliente no
 *      reconstruye el estado de una ejecucion, lo pide.
 *   3. **La navegacion.** Siete vistas; el estado de la vista es de React, no hay
 *      rutas ni historial que fingir.
 *
 * El estado de la ejecucion se relee cuando llega un evento y, mientras la
 * ejecucion no es terminal, cada 900 ms: una ejecucion puede cambiar de estado sin
 * emitir evento -al confirmar requisitos pasa de la puerta a `running` sin escribir
 * nada-, y un cliente que solo reaccionara a eventos se quedaria mostrando la puerta
 * ya respondida.
 *
 * La etiqueta de fase se lee de `/health`, nunca de un literal (AUD-13).
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
  type ExecutionMode,
  type Health,
  type Project,
  type RunState,
  type RunSummary,
  type Transcript,
} from "./lib/contracts";
import { hitosDe, useEventosRun } from "./hooks/useEventosRun";
import { Navegacion, type ItemNav, type VistaId } from "./components/Navegacion";
import { PantallaAcceso } from "./components/PantallaAcceso";
import type { AccionesCompositor, EstadoCompositor } from "./components/Compositor";
import { Chip, Panel } from "./components/ui";
import { VistaDetalle } from "./views/VistaDetalle";
import { VistaEjecuciones } from "./views/VistaEjecuciones";
import { VistaFlujo } from "./views/VistaFlujo";
import { VistaActividad } from "./views/VistaActividad";
import { VistaGeneral } from "./views/VistaGeneral";
import { EstadoProveedor } from "./components/EstadoProveedor";
import { GuiaEjecucion } from "./components/GuiaEjecucion";
import { VistaProyectos } from "./views/VistaProyectos";
import { VistaSeguridad } from "./views/VistaSeguridad";
import { VistaSesion } from "./views/VistaSesion";
import { Icono } from "./components/Icono";

/** Que respondio el servidor a las peticiones protegidas. */
type ResultadoCarga = "ok" | "401" | "fallo";

export function App({ profile }: { profile?: {
  name: string; onLogout: () => void; onVault: () => void; configurationRevision?: number;
} } = {}) {
  // --------------------------------------------------------------- datos
  const [salud, setSalud] = useState<Health | null>(null);
  const [saludError, setSaludError] = useState(false);
  const [proyectos, setProyectos] = useState<Project[]>([]);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [cargando, setCargando] = useState(true);

  const [runId, setRunId] = useState<string | null>(null);
  const [estado, setEstado] = useState<RunState | null>(null);
  const runSeleccionado = useRef<string | null>(null);

  // -------------------------------------------------------------- acceso
  const claveApi = useClaveApi();
  const [sesion, setSesion] = useState<EstadoSesion>("comprobando");
  const [mensajeAcceso, setMensajeAcceso] = useState<string | null>(null);
  const [cambiandoClave, setCambiandoClave] = useState(false);
  const [rol, setRol] = useState<string | null>(null);

  // ----------------------------------------------------------- compositor
  const [instruccion, setInstruccion] = useState(
    "",
  );
  /**
   * Procedencia de la instruccion cuando viene de un dictado.
   *
   * Se guarda aparte del texto y **se pierde en cuanto el texto se edita a
   * mano**: una instruccion reescrita por la persona ya no es la que reconocio el
   * modelo, y registrarla como dictada con la confianza de otro texto seria
   * falsear el origen. La ejecucion creada con esto puesto se registra como de
   * voz (`RF-03`); sin el, como de texto.
   */
  const [transcripcion, setTranscripcion] = useState<Transcript | null>(null);
  const [projectId, setProjectId] = useState<string>("");
  const [nombreProyecto, setNombreProyecto] = useState("");
  const [rutaProyecto, setRutaProyecto] = useState("");
  const [lanzando, setLanzando] = useState(false);
  const [registrando, setRegistrando] = useState(false);
  const [errorAccion, setErrorAccion] = useState<string | null>(null);
  const [allowedPaths, setAllowedPaths] = useState<string[]>([]);
  const [protectedPaths, setProtectedPaths] = useState<string[]>([]);
  const [mode, setMode] = useState<ExecutionMode>("FULL_PROPOSAL");
  const [destino, setDestino] = useState<"local" | "github">("local");
  const [menuAbierto, setMenuAbierto] = useState(false);
  const [tema, setTema] = useState<"sistema" | "claro" | "oscuro">("oscuro");
  useEffect(() => {
    document.documentElement.dataset.tema = tema;
  }, [tema]);
  useEffect(() => {
    if (!menuAbierto) return;
    const escapar = (e: KeyboardEvent) => {
      if (e.key === "Escape") { setMenuAbierto(false); document.getElementById("abrir-menu")?.focus(); }
    };
    window.addEventListener("keydown", escapar);
    return () => window.removeEventListener("keydown", escapar);
  }, [menuAbierto]);

  // ---------------------------------------------------------- navegacion
  const [vista, setVista] = useState<VistaId>("general");
  const [sidebarCompacta, setSidebarCompacta] = useState(false);
  const contenido = useRef<HTMLDivElement | null>(null);

  const { eventos, conexion, reanudar } = useEventosRun(runId);

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
      vista,
    };
  }, [runId, estado, eventos, conexion, sesion, vista]);

  /**
   * Anota un fallo de acceso en el sitio que le corresponde y devuelve el mensaje
   * que hay que ensenar.
   *
   * **401: la sesion se cae.** La credencial que valia dejo de valer -revocada,
   * cambiada en el servidor- o nunca valio: se olvida y se vuelve a pedir.
   *
   * **403: falta permiso.** La sesion sigue siendo valida; lo que no alcanza es el
   * rol. Se aprende cual es -el backend lo dice al rechazar- para dejar de ofrecer
   * acciones que van a ser rechazadas. **Un 403 no cierra la sesion.**
   */
  const anotarFallo = useCallback((causa: unknown): string => {
    const habiaCredencial = hayClave();
    if (causa instanceof ErrorApi && causa.status === 401) {
      borrarClave();
      setRol(null);
      setRunId(null);
      runSeleccionado.current = null;
      setEstado(null);
      setSesion("sesion-caida");
      setMensajeAcceso("Tu credencial dejó de ser válida. Introdúcela de nuevo.");
    } else if (causa instanceof ErrorApi && causa.status === 403) {
      setErrorAccion(mensajeVisible(causa, habiaCredencial));
      const detectado = rolDelRechazo(causa);
      if (detectado) setRol(detectado);
    } else if (causa instanceof ErrorApi && causa.status === 0) {
      setSaludError(true);
    }
    return mensajeVisible(causa, habiaCredencial);
  }, []);

  const refrescar = useCallback(
    async (id: string) => {
      const errores: string[] = [];
      try {
        const leido = await api.obtenerRun(id);
        if (runSeleccionado.current === id) setEstado(leido);
      } catch (causa) {
        errores.push(anotarFallo(causa));
      }
      try {
        setRuns(await api.listarRuns());
      } catch (causa) {
        errores.push(anotarFallo(causa));
      }
      return errores;
    },
    [anotarFallo],
  );

  const nEventos = eventos.length;
  const ultimoRef = useRef(-1);

  useEffect(() => {
    if (!runId || nEventos === ultimoRef.current) return;
    ultimoRef.current = nEventos;
    void refrescar(runId);
  }, [runId, nEventos, refrescar]);

  useEffect(() => {
    if (runId) void refrescar(runId);
  }, [runId, refrescar]);

  // Sondeo mientras la ejecucion no es terminal: ver la cabecera del fichero.
  useEffect(() => {
    if (!runId || !estado || ESTADOS_TERMINALES.has(estado.status)) return;
    const temporizador = window.setInterval(() => void refrescar(runId), 900);
    return () => window.clearInterval(temporizador);
  }, [runId, estado, refrescar]);

  /**
   * Lee lo que el servidor tiene. `/health` esta abierto en los dos modos, asi que
   * **no** distingue si hace falta credencial: eso lo dicen las peticiones
   * protegidas, y por eso su resultado es el que devuelve esta funcion.
   */
  const cargarInicial = useCallback(async (): Promise<ResultadoCarga> => {
    setCargando(true);
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
    } finally {
      setCargando(false);
    }
  }, []);

  // **El modo del servidor se deduce, no se adivina.**
  useEffect(() => {
    void (async () => {
      const resultado = await cargarInicial();
      if (resultado === "401") {
        const habia = hayClave();
        setSesion(habia ? "clave-invalida" : "sin-credencial");
        setMensajeAcceso(habia ? "Clave API no válida." : null);
      } else if (resultado === "ok") {
        setSesion(hayClave() ? "autenticado" : "sin-autenticacion");
      } else {
        setSesion("sin-servidor");
      }
    })();
  }, [cargarInicial, profile?.configurationRevision]);

  // El foco se mueve al contenido al cambiar de vista: sin eso, quien navega con
  // el teclado se queda en el boton de la barra y tiene que tabular por toda la
  // pagina anterior para llegar a la nueva.
  useEffect(() => {
    contenido.current?.focus({ preventScroll: true });
    window.scrollTo(0, 0);
  }, [vista, sesion]);

  const hitos = useMemo(() => hitosDe(eventos), [eventos]);

  /**
   * Comprueba una credencial introducida contra el servidor.
   *
   * Se guarda **antes** de comprobarla, porque es la unica forma de que la
   * peticion de comprobacion la lleve; si el servidor la rechaza se olvida acto
   * seguido. No se afirma que una credencial sea invalida por un fallo de red: eso
   * es un fallo, no un veredicto.
   */
  async function entrarConClave(clave: string) {
    setErrorAccion(null);
    setMensajeAcceso(null);
    setSesion("validando");
    guardarClave(clave);
    const resultado = await cargarInicial();
    if (resultado === "401") {
      borrarClave();
      setSesion("clave-invalida");
      setMensajeAcceso("Clave API no válida.");
      return;
    }
    if (resultado === "fallo") {
      borrarClave();
      setSesion("sin-credencial");
      setMensajeAcceso("No se pudo comprobar la credencial. Inténtalo de nuevo.");
      return;
    }
    setRol(null);
    setCambiandoClave(false);
    setSesion("autenticado");
  }

  /** Olvida la credencial de esta pestana. No hay peticion: no hay nada que revocar. */
  function cerrarSesion() {
    borrarClave();
    setRol(null);
    setCambiandoClave(false);
    setMensajeAcceso(null);
    setProyectos([]);
    setRuns([]);
    setRunId(null);
    runSeleccionado.current = null;
    setEstado(null);
    setTranscripcion(null);
    setVista("general");
    setSesion("sin-credencial");
  }

  async function eliminarProyecto(id: string) {
    if (!window.confirm("¿Quitar este proyecto de la lista? Se conservarán los archivos, el repositorio y el historial de ejecuciones.")) return false;
    try {
      await api.eliminarProyecto(id);
      setProyectos((previos) => previos.filter((p) => p.project_id !== id));
      if (projectId === id) {
        setProjectId("");
      }
      return true;
    } catch (causa) {
      setErrorAccion(anotarFallo(causa));
      return false;
    }
  }

  async function registrarProyecto(createIfMissing = false) {
    if (registrando) return;
    setRegistrando(true);
    setErrorAccion(null);
    try {
      const p = await api.crearProyecto(nombreProyecto, rutaProyecto, createIfMissing);
      setProyectos((previos) => [p, ...previos]);
      setProjectId(p.project_id);
      setNombreProyecto("");
      setRutaProyecto("");
    } catch (causa) {
      setErrorAccion(anotarFallo(causa));
    } finally {
      setRegistrando(false);
    }
  }

  async function lanzar() {
    const texto = instruccion.trim() || "Analiza el proyecto e identifica los errores principales.";
    if (!texto) return;
    setLanzando(true);
    setErrorAccion(null);
    setEstado(null);
    try {
      const creado = await api.crearRun(
        texto,
        projectId || undefined,
        transcripcion ?? undefined,
        { allowed_paths: allowedPaths, protected_paths: protectedPaths, mode, delivery_mode: destino },
      );
      runSeleccionado.current = creado.run_id;
      setRunId(creado.run_id);
      setEstado(creado);
      // La ejecucion ya lleva el origen: la procedencia no se arrastra a la
      // siguiente, que se teclea a mano salvo que se vuelva a dictar.
      setTranscripcion(null);
      setVista("general");
    } catch (causa) {
      setErrorAccion(anotarFallo(causa));
    } finally {
      setLanzando(false);
    }
  }

  function seleccionarRun(id: string) {
    runSeleccionado.current = id;
    setEstado(null);
    if (id === runId) void refrescar(id);
    setRunId(id);
    setVista("detalle");
  }

  const compositor: EstadoCompositor = {
    destino,
    instruccion,
    origenVoz: transcripcion,
    projectId,
    nombreProyecto,
    rutaProyecto,
    lanzando,
    registrando,
    errorAccion,
    allowedPaths,
    protectedPaths,
    mode,
  };
  const accionesCompositor: AccionesCompositor = {
    // Editar a mano **invalida la procedencia**: ver `transcripcion`.
    alCambiarInstruccion: (v) => {
      setInstruccion(v);
      setTranscripcion(null);
    },
    alCambiarProyecto: setProjectId,
    alCambiarNombre: setNombreProyecto,
    alCambiarRuta: setRutaProyecto,
    alLanzar: () => void lanzar(),
    alRegistrarProyecto: (crear = false) => void registrarProyecto(crear),
    alCambiarPermitidas: setAllowedPaths,
    alCambiarProtegidas: setProtectedPaths,
    alCambiarModo: setMode,
    alCambiarDestino: setDestino,
    alFallo: anotarFallo,
    alUsarTranscripcion: (texto, meta) => {
      setInstruccion(texto);
      setTranscripcion(meta);
    },
  };

  // El rol, cuando se conoce, ordena la jerarquia que el backend aplica de verdad:
  // `reader` < `operator` < `admin`. Se usa **solo** para no ofrecer lo que va a ser
  // rechazado; la autorizacion la sigue haciendo el servidor.
  const puedeOperar = rol === null || rol !== "reader";
  const puedeAdministrar = rol === null || rol === "admin";

  const esperando = runs.some((r) => r.awaiting_approval || r.status.startsWith("awaiting"));
  const items: ItemNav[] = [
    { id: "general", etiqueta: "Vista general" },
    { id: "proyectos", etiqueta: "Proyectos" },
    { id: "ejecuciones", etiqueta: "Ejecuciones", aviso: esperando },
    { id: "detalle", etiqueta: "Detalle" },
    { id: "flujo", etiqueta: "Flujo" },
    { id: "actividad", etiqueta: "Actividad" },
    { id: "seguridad", etiqueta: "Seguridad" },
    { id: "sesion", etiqueta: "Sesión" },
  ];

  // El chip de salud tiene que seguir siendo el **primero** de la cabecera: es el
  // que el verificador lee para comprobar que la fase sale de `/health`.
  const cabecera = (
    <header className="cabecera">
      <button id="abrir-menu" className="boton-menu" aria-label="Abrir navegación" aria-expanded={menuAbierto}
        aria-controls="sidebar" onClick={() => setMenuAbierto(v => !v)}><Icono nombre="menu" /></button>
      <div>
        <button className="contraer-sidebar" aria-label={sidebarCompacta ? "Expandir barra lateral" : "Contraer barra lateral"} aria-expanded={!sidebarCompacta} aria-controls="sidebar" onClick={() => setSidebarCompacta(v => !v)}><Icono nombre="capas" /></button>
        <div className="titulo">AI Software Engineering System</div>
        <p className="subtitulo">Espacio de trabajo · Ingeniería con evidencia</p>
      </div>
      <div className="fila">
        {saludError ? (
          <Chip tono="error">servidor inaccesible</Chip>
        ) : salud ? (
          <Chip tono="ok">
            servidor ok · fase {salud.fase}
          </Chip>
        ) : (
          <Chip pulsa>comprobando…</Chip>
        )}
        <EstadoProveedor configuracion={salud?.provider_configuration} />
        {profile || sesion === "autenticado" ? <Chip tono="ok">sesión autenticada</Chip> : null}
        {/* La credencial enmascarada se enseña **en la cabecera**, discreta y en
            todas las vistas: confirma cual esta en uso sin revelarla. Estuvo solo
            en la vista de sesion y eso rompio una comprobacion -la de que la
            credencial no acaba en el DOM-, porque el verificador mira la vista
            general y no la encontraba. */}
        {sesion === "autenticado" && claveApi ? (
          <span
            className="chip mono"
            title="Credencial enmascarada: solo se muestran los dos últimos caracteres"
          >
            {enmascarar(claveApi)}
          </span>
        ) : null}
        {!profile && sesion === "sin-autenticacion" ? <Chip>sin autenticación</Chip> : null}
        {rol ? <Chip>{rol}</Chip> : null}
        <label className="solo-lector" htmlFor="tema">Tema</label>
        <select id="tema" className="selector-tema" value={tema}
          onChange={e => setTema(e.target.value as typeof tema)}>
          <option value="oscuro">Oscuro</option><option value="claro">Claro</option><option value="sistema">Tema del sistema</option>
        </select>
        <button type="button" className="topbar-icono-btn" aria-label="Actividad y notificaciones" title="Ver actividad" onClick={() => setVista(esperando ? "ejecuciones" : "actividad")}><Icono nombre="campana" /><span className="topbar-punto-alerta" aria-hidden="true" /></button>
        <button type="button" className="topbar-avatar-btn" aria-label="Perfil y sesión" title={profile?.name ?? "Sesión"} onClick={() => setVista("sesion")} />
        {sesion === "autenticado" ? <button className="sutil salir-topbar" onClick={cerrarSesion}>Cerrar sesión</button> : null}
        {sesion === "sin-credencial" ||
        sesion === "clave-invalida" ||
        sesion === "sesion-caida" ? (
          <Chip tono="aviso">sin credencial</Chip>
        ) : null}
      </div>
    </header>
  );

  // Mientras no se sabe si hace falta credencial no se ofrece nada: pintar la
  // aplicacion en ese hueco pone el primer clic sobre un boton que responde 401.
  if (sesion === "sin-servidor") {
    return <main className="app">{cabecera}<Panel titulo="Servidor no disponible">
      <p role="alert">No se pudo comprobar el acceso al servidor. Revisa la conexión antes de continuar.</p>
      <button className="primario" onClick={() => window.location.reload()}>Volver a comprobar</button>
    </Panel></main>;
  }
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

  // La pantalla de acceso sustituye al contenido: sin credencial no hay nada que
  // ensenar que no sea un panel vacio. La cabecera se queda -el chip de salud
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
    <div className={`app-shell${sidebarCompacta ? " sidebar-compacta" : ""}`}>
      <a className="saltar" href="#contenido">Saltar al contenido</a>
      <aside id="sidebar" className={`sidebar ${menuAbierto ? "abierto" : ""}`}>
        <button className="cerrar-menu sutil" aria-label="Cerrar navegación" onClick={() => {
          setMenuAbierto(false); document.getElementById("abrir-menu")?.focus();
        }}><Icono nombre="cerrar" /></button>
        <Navegacion vista={vista} items={items} alCambiar={v => { setVista(v); setMenuAbierto(false); window.requestAnimationFrame(() => { contenido.current?.focus({ preventScroll: true }); window.scrollTo(0, 0); }); }}
          proyectos={proyectos} proyectoActual={projectId}
          runs={runs} runActual={runId} alRun={id => { seleccionarRun(id); setMenuAbierto(false); }}
          alProyecto={id => { setProjectId(id); setVista("general"); setMenuAbierto(false); }}
          alCrearProyecto={() => { setVista("proyectos"); setMenuAbierto(false); }} perfilNombre={profile?.name} />
      </aside>
      {cabecera}
      <main id="contenido" className="app contenido">

      <div className="vista" ref={contenido} tabIndex={-1} aria-label={`Vista: ${vista}`}>
        {estado?.status === "completed" && estado.promotion_receipt?.status === "promoted" ?
          <GuiaEjecucion key={estado.run_id} estado={estado} puedeOperar={puedeOperar}
            projectId={proyectos.find(p => p.repo_path === estado.options.repo_path)?.project_id} /> : null}
        {!puedeOperar && errorAccion ? <p className="banner aviso" role="alert">{errorAccion}</p> : null}
        {runId && !estado ? <p role="status" className="carga-run">Cargando la ejecución seleccionada…</p> : null}
        {vista === "general" ? (
          <VistaGeneral
            salud={salud}
            saludError={saludError}
            sesion={profile ? "autenticado" : sesion}
            rol={profile ? "admin" : rol}
            conexion={conexion}
            proyectos={proyectos}
            runs={runs}
            estado={estado}
            hitos={hitos}
            cargando={cargando}
            eventos={eventos}
            compositor={compositor}
            accionesCompositor={accionesCompositor}
            alSeleccionarRun={seleccionarRun}
            alRefrescar={(id) => { reanudar(); void refrescar(id); }}
            alFallo={anotarFallo}
            alIrA={setVista}
            puedeAdministrar={puedeAdministrar}
            puedeOperar={puedeOperar}
          />
        ) : null}

        {vista === "proyectos" ? (
          <VistaProyectos
            proyectos={proyectos}
            cargando={cargando}
            nombre={nombreProyecto}
            ruta={rutaProyecto}
            alCambiarNombre={setNombreProyecto}
            alCambiarRuta={setRutaProyecto}
            alRegistrar={(crear = false) => void registrarProyecto(crear)}
            errorRegistro={errorAccion}
            registrando={registrando}
            alEjecutarContra={(id) => {
              setProjectId(id);
              setVista("general");
            }}
            alEliminar={eliminarProyecto}
            alFallo={anotarFallo}
            puedeAdministrar={puedeAdministrar}
          />
        ) : null}

        {vista === "ejecuciones" ? (
          <VistaEjecuciones
            runs={runs}
            cargando={cargando}
            conexion={conexion}
            proyectos={proyectos}
            salud={salud}
            compositor={compositor}
            accionesCompositor={accionesCompositor}
            alSeleccionarRun={seleccionarRun}
            puedeAdministrar={puedeAdministrar}
            puedeOperar={puedeOperar}
          />
        ) : null}

        {vista === "detalle" ? (
          <VistaDetalle
            estado={estado}
            hitos={hitos}
            eventos={eventos}
            conexion={conexion}
            proyectos={proyectos}
            alRefrescar={refrescar}
            alReanudar={(id) => { reanudar(); void refrescar(id); }}
            alFallo={anotarFallo}
          />
        ) : null}

        {vista === "flujo" ? <VistaFlujo estado={estado} eventos={eventos} alPuerta={() => setVista("detalle")} /> : null}
        {vista === "actividad" ? <VistaActividad estado={estado} eventos={eventos} conexion={conexion} /> : null}

        {vista === "seguridad" ? (
          <VistaSeguridad estado={estado} sesion={profile ? "autenticado" : sesion} rol={profile ? "admin" : rol} />
        ) : null}

        {vista === "sesion" ? (
          <VistaSesion
            profileName={profile?.name}
            sesion={profile ? "autenticado" : sesion}
            rol={profile ? "admin" : rol}
            credencial={enmascarar(claveApi)}
            conexion={conexion}
            salud={salud}
            saludError={saludError}
            alCambiarCredencial={profile?.onVault ?? (() => setCambiandoClave(true))}
            alCerrarSesion={profile?.onLogout ?? cerrarSesion}
          />
        ) : null}
      </div>
      </main>
    </div>
  );
}

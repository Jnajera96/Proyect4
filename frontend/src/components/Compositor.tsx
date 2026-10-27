/**
 * Compositor de una ejecucion: la instruccion, el proyecto y el disparo.
 *
 * Es el unico sitio donde viven `#instruccion`, `#btn-crear` y los campos de alta
 * de proyecto. Lo usan la vista general y la de ejecuciones, y tenerlo en un solo
 * componente evita que las dos copias se separen -y que los identificadores que
 * maneja la verificacion del navegador se dupliquen o desaparezcan de una-.
 *
 * El estado vive en el shell (`App`) y no aqui: cambiar de seccion y volver no
 * puede borrar lo que la persona estaba escribiendo.
 */
import type { Health, Project, Transcript } from "../lib/contracts";
import { duracion } from "../lib/formato";
import { PanelVoz } from "./PanelVoz";
import { Fila, Panel } from "./ui";
import { EditorRutas } from "./EditorRutas";
import { Icono } from "./Icono";
import { rutaCorta } from "../lib/formato";

export interface EstadoCompositor {
  instruccion: string;
  /**
   * Origen dictado de la instruccion, si viene de `POST /transcriptions`.
   *
   * Se ensena bajo el campo porque cambia **lo que se va a registrar**: la
   * ejecucion se creara como de voz con los metadatos del reconocimiento
   * (`RF-03`). Quien escribe a mano no lo ve -y si edita el texto dictado
   * desaparece, porque entonces la instruccion ya no es la que reconocio el
   * modelo-.
   */
  origenVoz: Transcript | null;
  projectId: string;
  nombreProyecto: string;
  rutaProyecto: string;
  lanzando: boolean;
  registrando: boolean;
  errorAccion: string | null;
  allowedPaths: string[];
  protectedPaths: string[];
}

export interface AccionesCompositor {
  alCambiarInstruccion: (v: string) => void;
  alCambiarProyecto: (v: string) => void;
  alCambiarNombre: (v: string) => void;
  alCambiarRuta: (v: string) => void;
  alLanzar: () => void;
  alRegistrarProyecto: () => void;
  alCambiarPermitidas: (rutas: string[]) => void;
  alCambiarProtegidas: (rutas: string[]) => void;
  alFallo: (causa: unknown) => string;
  /** Copia el texto confirmado por voz, **con su procedencia**, al campo. */
  alUsarTranscripcion: (texto: string, meta: Transcript) => void;
}

export function Compositor({
  estado,
  acciones,
  proyectos,
  salud,
  puedeAdministrar,
}: {
  estado: EstadoCompositor;
  acciones: AccionesCompositor;
  proyectos: Project[];
  salud: Health | null;
  puedeAdministrar: boolean;
}) {
  function abrirDictado(archivo = false) {
    const voz = document.getElementById("dictado");
    if (!(voz instanceof HTMLDetailsElement)) return;
    voz.open = true;
    const campo = voz.querySelector<HTMLInputElement>("#audio-fichero");
    if (archivo && campo) campo.click();
    else voz.querySelector("summary")?.focus();
  }

  return (
    <>
      <Panel
        titulo="Tu próxima ejecución"
      >
        <label className="solo-lector" htmlFor="instruccion">Instrucción</label>
        <div className="entrada-principal">
        <textarea
          id="instruccion"
          value={estado.instruccion}
          onChange={(e) => acciones.alCambiarInstruccion(e.target.value)}
          placeholder="Describe qué quieres construir o mejorar…"
          autoFocus={typeof window !== "undefined" && window.matchMedia("(pointer: fine)").matches && !estado.instruccion}
        />
        <div className="comando-herramientas">
        <button className="boton-microfono" aria-label="Abrir dictado por voz"
          title="Abrir dictado por voz" onClick={() => abrirDictado()}><Icono nombre="microfono" /></button>
        <button className="boton-audio" aria-label="Elegir un fichero de audio"
          title="Elegir un fichero de audio en el estudio de voz" onClick={() => abrirDictado(true)}>
          <Icono nombre="detalle" /><span>Audio</span></button>
        <span className="comando-ayuda">Texto o voz. Tú decides cuándo ejecutar.</span>
        <button id="btn-crear" className="primario enviar" disabled={estado.lanzando || !estado.instruccion.trim()}
          onClick={acciones.alLanzar} aria-label={estado.lanzando ? "Lanzando ejecución" : "Ejecutar"}>
          <Icono nombre="flecha" /><span>{estado.lanzando ? "Lanzando…" : "Ejecutar"}</span>
        </button></div></div>

        {estado.origenVoz ? (
          <p className="tenue fila-sep">
            Instrucción dictada: <span className="mono">{estado.origenVoz.provider}</span>{" "}
            · confianza {(estado.origenVoz.confidence * 100).toFixed(0)}% ·{" "}
            {duracion(estado.origenVoz.duration_s)}. La ejecución se registrará como
            de voz con estos datos. Si editas el texto, el origen se pierde.
          </p>
        ) : null}

        <div className="compositor-extra"><div className="rejilla">
          <div>
            <label htmlFor="proyecto">Proyecto</label>
            <select
              id="proyecto"
              value={estado.projectId}
              onChange={(e) => acciones.alCambiarProyecto(e.target.value)}
            >
              <option value="">(sin proyecto · ruta por defecto)</option>
              {proyectos.map((p) => (
                <option key={p.project_id} value={p.project_id}>
                  {p.name} — {rutaCorta(p.repo_path)}
                </option>
              ))}
            </select>
          </div>
        </div>

        <details className="plegable" id="alcance-avanzado"><summary>Opciones avanzadas · alcance</summary>
          <p className="tenue">Sin rutas permitidas se autoriza todo el repositorio. Las rutas protegidas restringen la escritura.</p>
          <div className="rejilla rejilla-doble">
            <EditorRutas id="allowed-paths" titulo="Rutas permitidas" rutas={estado.allowedPaths} alCambiar={acciones.alCambiarPermitidas} />
            <EditorRutas id="protected-paths" titulo="Rutas protegidas" rutas={estado.protectedPaths} alCambiar={acciones.alCambiarProtegidas} />
          </div>
        </details>
        </div>

        {puedeAdministrar ? (
          <details className="plegable">
            <summary>Registrar un proyecto</summary>
            <div className="stack" style={{ marginTop: "0.75rem" }}>
              <div>
                <label htmlFor="p-nombre">Nombre</label>
                <input
                  id="p-nombre"
                  type="text"
                  value={estado.nombreProyecto}
                  onChange={(e) => acciones.alCambiarNombre(e.target.value)}
                  placeholder="mi-repositorio"
                />
              </div>
              <div>
                <label htmlFor="p-ruta">Ruta del repositorio</label>
                <input
                  id="p-ruta"
                  type="text"
                  value={estado.rutaProyecto}
                  onChange={(e) => acciones.alCambiarRuta(e.target.value)}
                  placeholder="C:\\ruta\\al\\repositorio"
                />
              </div>
              <Fila>
                <button
                  disabled={estado.registrando || !estado.nombreProyecto.trim() || !estado.rutaProyecto.trim()}
                  onClick={acciones.alRegistrarProyecto}
                >
                  {estado.registrando ? "Registrando…" : "Registrar"}
                </button>
                <span className="tenue">La ruta se valida al registrar, no al ejecutar</span>
              </Fila>
            </div>
          </details>
        ) : null}

        {estado.errorAccion ? (
          <p className="aviso" role="alert">
            {estado.errorAccion}
          </p>
        ) : null}
      </Panel>

      <details className="plegable" id="dictado">
        <summary>Dictar la instrucción</summary>
        <div style={{ marginTop: "0.75rem" }}>
          <PanelVoz
            disponible={salud?.stt === true}
            alFallo={acciones.alFallo}
            alConfirmar={(texto, meta) => acciones.alUsarTranscripcion(texto, meta)}
          />
        </div>
      </details>
    </>
  );
}

/**
 * Dictado de la instruccion por voz (`POST /transcriptions`).
 *
 * **El flujo es el que manda el backend, y no tiene atajos:** grabar -> detener ->
 * subir -> transcribir -> texto editable -> confirmar -> usar como instruccion.
 * La transcripcion **nunca arranca una ejecucion**: `POST /transcriptions` no crea
 * ninguna (`RF-02`), y el texto vuelve a la persona para que lo lea, lo corrija y
 * decida. Un dictado que se ejecutara solo convertiria un reconocimiento
 * imperfecto en cambios en un repositorio.
 *
 * **Si el servidor no puede transcribir, se dice.** `/health` publica si el
 * adaptador esta disponible; cuando no lo esta -falta la dependencia
 * `faster-whisper`, que es un extra opcional- la interfaz no finge un microfono
 * que va a fallar al subir: explica que falta y no ofrece el control.
 *
 * La grabacion usa `MediaRecorder`, que es del navegador y no del backend: si el
 * navegador no lo trae, queda la segunda via -elegir un fichero de audio-.
 */
import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { Transcript } from "../lib/contracts";
import { duracion } from "../lib/formato";
import { Chip, Fila, Panel } from "./ui";

type Fase = "inicial" | "grabando" | "listo" | "transcribiendo" | "revisando" | "error";

const VOCABULARIO_SWE =
  "software, Python, pytest, FastAPI, endpoint, git, commit, frontend, backend, refactorizar, función, clase, variable, interfaz, base de datos, SQLite, React, TypeScript, test, bug, migración, Docker";

export function PanelVoz({
  disponible,
  alConfirmar,
  alFallo,
}: {
  /** Lo que declara `/health`: si el adaptador de voz del servidor esta listo. */
  disponible: boolean;
  /** Entrega el texto **confirmado** para que se use como instruccion. */
  alConfirmar: (texto: string, meta: Transcript) => void;
  alFallo: (causa: unknown) => string;
}) {
  const [fase, setFase] = useState<Fase>("inicial");
  const [audio, setAudio] = useState<Blob | null>(null);
  const [nombreAudio, setNombreAudio] = useState("dictado.webm");
  const [transcripcion, setTranscripcion] = useState<Transcript | null>(null);
  const [texto, setTexto] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [segundos, setSegundos] = useState(0);
  const grabadora = useRef<MediaRecorder | null>(null);
  const trozos = useRef<Blob[]>([]);
  const reloj = useRef<number | null>(null);

  const hayMicrofono = typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia;
  const hayGrabadora = typeof window !== "undefined" && typeof window.MediaRecorder !== "undefined";

  useEffect(() => {
    return () => {
      if (reloj.current !== null) window.clearInterval(reloj.current);
      grabadora.current?.stream.getTracks().forEach((t) => t.stop());
    };
  }, []);

  if (!disponible) {
    return (
      <Panel titulo="Dictar la instrucción">
        <p className="tenue">
          El servidor no informa un adaptador de transcripción disponible.
          Puedes escribir la instrucción. La disponibilidad del adaptador no confirma
          que un modelo esté cargado ni que haya una GPU preparada.
        </p>
      </Panel>
    );
  }

  async function empezar() {
    setError(null);
    try {
      const flujo = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(flujo);
      trozos.current = [];
      rec.ondataavailable = (evento) => {
        if (evento.data.size > 0) trozos.current.push(evento.data);
      };
      rec.onstop = () => {
        flujo.getTracks().forEach((t) => t.stop());
        setAudio(new Blob(trozos.current, { type: rec.mimeType || "audio/webm" }));
        setFase("listo");
      };
      grabadora.current = rec;
      setSegundos(0);
      reloj.current = window.setInterval(() => setSegundos((s) => s + 1), 1000);
      rec.start();
      setFase("grabando");
    } catch (causa) {
      setError(
        `No se pudo acceder al micrófono: ${causa instanceof Error ? causa.message : String(causa)}. ` +
          "Puedes elegir un fichero de audio en su lugar.",
      );
      setFase("error");
    }
  }

  function detener() {
    if (reloj.current !== null) {
      window.clearInterval(reloj.current);
      reloj.current = null;
    }
    grabadora.current?.stop();
  }

  async function transcribir() {
    if (!audio) return;
    setFase("transcribiendo");
    setError(null);
    try {
      const resultado = await api.transcribir(audio, nombreAudio, VOCABULARIO_SWE);
      setTranscripcion(resultado);
      setTexto(resultado.text);
      setFase("revisando");
    } catch (causa) {
      const detalle = alFallo(causa);
      setError(`No se pudo transcribir: ${detalle}`);
      setFase("error");
    }
  }

  function reiniciar() {
    setAudio(null);
    setTranscripcion(null);
    setTexto("");
    setError(null);
    setFase("inicial");
  }

  return (
    <div className={`voz-estudio voz-${fase}`}>
    <Panel
      titulo="Dictar la instrucción"
      nota="El audio se convierte en texto y el texto se te enseña para que lo revises. Nada se ejecuta hasta que tú lo confirmes."
    >
      {fase === "grabando" || fase === "transcribiendo" ? (
        <div className="voz-onda" aria-hidden="true">
          {Array.from({ length: 11 }, (_, i) => <span key={i} style={{ animationDelay: `${i * 65}ms` }} />)}
        </div>
      ) : null}
      {fase === "inicial" || fase === "error" ? (
        <Fila>
          {hayGrabadora && hayMicrofono ? (
            <button className="primario" onClick={() => void empezar()}>
              Grabar
            </button>
          ) : (
            <span className="tenue">Este navegador no ofrece grabación; usa un fichero.</span>
          )}
          <label className="sutil boton-archivo">
            Elegir un fichero de audio
            <input
              id="audio-fichero"
              type="file"
              accept="audio/*"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (!f) return;
                setAudio(f);
                setNombreAudio(f.name);
                setFase("listo");
              }}
            />
          </label>
        </Fila>
      ) : null}

      {fase === "grabando" ? (
        <Fila>
          <Chip tono="error" pulsa>
            grabando
          </Chip>
          <span className="mono">{duracion(segundos)}</span>
          <button className="primario" onClick={detener}>
            Detener
          </button>
        </Fila>
      ) : null}

      {fase === "listo" && audio ? (
        <Fila>
          <Chip tono="ok">audio listo</Chip>
          <span className="tenue mono">
            {nombreAudio} · {Math.round(audio.size / 1024)} kB
          </span>
          <button className="primario" onClick={() => void transcribir()}>
            Transcribir
          </button>
          <button onClick={reiniciar}>Descartar</button>
        </Fila>
      ) : null}

      {fase === "transcribiendo" ? (
        <p className="tenue">Transcribiendo… El audio se procesa en el servidor.</p>
      ) : null}

      {fase === "revisando" && transcripcion ? (
        <div className="transcripcion-revision">
          <div className="fila">
            <Chip tono={transcripcion.low_confidence ? "aviso" : "ok"}>
              confianza {(transcripcion.confidence * 100).toFixed(0)}%
            </Chip>
            <span className="tenue">
              {transcripcion.provider} · {transcripcion.language} ·{" "}
              {duracion(transcripcion.duration_s)}
            </span>
          </div>
          {transcripcion.low_confidence ? (
            <p className="aviso" role="alert">
              La confianza del reconocimiento está por debajo del umbral: revisa el
              texto con atención antes de usarlo.
            </p>
          ) : null}
          <label htmlFor="transcripcion-texto">Texto reconocido (editable)</label>
          <textarea
            id="transcripcion-texto"
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
          />
          <Fila sep>
            <button
              id="btn-usar-transcripcion"
              className="primario"
              disabled={!texto.trim()}
              onClick={() => alConfirmar(texto.trim(), transcripcion)}
            >
              Usar como instrucción
            </button>
            <button onClick={reiniciar}>Descartar</button>
            <span className="tenue">
              Se copia al campo de instrucción y la ejecución se registrará como
              dictada; no se ejecuta nada hasta que pulses Ejecutar.
            </span>
          </Fila>
        </div>
      ) : null}

      {error ? (
        <p className="aviso" role="alert">
          {error}
        </p>
      ) : null}
    </Panel>
    </div>
  );
}

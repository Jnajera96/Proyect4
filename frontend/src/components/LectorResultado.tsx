import { useEffect, useState } from "react";
import { iniciarLectura, localCapabilities } from "../lib/localCapabilities";

export function LectorResultado({ texto }: {texto: string}) {
  const [enabled, setEnabled] = useState(false);
  const [reading, setReading] = useState(false);
  const [message, setMessage] = useState("");
  useEffect(() => {
    let active = true;
    void localCapabilities.status().then(c => {if (active) setEnabled(c.tts.enabled);})
      .catch(() => {if (active) setMessage("No se pudo consultar la disponibilidad de lectura.");});
    return () => { active = false; window.speechSynthesis?.cancel(); };
  }, []);
  useEffect(() => { window.speechSynthesis?.cancel(); setReading(false); }, [texto]);
  function read() {
    setMessage("");
    try {
      if (!window.speechSynthesis || !window.SpeechSynthesisUtterance) {
        throw new Error("Este navegador no dispone de lectura de voz local.");
      }
      const utterance = new SpeechSynthesisUtterance();
      utterance.onstart = () => setReading(true);
      utterance.onend = () => setReading(false);
      utterance.onerror = () => {setReading(false); setMessage("La lectura se interrumpió.");};
      setReading(true);
      iniciarLectura(texto, window.speechSynthesis, utterance);
      if (texto.length > 4000) setMessage("Se leerán los primeros 4.000 caracteres del resultado.");
    } catch (error) { setReading(false); setMessage((error as Error).message); }
  }
  return <section aria-label="Lectura del resultado">
    <h3>Escuchar el resultado</h3>
    <p>Lectura voluntaria con una voz local del navegador. No se envía el texto a un servicio de voz.</p>
    {!enabled && <p>La lectura de voz no está habilitada en esta instalación.</p>}
    <div className="fila">
      <button disabled={!enabled || !texto || reading} onClick={read}>Escuchar resultado</button>
      <button disabled={!reading} onClick={() => {window.speechSynthesis?.cancel(); setReading(false);}}>Detener lectura</button>
    </div>
    {message && <p role="status">{message}</p>}
  </section>;
}

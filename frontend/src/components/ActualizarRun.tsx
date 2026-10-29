import { useRef, useState } from "react";

/** La consulta no reanuda ni vuelve a generar una ejecución detenida. */
export function ActualizarRun({ runId, alRefrescar }: {
  runId: string;
  alRefrescar: (id: string) => Promise<string[]>;
}) {
  const pendiente = useRef(false);
  const [cargando, setCargando] = useState(false);
  const [resultado, setResultado] = useState("");
  const [error, setError] = useState("");

  async function actualizar() {
    if (pendiente.current) return;
    pendiente.current = true;
    setCargando(true);
    setResultado("");
    setError("");
    try {
      const errores = await alRefrescar(runId);
      if (errores.length) setError(`No se pudo completar la consulta: ${errores.join("; ")}`);
      else setResultado(`Consulta completada a las ${new Date().toLocaleTimeString()}.`);
    } catch {
      setError("No se pudo completar la consulta. Comprueba la conexión y vuelve a intentar.");
    } finally {
      pendiente.current = false;
      setCargando(false);
    }
  }

  return <div>
    <button className="sutil" type="button" disabled={cargando} aria-busy={cargando}
      onClick={() => void actualizar()}>{cargando ? "Consultando servidor…" : "Releer del servidor"}</button>
    <p className="tenue" role="status">{cargando ? "Solicitando el estado y el historial al servidor…" : resultado}</p>
    {error ? <p className="aviso" role="alert">{error}</p> : null}
    <p className="tenue">Releer actualiza la información; no reanuda ni reintenta una ejecución detenida.</p>
  </div>;
}

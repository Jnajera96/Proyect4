/**
 * Linea de tiempo del progreso.
 *
 * **Solo pinta lo que ha llegado.** Los hitos ya alcanzados salen marcados; los
 * que aun no han llegado salen como pendientes. No hay ningun estado intermedio
 * inventado ni un temporizador que rellene huecos: si un hito no ha llegado, esta
 * pendiente, y punto.
 */
import { type EventKind } from "../lib/contracts";
import { hora } from "./ui";

/** Los hitos, en su orden canonico, con su etiqueta. */
export const HITOS: { kind: EventKind; etiqueta: string; inicial: string }[] = [
  { kind: "requirements.completed", etiqueta: "Requisitos analizados", inicial: "R" },
  { kind: "plan.completed", etiqueta: "Plan construido", inicial: "P" },
  { kind: "coder.completed", etiqueta: "Cambio propuesto", inicial: "C" },
  { kind: "tests.completed", etiqueta: "Pruebas ejecutadas", inicial: "T" },
];

interface Hito {
  kind: EventKind;
  seq: number;
  at: string;
}

export function Timeline({ hitos }: { hitos: Hito[] }) {
  const alcanzados = new Map<string, Hito>();
  for (const h of hitos) {
    // Se guarda el primero de cada tipo: el progreso de una ejecucion es una
    // secuencia, y un hito repetido (un ciclo de revisión) no debe duplicar filas.
    if (!alcanzados.has(h.kind)) alcanzados.set(h.kind, h);
  }

  const algunoAlcanzado = alcanzados.size > 0;

  return (
    <ul className="timeline">
      {HITOS.map(({ kind, etiqueta, inicial }) => {
        const h = alcanzados.get(kind);
        return (
          <li key={kind}>
            <span
              className="icono-hito"
              style={h ? undefined : { background: "var(--borde-fuerte)" }}
            >
              {inicial}
            </span>
            <span className="hito">{etiqueta}</span>
            {h ? (
              <span className="cuando">
                #{h.seq} · {hora(h.at)}
              </span>
            ) : (
              <span className="cuando tenue">pendiente</span>
            )}
          </li>
        );
      })}
      {!algunoAlcanzado ? (
        <li>
          <span className="tenue">
            Aún no ha llegado ningún hito. El progreso se actualiza con cada evento
            del servidor.
          </span>
        </li>
      ) : null}
    </ul>
  );
}

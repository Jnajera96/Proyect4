/**
 * Suscripcion al flujo SSE de una ejecucion.
 *
 * **Solo se consumen los eventos canonicos de F10.** Hasta F10 el frontend
 * escuchaba `run.status`, `run.step`, `run.awaiting_approval`, `run.report` y
 * `run.error` (los nombres heredados, AUD-11). Aqui se escuchan unicamente:
 *
 *   - los hitos por nodo: `requirements.completed`, `plan.completed`,
 *     `coder.completed`, `tests.completed`;
 *   - la puerta humana: `run.awaiting_human`;
 *   - el resultado: `run.completed`, `run.failed`;
 *   - `run.done`, que **no es un hito** sino la senal de que el flujo se cierra.
 *
 * El progreso que se pinta es el que llega de verdad. No se simula, no se
 * rellena y no se inventa un estado intermedio entre el ultimo evento recibido y
 * el siguiente: lo que se ve es lo que el servidor emitio.
 *
 * **Reconexion.** `EventSource` reenvia `Last-Event-ID` al reconectar. Como el
 * registro del backend es persistente y `seq` es monotonamente creciente, una
 * recarga o un corte de red no pierde progreso: el servidor reanuda desde el
 * ultimo `seq` visto. El `EventSource` lo gestiona el navegador; aqui solo se
 * refleja el estado de la conexion para que la interfaz lo muestre.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import {
  EVENTO_CIERRE,
  EVENTOS_ESCUCHADOS,
  type EventKind,
  type RunEvent,
} from "../lib/contracts";

export type EstadoConexion = "inactivo" | "conectando" | "conectado" | "cerrado" | "error";

interface ResultadoSse {
  eventos: RunEvent[];
  conexion: EstadoConexion;
  /** Cierra el flujo manualmente (al cambiar de ejecucion o desmontar). */
  cerrar: () => void;
}

/**
 * Escucha el flujo de una ejecucion.
 *
 * Devuelve los eventos recibidos **en orden**, sin deduplicar por `seq` en la
 * interfaz: el backend garantiza orden y unicidad, y deduplicar aqui escondería
 * un error del servidor en lugar de dejarlo visible.
 */
export function useEventosRun(runId: string | null): ResultadoSse {
  const [eventos, setEventos] = useState<RunEvent[]>([]);
  const [conexion, setConexion] = useState<EstadoConexion>("inactivo");
  const fuenteRef = useRef<EventSource | null>(null);

  const cerrar = useCallback(() => {
    if (fuenteRef.current) {
      fuenteRef.current.close();
      fuenteRef.current = null;
      setConexion("cerrado");
    }
  }, []);

  useEffect(() => {
    if (!runId) {
      setEventos([]);
      setConexion("inactivo");
      return;
    }

    // Ejecucion nueva: se empieza de cero. Reutilizar la lista anterior mezclaria
    // los eventos de dos ejecuciones distintas.
    setEventos([]);
    setConexion("conectando");

    const fuente = new EventSource(`/runs/${encodeURIComponent(runId)}/events`);
    fuenteRef.current = fuente;

    fuente.onopen = () => setConexion("conectado");

    // Un `listener` por tipo de la lista canonica. Se registran todos: un
    // `switch` sobre `kind` en el consumidor decide que hacer con cada uno, y un
    // tipo que llegue sin estar en la lista no se escucharia (y eso es
    // deliberado: la lista es el contrato).
    for (const tipo of EVENTOS_ESCUCHADOS) {
      fuente.addEventListener(tipo, (ev: MessageEvent) => {
        let evento: RunEvent;
        try {
          evento = JSON.parse(ev.data) as RunEvent;
        } catch {
          // Un evento ilegible no debe tumbar el flujo. Se ignora y se sigue.
          return;
        }
        setEventos((previos) => [...previos, evento]);
        if (evento.kind === EVENTO_CIERRE) {
          // `run.done` cierra el flujo por diseno: entre dos puertas humanas el
          // stream termina y el cliente se reconecta al reanudar. Se cierra del
          // lado del cliente para no dejar una conexion abierta que el servidor
          // ya cerro.
          fuente.close();
          fuenteRef.current = null;
          setConexion("cerrado");
        }
      });
    }

    fuente.onerror = () => {
      // `EventSource` marca `readyState === CLOSED` cuando no va a reintentar
      // (p. ej. un 404). Si sigue abierto, el navegador reintentara solo y no es
      // un error para la interfaz: se mantiene "conectando".
      if (fuente.readyState === EventSource.CLOSED) {
        setConexion("error");
      }
    };

    return () => {
      fuente.close();
      fuenteRef.current = null;
    };
  }, [runId]);

  return { eventos, conexion, cerrar };
}

/**
 * Extrae los hitos de nodo de una lista de eventos, para pintar el progreso.
 *
 * Devuelve **solo** los hitos canonicos, en el orden en que llegaron. Es la
 * lista que alimenta la linea de tiempo: nada mas, nada inventado.
 */
export function hitosDe(eventos: RunEvent[]): { kind: EventKind; seq: number; at: string }[] {
  const CANONICOS = new Set<string>([
    "requirements.completed",
    "plan.completed",
    "coder.completed",
    "tests.completed",
  ]);
  return eventos
    .filter((e) => CANONICOS.has(e.kind))
    .map((e) => ({ kind: e.kind, seq: e.seq, at: e.at }));
}

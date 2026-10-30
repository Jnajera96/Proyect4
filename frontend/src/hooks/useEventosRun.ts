/**
 * Suscripcion al flujo SSE de una ejecucion.
 *
 * **Solo se consumen los eventos canonicos de F10.** Hasta F10 el frontend
 * escuchaba `run.status`, `run.step`, `run.awaiting_approval`, `run.report` y
 * `run.error` (los nombres heredados, AUD-11). Aqui se escuchan unicamente:
 *   - arranque: `run.created`, `run.started`, para seguir toda la secuencia;
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
 *
 * **La clave de API viaja en la query.** `EventSource` no puede enviar
 * cabeceras; el backend admite `?api_key=` **solo en este flujo** por eso. Es
 * una excepcion con precio -la clave acaba en registros de acceso y proxies-,
 * asi que se usa unicamente aqui. Cambiar la credencial en memoria reconecta el
 * flujo con la nueva, que es lo contrario de dejarlo silenciosamente sin
 * autorizar. La URL con la credencial no se muestra en ningun sitio de la
 * interfaz.
 *
 * **Deuda declarada: TD-02 — Replace SSE query key with one-use ticket.** Lo que
 * cierra el precio de esta excepcion es sustituir la clave por un vale de un solo
 * uso emitido por un endpoint autenticado, y eso es un cambio de backend: **no se
 * toca aqui**. Mientras siga abierta, el mecanismo de este fichero se conserva
 * exactamente como esta.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import {
  EVENTO_CIERRE,
  EVENTOS_ESCUCHADOS,
  ESTADOS_TERMINALES,
  type EventKind,
  type RunEvent,
  type RunStatus,
  type RunState,
} from "../lib/contracts";
import { useClaveApi } from "../lib/auth";
import { api } from "../lib/api";

export type EstadoConexion = "inactivo" | "conectando" | "conectado" | "cerrado" | "error";

interface ResultadoSse {
  eventos: RunEvent[];
  conexion: EstadoConexion;
  /** Cierra el flujo manualmente (al cambiar de ejecucion o desmontar). */
  cerrar: () => void;
  reanudar: () => void;
  errorReconciliacion: string;
}

/**
 * Escucha el flujo de una ejecucion.
 *
 * Descarta repeticiones y reconcilia huecos contra el snapshot autoritativo.
 * La recuperacion solo lee estado; nunca reanuda agentes ni decisiones humanas.
 */
export function useEventosRun(runId: string | null, onSnapshot?: (state: RunState) => void): ResultadoSse {
  const [eventos, setEventos] = useState<RunEvent[]>([]);
  const [conexion, setConexion] = useState<EstadoConexion>("inactivo");
  const fuenteRef = useRef<EventSource | null>(null);
  const clave = useClaveApi();
  const activeSelection = useRef({ runId, clave });
  activeSelection.current = { runId, clave };
  const [revision, setRevision] = useState(0);
  const cursor = useRef(0);
  const snapshotCallback = useRef(onSnapshot);
  snapshotCallback.current = onSnapshot;
  const needsSnapshot = useRef(false);
  const [errorReconciliacion, setErrorReconciliacion] = useState("");
  const identidad = useRef<{ runId: string | null; clave: string | null }>({ runId: null, clave: null });
  const reanudar = useCallback(() => {
    setRevision(v => v + 1);
  }, []);

  const cerrar = useCallback(() => {
    if (fuenteRef.current) {
      fuenteRef.current.close();
      fuenteRef.current = null;
      setConexion("cerrado");
    }
  }, []);

  useEffect(() => {
    if (!runId) {
      identidad.current = { runId: null, clave: null };
      cursor.current = 0;
      needsSnapshot.current = false;
      setErrorReconciliacion("");
      setEventos([]);
      setConexion("inactivo");
      return;
    }

    if (identidad.current.runId !== runId || identidad.current.clave !== clave) {
      identidad.current = { runId, clave };
      cursor.current = 0;
      needsSnapshot.current = false;
      setErrorReconciliacion("");
      setEventos([]);
    }
    setConexion("conectando");

    // Sin clave, la URL va limpia: con la autenticacion desactivada el servidor
    // no necesita nada mas, y anadir un parametro vacio seria ruido.
    const parametros = new URLSearchParams();
    if (clave) parametros.set("api_key", clave);
    if (cursor.current) parametros.set("after", String(cursor.current));
    const consulta = parametros.size ? `?${parametros}` : "";
    const fuente = new EventSource(`/runs/${encodeURIComponent(runId)}/events${consulta}`);
    let vigente = true;
    fuenteRef.current = fuente;

    let recovering = false;
    let gapVersion = 0;
    async function reconcile() {
      if (recovering || !vigente || !runId) return;
      recovering = true;
      const requestedVersion = gapVersion;
      try {
        const snapshot = await api.obtenerRun(runId);
        if (!vigente || activeSelection.current.runId !== runId || activeSelection.current.clave !== clave) return;
        snapshotCallback.current?.(snapshot);
        needsSnapshot.current = requestedVersion !== gapVersion;
        setErrorReconciliacion("");
      } catch {
        if (vigente) setErrorReconciliacion("No se pudo recuperar el estado tras perder eventos. Vuelve a reconciliar.");
      } finally {
        recovering = false;
        if (vigente && needsSnapshot.current && requestedVersion !== gapVersion) void reconcile();
      }
    }

    fuente.onopen = () => { if (vigente) { setConexion("conectado"); if (needsSnapshot.current) void reconcile(); } };

    // Un `listener` por tipo de la lista canonica. Se registran todos: un
    // `switch` sobre `kind` en el consumidor decide que hacer con cada uno, y un
    // tipo que llegue sin estar en la lista no se escucharia (y eso es
    // deliberado: la lista es el contrato).
    for (const tipo of EVENTOS_ESCUCHADOS) {
      fuente.addEventListener(tipo, (ev: MessageEvent) => {
        if (!vigente) return;
        let evento: RunEvent;
        try {
          evento = JSON.parse(ev.data) as RunEvent;
        } catch {
          // Un evento ilegible no debe tumbar el flujo. Se ignora y se sigue.
          return;
        }
        if (!Number.isSafeInteger(evento.seq) || evento.seq <= cursor.current) return;
        if (evento.seq !== cursor.current + 1) {
          gapVersion++;
          needsSnapshot.current = true;
          setEventos([]);
          void reconcile();
        }
        cursor.current = evento.seq;
        setConexion("conectado");
        setEventos((previos) => [...previos, evento]);
        if (evento.kind === EVENTO_CIERRE &&
            ESTADOS_TERMINALES.has(evento.data.status as RunStatus)) {
          // Solo el cierre terminal detiene EventSource. Un run historico puede
          // contener varios cierres de puertas: cerrarse en el primero pierde
          // los hitos posteriores. Entre lotes el navegador reconecta con
          // Last-Event-ID; una decision humana reabre desde el cursor guardado.
          fuente.close();
          fuenteRef.current = null;
          setConexion("cerrado");
        }
      });
    }

    fuente.onerror = () => {
      if (!vigente) return;
      // `EventSource` marca `readyState === CLOSED` cuando no va a reintentar
      // (p.ej. un 404). Si sigue abierto, el navegador reintentara solo y no es
      // un error para la interfaz: se mantiene "conectando".
      if (fuente.readyState === EventSource.CLOSED) {
        setConexion("error");
      } else {
        setConexion("conectando");
      }
    };

    return () => {
      vigente = false;
      fuente.close();
      fuenteRef.current = null;
    };
    // `clave` en las dependencias: guardarla u olvidarla debe reabrir el flujo
    // con la credencial nueva. Sin eso, el flujo seguiria con la clave vieja
    // hasta recargar la pagina.
  }, [runId, clave, revision]);

  return { eventos, conexion, cerrar, reanudar, errorReconciliacion };
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

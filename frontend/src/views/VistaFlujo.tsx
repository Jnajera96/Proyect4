/**
 * Flujo: por donde va la ejecucion seleccionada.
 *
 * Solo representa lo que el estado declara. Cuando no hay ejecucion elegida lo dice
 * en lugar de dibujar un diagrama vacio, y cuando la hay ensena el `next_step` tal
 * como lo publica el motor, sin traducirlo a una promesa.
 */
import type { RunState } from "../lib/contracts";
import { ETIQUETA_ESTADO } from "../lib/contracts";
import { DiagramaFlujo } from "../components/DiagramaFlujo";
import { Chip, EstadoVacio, Panel, Seccion } from "../components/ui";

export function VistaFlujo({ estado }: { estado: RunState | null }) {
  if (!estado) {
    return (
      <Panel>
        <EstadoVacio titulo="Ninguna ejecución seleccionada">
          El flujo se dibuja a partir del estado de una ejecución: qué etapas ya
          están hechas, cuál espera una decisión humana y cuál es la siguiente. Elige
          una ejecución para verlo.
        </EstadoVacio>
      </Panel>
    );
  }

  const espera = estado.status.startsWith("awaiting");
  const subtarea = estado.plan?.subtasks[estado.plan_index];
  const subtareaActiva = estado.status === "running" && subtarea !== undefined &&
    estado.next_step === subtarea.agent;

  return (
    <>
      <Seccion
        titulo="Etapas del flujo"
        nota="Los nodos reales del grafo, en su orden. El estado de cada etapa sale de la evidencia guardada, no de un temporizador."
        acciones={<Chip tono={espera ? "aviso" : ""}>{ETIQUETA_ESTADO[estado.status]}</Chip>}
      >
        <Panel>
          <DiagramaFlujo estado={estado} />
        </Panel>
      </Seccion>

      <Seccion titulo="Posición declarada por el motor">
        <Panel>
          <dl className="datos">
            <dt>estado</dt>
            <dd>
              {ETIQUETA_ESTADO[estado.status]} <span className="tenue mono">({estado.status})</span>
            </dd>
            <dt>siguiente paso</dt>
            <dd className="mono">{estado.next_step ?? "(ninguno: la ejecución terminó)"}</dd>
            <dt>subtarea activa</dt>
            <dd>
              {subtareaActiva
                ? `${estado.plan_index + 1} de ${estado.plan!.subtasks.length}`
                : estado.plan ? "ninguna activa" : "sin plan"}
            </dd>
          </dl>
          {espera ? (
            <p className="aviso" role="status">
              El flujo está detenido en una puerta humana. No avanza hasta que alguien
              decida.
            </p>
          ) : null}
        </Panel>
      </Seccion>
    </>
  );
}

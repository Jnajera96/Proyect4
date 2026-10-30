/**
 * Flujo: por donde va la ejecucion seleccionada.
 *
 * Solo representa lo que el estado declara. Cuando no hay ejecucion elegida lo dice
 * en lugar de dibujar un diagrama vacio, y cuando la hay ensena el `next_step` tal
 * como lo publica el motor, sin traducirlo a una promesa.
 */
import { useState } from "react";
import type { RunEvent, RunState } from "../lib/contracts";
import { ActividadPipeline } from "../components/ActividadPipeline";
import { ETIQUETA_ESTADO } from "../lib/contracts";
import { calcular, type Etapa } from "../components/DiagramaFlujo";
import { SecuenciaAgentes } from "../components/SecuenciaAgentes";
import { InspectorEtapa } from "../components/InspectorEtapa";
import { Chip, EstadoVacio, Panel, Seccion } from "../components/ui";

export function VistaFlujo({ estado, eventos = [], alPuerta }: { estado: RunState | null; eventos?: RunEvent[]; alPuerta?: () => void }) {
  const [etapa, setEtapa] = useState<Etapa | null>(null);
  const etapaActual = estado && etapa ? calcular(estado, eventos).find(e => e.id === etapa.id) : null;
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
      <Panel><p>{estado.options.delivery_mode === "github" ? "Modo GitHub" : "Modo local"}:
        la aplicación se construye primero en tu computadora. Publicar en GitHub requiere tu decisión.</p></Panel>
      <ActividadPipeline eventos={eventos} estado={estado} />
      <Seccion
        titulo="Etapas del flujo"
        nota="Los nodos reales del grafo, en su orden. El estado de cada etapa sale de la evidencia guardada, no de un temporizador."
        acciones={<Chip tono={espera ? "aviso" : ""}>{ETIQUETA_ESTADO[estado.status]}</Chip>}
      >
        <Panel>
          <SecuenciaAgentes estado={estado} alEtapa={setEtapa} eventos={eventos} />
        </Panel>
      </Seccion>

      {etapaActual ? <InspectorEtapa key={estado.run_id + etapaActual.id} etapa={etapaActual} estado={estado} eventos={eventos} alCerrar={() => setEtapa(null)} alPuerta={alPuerta} /> : null}
      <Seccion titulo="Posición declarada por el motor">
        <Panel>
          <dl className="datos">
            <dt>Estado</dt>
            <dd>
              {ETIQUETA_ESTADO[estado.status]} <span className="tenue mono">({estado.status})</span>
            </dd>
            <dt>Siguiente paso</dt>
            <dd className="mono">{estado.next_step ?? "(ninguno: la ejecución terminó)"}</dd>
            <dt>Subtarea activa</dt>
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

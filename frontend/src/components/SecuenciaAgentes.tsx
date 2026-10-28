/** Adaptación de WorkflowPipeline de Antigravity al estado canónico actual. */
import type { RunEvent, RunState } from "../lib/contracts";
import { calcular, type Etapa } from "./DiagramaFlujo";
import { Chip } from "./ui";
const CONTRATOS: Record<string, string> = {
  requisitos: "TaskInterpretation", supervisor: "RunPlan", investigador: "outputs.researcher_output",
  coder: "outputs.coder_output", pruebas: "evidence.test_runs", revisor: "ReviewVerdict",
  aprobacion: "approvals", promocion: "final_report",
};
const ETIQUETAS = { hecha: "completada", "en-curso": "en curso", esperando: "espera decisión humana", fallida: "fallida", pendiente: "pendiente", omitida: "No aplica", bloqueada: "bloqueada / no ejecutada" };
const TONOS = { hecha: "ok", "en-curso": "acento", esperando: "aviso", fallida: "error", pendiente: "", omitida: "", bloqueada: "aviso" } as const;
export function SecuenciaAgentes({ estado, alEtapa, eventos = [] }: { estado: RunState; alEtapa: (etapa: Etapa) => void; eventos?: RunEvent[] }) {
  return <ol className="secuencia-agentes" aria-label="Secuencia coordinada de ocho etapas">
    {calcular(estado, eventos).map((etapa, indice) => <li key={etapa.id} className={`flujo-etapa ${etapa.estado}`}>
      <button className={`secuencia-etapa ${etapa.estado}`} onClick={() => alEtapa(etapa)} aria-label={`Inspeccionar etapa: ${etapa.nombre}`}>
        <span className="secuencia-indice" aria-hidden="true">{indice + 1}</span>
        <span className="secuencia-rol"><strong>{etapa.nombre}</strong><span>{etapa.detalle}</span></span>
        <span className="secuencia-contrato"><span>Contrato / evidencia</span><code>{CONTRATOS[etapa.id]}</code></span>
        <Chip tono={TONOS[etapa.estado]}>{ETIQUETAS[etapa.estado]}</Chip><span aria-hidden="true">›</span>
      </button>
    </li>)}
  </ol>;
}

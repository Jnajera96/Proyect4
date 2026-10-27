import { useEffect, useRef } from "react";
import type { RunState } from "../lib/contracts";
import type { Etapa } from "./DiagramaFlujo";
import { PanelPlan, PanelPruebas, PanelReviewer, HistorialAprobaciones, ListaHallazgos } from "./evidencia";
import { VisorDiff } from "./VisorDiff";

/** Solo lectura: las decisiones conservan sus puertas y handlers originales. */
export function InspectorEtapa({ etapa, estado, alCerrar }: {
  etapa: Etapa; estado: RunState; alCerrar: () => void;
}) {
  const dialogo = useRef<HTMLDialogElement>(null);
  const origen = useRef(document.activeElement instanceof HTMLElement ? document.activeElement : null);
  useEffect(() => {
    const dialog = dialogo.current;
    dialog?.showModal();
    return () => { dialog?.close(); origen.current?.focus({ preventScroll: true }); };
  }, []);
  const diff = estado.artifacts.diff ?? estado.outputs.coder_output?.diff ?? "";
  const investigacion = estado.outputs.researcher_output;
  return <dialog ref={dialogo} className="inspector-etapa" aria-labelledby="inspector-titulo" onCancel={alCerrar}>
    <header className="inspector-cabecera"><div><p className="hero-antetitulo">Evidencia de la etapa</p><h2 id="inspector-titulo">{etapa.nombre}</h2></div>
      <button onClick={alCerrar} aria-label="Cerrar inspector de etapa">Cerrar</button></header>
    <p className="tenue">{etapa.detalle}</p>
    <p className="mono tenue">{estado.run_id} · {etapa.nodo}</p>
    {etapa.id === "requisitos" ? <section><h3>Interpretación registrada</h3><p>{estado.interpretation?.rationale ?? "Todavía no hay interpretación registrada."}</p><p className="tenue">La confirmación se realiza en la puerta de requisitos de la ejecución.</p></section> : null}
    {etapa.id === "supervisor" ? estado.plan ? <PanelPlan plan={estado.plan} indice={estado.plan_index} status={estado.status} siguiente={estado.next_step} /> : <p>Sin plan registrado.</p> : null}
    {etapa.id === "investigador" ? <section><h3>Investigación</h3>{investigacion ? <><ListaHallazgos hallazgos={investigacion.findings} /><h3>Incógnitas declaradas</h3><ul>{investigacion.unknowns.map((texto, i) => <li key={i}>{texto}</li>)}</ul>{!investigacion.unknowns.length ? <p>Sin incógnitas declaradas.</p> : null}</> : <p>Sin evidencia de investigación registrada.</p>}</section> : null}
    {etapa.id === "coder" ? <section><h3>Cambio propuesto</h3>{diff ? <VisorDiff texto={diff} /> : <p>Sin diff registrado.</p>}</section> : null}
    {etapa.id === "pruebas" ? <PanelPruebas pruebas={estado.evidence.test_runs} /> : null}
    {etapa.id === "revisor" ? estado.outputs.reviewer_output ? <PanelReviewer veredicto={estado.outputs.reviewer_output} /> : <p>Sin veredicto registrado.</p> : null}
    {etapa.id === "aprobacion" ? <><HistorialAprobaciones aprobaciones={estado.approvals} /><p className="aviso">Revisa y decide en el detalle de la ejecución. Este inspector es de solo lectura.</p></> : null}
    {etapa.id === "promocion" ? <section><h3>Resultado declarado</h3>{estado.final_report ? <p>{estado.final_report.changes_applied.length} cambio(s) aplicado(s) en el informe final.</p> : <p>Todavía no hay informe final de promoción.</p>}<p className="tenue">Aprobar autoriza la promoción; el éxito se acredita con el resultado del motor.</p></section> : null}
  </dialog>;
}

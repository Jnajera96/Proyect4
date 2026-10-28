import { useEffect, useRef } from "react";
import type { RunEvent, RunState } from "../lib/contracts";
import { actividadesPendientes, ActividadPipeline } from "./ActividadPipeline";
import type { Etapa } from "./DiagramaFlujo";
import { PanelPlan, PanelPruebas, PanelReviewer, HistorialAprobaciones, ListaHallazgos } from "./evidencia";
import { VisorDiff } from "./VisorDiff";

/** Solo lectura: las decisiones conservan sus puertas y handlers originales. */
export function InspectorEtapa({ etapa, estado, alCerrar, eventos = [], alPuerta }: {
  etapa: Etapa; estado: RunState; alCerrar: () => void; eventos?: RunEvent[]; alPuerta?: () => void;
}) {
  const dialogo = useRef<HTMLDialogElement>(null);
  const origen = useRef(document.activeElement instanceof HTMLElement ? document.activeElement : null);
  useEffect(() => {
    const dialog = dialogo.current;
    dialog?.showModal();
    return () => { dialog?.close(); origen.current?.focus({ preventScroll: true }); };
  }, []);
  const diff = estado.artifacts.diff || estado.outputs.coder_output?.diff || "";
  const pruebasActivas = estado.status === "running" && actividadesPendientes(eventos).some(e => e.data.node === "run_tests");
  const investigacion = estado.outputs.researcher_output;
  return <dialog ref={dialogo} className="inspector-etapa" aria-labelledby="inspector-titulo" onCancel={alCerrar}>
    <header className="inspector-cabecera"><div><p className="hero-antetitulo">Evidencia de la etapa</p><h2 id="inspector-titulo">{etapa.nombre}</h2></div>
      <button onClick={alCerrar} aria-label="Cerrar inspector de etapa">Cerrar</button></header>
    <p className="tenue">{etapa.detalle}</p>
    <p className="mono tenue">{estado.run_id} · {etapa.nodo}</p>
    {eventos.length ? <ActividadPipeline eventos={eventos} estado={estado} nodo={etapa.nodo} /> : null}
    {alPuerta && ((etapa.id === "requisitos" && estado.status === "awaiting_human_requirements_confirmation") || (etapa.id === "aprobacion" && estado.status === "awaiting_approval")) ? <button className="primario" onClick={alPuerta}>Abrir puerta para revisar y decidir</button> : null}
    {etapa.id === "requisitos" ? <section><h3>Interpretación registrada</h3><p>{estado.interpretation?.rationale ?? "Todavía no hay interpretación registrada."}</p><p>Confirmación inicial de requisitos: {estado.instruction.confirmed_by_user ? "confirmada por una persona" : "todavía no confirmada"}. Esta confirmación no autoriza la promoción de archivos.</p><p className="tenue">La confirmación se realiza en la puerta de requisitos de la ejecución.</p></section> : null}
    {etapa.id === "supervisor" ? estado.plan ? <PanelPlan plan={estado.plan} indice={estado.plan_index} status={estado.status} siguiente={estado.next_step} /> : <p>Sin plan registrado.</p> : null}
    {etapa.id === "investigador" ? <section><h3>Investigación</h3>{investigacion ? <><ListaHallazgos hallazgos={investigacion.findings} /><h3>Incógnitas declaradas</h3><ul>{investigacion.unknowns.map((texto, i) => <li key={i}>{texto}</li>)}</ul>{!investigacion.unknowns.length ? <p>Sin incógnitas declaradas.</p> : null}</> : <p>Sin evidencia de investigación registrada.</p>}</section> : null}
    {etapa.id === "coder" ? <section><h3>Cambio propuesto</h3><p>{estado.outputs.code_proposal?.rationale ?? estado.outputs.coder_output?.rationale ?? "Sin propuesta registrada."}</p>{diff ? <VisorDiff texto={diff} /> : <p>Sin diff registrado. Esta etapa no acredita un cambio completado.</p>}{estado.errors.filter(e => e.agent === "coder" || e.error_class.startsWith("MODEL_") || e.error_class.startsWith("SANDBOX_")).map((e, i) => <p className="aviso" key={i}>{e.error_class}: {e.message}</p>)}{estado.errors.some(e => e.error_class === "SANDBOX_NO_REPO") ? <p className="aviso">Selecciona un proyecto Git registrado en el compositor e inicia una nueva ejecución con ese repositorio autorizado.</p> : null}</section> : null}
    {etapa.id === "pruebas" && etapa.estado !== "omitida" && (!pruebasActivas || estado.evidence.test_runs.length > 0) ? <PanelPruebas pruebas={estado.evidence.test_runs} /> : null}
    {etapa.id === "revisor" ? estado.outputs.reviewer_output ? <PanelReviewer veredicto={estado.outputs.reviewer_output} /> : <p>Sin veredicto registrado.</p> : null}
    {etapa.id === "aprobacion" ? <><HistorialAprobaciones aprobaciones={estado.approvals} /><p className="aviso">Revisa y decide en el detalle de la ejecución. Este inspector es de solo lectura.</p></> : null}
    {etapa.id === "promocion" ? <section><h3>Resultado declarado</h3>{estado.final_report ? <p>{estado.final_report.changes_applied.length} cambio(s) aplicado(s) en el informe final.</p> : <p>Todavía no hay informe final de promoción.</p>}<p className="tenue">Aprobar autoriza la promoción; el éxito se acredita con el resultado del motor.</p></section> : null}
  </dialog>;
}

/**
 * Barra de contexto del estudio.
 *
 * Responde de un vistazo a las tres preguntas que antes obligaban a cambiar de
 * vista: **¿qué ejecución estoy mirando?**, **¿en qué etapa va?** y **¿cuánto
 * presupuesto lleva?**
 *
 * **No inventa estado.** Las etapas salen de `calcular` -la misma función que
 * pinta el diagrama de flujo-, así que la barra y el diagrama no pueden decir
 * cosas distintas. El presupuesto sale de `estado.budget` tal cual lo manda el
 * backend; si no hay límite monetario no se dibuja una barra de coste.
 */
import { useMemo } from "react";
import { ESTADOS_TERMINALES, ETIQUETA_ESTADO, type Project, type RunError, type RunEvent, type RunState } from "../lib/contracts";
import { calcular } from "./DiagramaFlujo";
import type { VistaId } from "./Navegacion";

const TONO_ESTADO: Record<string, string> = {
  running: "acento",
  planned: "",
  awaiting_human_requirements_confirmation: "aviso",
  awaiting_approval: "aviso",
  paused: "aviso",
  completed: "ok",
  failed: "error",
  needs_human: "aviso",
  cancelled: "",
};

/** Etiqueta corta para la barra: las largas (con emoji) son para el banner. */
const ESTADO_CORTO: Record<string, string> = {
  awaiting_human_requirements_confirmation: "esperando requisitos",
  awaiting_approval: "esperando aprobación",
};

function porcentaje(usado: number, maximo: number): number {
  return maximo > 0 ? Math.min(100, Math.max(0, (usado / maximo) * 100)) : 0;
}

export function BarraContexto({
  estado,
  eventos,
  proyectos,
  alIrA,
}: {
  estado: RunState | null;
  eventos: RunEvent[];
  proyectos: Project[];
  alIrA: (vista: VistaId) => void;
}) {
  const etapas = useMemo(() => (estado ? calcular(estado, eventos) : []), [estado, eventos]);
  if (!estado) return null;

  const proyecto = proyectos.find((p) => p.repo_path === estado.options.repo_path);
  const activo = !ESTADOS_TERMINALES.has(estado.status);
  const tokens = porcentaje(estado.budget.used_tokens, estado.budget.max_tokens);
  const tiempo = porcentaje(estado.budget.elapsed_seconds, estado.budget.max_seconds);
  const tono = (pct: number) => (pct >= 90 ? "error" : pct >= 70 ? "aviso" : "");

  const errorPresupuesto = [...(estado?.errors || [])].reverse().find(
    (e: RunError) => e.error_class === "BUDGET_EXCEEDED"
  );
  const esPausaPresupuesto = estado?.status === "paused" && Boolean(errorPresupuesto);
  const textoEstado = esPausaPresupuesto
    ? "pausado por presupuesto"
    : (ESTADO_CORTO[estado.status] ?? ETIQUETA_ESTADO[estado.status]);

  return (
    <section className="barra-contexto" aria-label="Contexto de la ejecución seleccionada">
      <div className="bc-identidad">
        <span className={`bc-punto ${TONO_ESTADO[estado.status] ?? ""}${activo ? " vivo" : ""}`} aria-hidden="true" />
        <div className="bc-textos">
          <span className="bc-ruta">
            {proyecto ? <span className="bc-proyecto">{proyecto.name}</span> : null}
            {proyecto ? <span className="bc-sep" aria-hidden="true">/</span> : null}
            <button type="button" className="bc-run mono" onClick={() => alIrA("detalle")} title="Abrir el detalle de la ejecución">
              {estado.run_id}
            </button>
          </span>
          <span className={`bc-estado ${TONO_ESTADO[estado.status] ?? ""}`}>
            {textoEstado}
          </span>
        </div>
      </div>

      {etapas.length ? (
        <ol className="bc-etapas" aria-label="Etapas de la ejecución">
          {etapas.map((e) => (
            <li key={e.id} className={`bc-etapa ${e.estado}`} title={`${e.nombre}: ${e.detalle}`}>
              <span className="bc-etapa-marca" aria-hidden="true" />
              <span className="bc-etapa-nombre">{e.nombre}</span>
            </li>
          ))}
        </ol>
      ) : null}

      <div className="bc-metricas">
        <div className="bc-metrica" title={`${estado.budget.used_tokens.toLocaleString()} de ${estado.budget.max_tokens.toLocaleString()} tokens`}>
          <span className="bc-metrica-rotulo">Tokens</span>
          <span className={`bc-medidor ${tono(tokens)}`} role="progressbar" aria-label="Tokens consumidos"
            aria-valuenow={Math.round(tokens)} aria-valuemin={0} aria-valuemax={100}>
            <span style={{ width: `${tokens}%` }} />
          </span>
          <span className="bc-metrica-valor mono">{Math.round(tokens)}%</span>
        </div>
        <div className="bc-metrica" title={`${Math.round(estado.budget.elapsed_seconds)} s de ${Math.round(estado.budget.max_seconds)} s`}>
          <span className="bc-metrica-rotulo">Tiempo</span>
          <span className={`bc-medidor ${tono(tiempo)}`} role="progressbar" aria-label="Tiempo consumido"
            aria-valuenow={Math.round(tiempo)} aria-valuemin={0} aria-valuemax={100}>
            <span style={{ width: `${tiempo}%` }} />
          </span>
          <span className="bc-metrica-valor mono">{Math.round(tiempo)}%</span>
        </div>
        <button type="button" className="bc-accion" onClick={() => alIrA("flujo")}>
          Ver flujo
        </button>
      </div>
    </section>
  );
}

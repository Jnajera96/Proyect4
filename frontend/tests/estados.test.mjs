// Regresiones de componentes reales, renderizados en memoria. Sin backend ni red.
// Ejecutar desde frontend: node --test tests/estados.test.mjs
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { build } from "esbuild";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

const require = createRequire(import.meta.url);
async function cargar(ruta) {
  const resultado = await build({
    entryPoints: [fileURLToPath(new URL(ruta, import.meta.url))],
    bundle: true, write: false, platform: "node", format: "cjs", jsx: "automatic",
    external: ["react", "react/jsx-runtime"],
  });
  const modulo = { exports: {} };
  new Function("require", "module", "exports", resultado.outputFiles[0].text)(
    require, modulo, modulo.exports,
  );
  return modulo.exports;
}
const { DiagramaFlujo } = await cargar("../src/components/DiagramaFlujo.tsx");
const { PanelPlan, PanelPresupuesto } = await cargar("../src/components/evidencia.tsx");
const { VistaFlujo } = await cargar("../src/views/VistaFlujo.tsx");
const { api } = await cargar("../src/lib/api.ts");
const { VisorDiff } = await cargar("../src/components/VisorDiff.tsx");

const decision = (valor) => ({
  action: "promote_changes", actor: "usuario", decided_at: "2026-10-14T12:00:00Z",
  content_sha256: "a".repeat(64), decision: valor, reason: "decision de prueba",
});
function estado(cambios = {}) {
  return {
    run_id: "run-regresion", trace_id: "trace-regresion", status: "running",
    created_at: "2026-10-14T12:00:00Z", updated_at: "2026-10-14T12:01:00Z",
    instruction: { text: "cambio de prueba", source: "text", confirmed_by_user: true, transcript_meta: null },
    options: { repo_path: null, allowed_paths: [], protected_paths: [] },
    interpretation: null, plan: null, plan_index: 0,
    artifacts: { diff: "diff de prueba", changed_files: [{ path: "app.py", added: 1, removed: 0, sha256: "a".repeat(64) }], base_commit: null, worktree_path: null },
    outputs: { coder_output: null, researcher_output: null, reviewer_output: null },
    evidence: { test_runs: [], findings: [] }, approvals: [],
    budget: { max_tokens: 100, used_tokens: 0, used_input_tokens: 0, used_output_tokens: 0,
      max_tool_calls: 10, used_tool_calls: 0, max_model_calls: 10, used_model_calls: 0,
      max_seconds: 60, elapsed_seconds: 0, max_cost: null, used_cost: 0,
      max_review_cycles: 2, review_cycles_used: 0 },
    errors: [], human_feedback: [], final_report: null, next_step: null,
    ...cambios,
  };
}
const informe = { summary: "completado", changes_applied: ["app.py (+1/-0)"], tests_executed: [], pending: [], review: "accept" };
function etapas(run) {
  const html = renderToStaticMarkup(React.createElement(DiagramaFlujo, { estado: run }));
  const filas = [...html.matchAll(/<li class="flujo-etapa ([^"]+)">([\s\S]*?)<\/li>/g)];
  return Object.fromEntries(filas.map(([, clase, contenido]) => [
    /class="flujo-nombre">([^<]+)/.exec(contenido)[1], { clase, contenido },
  ]));
}

test("aprobacion con informe exitoso terminal muestra promocion completada", () => {
  const e = etapas(estado({ status: "completed", approvals: [decision("approved")], final_report: informe }));
  assert.equal(e["Promoción al repositorio"].clase, "hecha");
});
test("approved seguido de PROMOTION_FAILED muestra promocion fallida", () => {
  const e = etapas(estado({ status: "needs_human", approvals: [decision("approved")],
    errors: [{ error_class: "PROMOTION_FAILED", agent: "supervisor", message: "fallo sintetico", recoverable: false, occurred_at: "2026-10-14T12:01:00Z", subtask_id: null }] }));
  assert.equal(e["Promoción al repositorio"].clase, "fallida");
});
test("aprobar solo autoriza, no prueba que el parche ya se aplico", () => {
  const e = etapas(estado({ next_step: "promote_changes", approvals: [decision("approved")] }));
  assert.notEqual(e["Promoción al repositorio"].clase, "hecha");
});
test("solicitar cambios vuelve al ciclo sin completar promocion", () => {
  const e = etapas(estado({ next_step: "coder", approvals: [decision("modified")] }));
  assert.equal(e["Promoción al repositorio"].clase, "pendiente");
});
test("solicitar cambios, nueva revision y approved usa la ultima decision", () => {
  const e = etapas(estado({ status: "completed", approvals: [decision("modified"), decision("approved")],
    outputs: { coder_output: null, researcher_output: null, reviewer_output: { decision: "accept", summary: "segunda revision", findings: [], required_fixes: [] } }, final_report: informe }));
  assert.equal(e["Promoción al repositorio"].clase, "hecha");
  assert.match(e["Aprobación humana"].contenido, /Decisión: approved/);
});
test("ultima decision rejected impide promocion aunque antes hubiera approved", () => {
  const e = etapas(estado({ status: "cancelled", approvals: [decision("approved"), decision("rejected")] }));
  assert.equal(e["Promoción al repositorio"].clase, "pendiente");
  assert.match(e["Aprobación humana"].contenido, /Decisión: rejected/);
});
test("completed sin evidencia final de cambios no afirma promocion", () => {
  const e = etapas(estado({ status: "completed", approvals: [decision("approved")] }));
  assert.notEqual(e["Promoción al repositorio"].clase, "hecha");
});

const plan = { subtasks: [{ id: "s1", description: "investigar", agent: "researcher", status: "pending", done_criteria: "evidencia" }], rationale: "plan de prueba", max_review_cycles: 2 };
function panel(status, next_step = "researcher", indice = 0) {
  return renderToStaticMarkup(React.createElement(PanelPlan, {
    plan, indice, status, siguiente: next_step,
  }));
}
for (const status of ["completed", "failed", "cancelled", "needs_human", "planned", "awaiting_approval", "awaiting_human_requirements_confirmation"]) {
  test(`subtarea no aparece activa con run ${status}`, () => {
    assert.doesNotMatch(panel(status), /class="actual"|>en curso</);
  });
}
test("subtarea compatible con run running y siguiente researcher puede estar activa", () => {
  assert.match(panel("running"), /class="actual"/);
});
test("indice sin siguiente compatible no marca una subtarea activa", () => {
  assert.doesNotMatch(panel("running", "approval_gate"), /class="actual"|>en curso</);
});
test("indice agotado no marca una subtarea activa", () => {
  assert.doesNotMatch(panel("running", "researcher", 1), /class="actual"|>en curso</);
});
test("un status running historico de subtarea no afirma actividad en un run terminado", () => {
  const html = renderToStaticMarkup(React.createElement(PanelPlan, {
    plan: { ...plan, subtasks: [{ ...plan.subtasks[0], status: "running" }] },
    indice: 0, status: "completed", siguiente: null,
  }));
  assert.doesNotMatch(html, /class="actual"|en curso/);
});
test("vista de flujo no declara subtarea en curso durante una puerta humana", () => {
  const html = renderToStaticMarkup(React.createElement(VistaFlujo, { estado: estado({
    plan, status: "awaiting_approval", next_step: "approval_gate",
  }) }));
  assert.doesNotMatch(html, /subtarea en curso/);
  assert.match(html, /ninguna activa/);
});
test("crear run transmite el alcance real sin entradas vacias", async () => {
  const original = globalThis.fetch;
  let cuerpo;
  globalThis.fetch = async (_url, init) => {
    cuerpo = JSON.parse(init.body);
    return new Response(JSON.stringify(estado()), { status: 202 });
  };
  try {
    await api.crearRun("inspecciona", undefined, undefined, {
      allowed_paths: [" src/ ", "", "tests/"], protected_paths: [".env", "  "],
    });
    assert.deepEqual(cuerpo.options, { allowed_paths: ["src/", "tests/"], protected_paths: [".env"] });
  } finally { globalThis.fetch = original; }
});
test("presupuesto sin limite no inventa disponibilidad de tarifas ni duracion", () => {
  const html = renderToStaticMarkup(React.createElement(PanelPresupuesto, { budget: estado().budget }));
  assert.doesNotMatch(html, /tarifas no configuradas|tiempo transcurrido|0\.0000/);
  assert.match(html, /Sin límite monetario/);
  assert.match(html, /Coste no disponible/);
});
test("diff conserva literalmente cabeceras y rutas con espacios", () => {
  const texto = 'diff --git a/my file.py b/my file.py\n--- a/my file.py\n+++ b/my file.py\n@@ -1 +1 @@\n-old\n+new\n';
  const html = renderToStaticMarkup(React.createElement(VisorDiff, { texto }));
  assert.match(html, /diff --git a\/my file\.py b\/my file\.py/);
  assert.match(html, /\+\+\+ b\/my file\.py/);
});
test("una prueba fallida vigente no queda verde porque otra pasa", () => {
  const e = etapas(estado({ evidence: { findings: [], test_runs: [
    { target:'unit', exit_code:0 }, { target:'lint', exit_code:1 },
  ] } }));
  assert.equal(e["Pruebas"].clase, "fallida");
});
test("una repeticion exitosa sustituye el fallo anterior del mismo target", () => {
  const e = etapas(estado({ evidence: { findings: [], test_runs: [
    { target:'unit', exit_code:1 }, { target:'unit', exit_code:0 },
  ] } }));
  assert.equal(e["Pruebas"].clase, "hecha");
});

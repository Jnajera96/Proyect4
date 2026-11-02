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
const { VistaSeguridad } = await cargar("../src/views/VistaSeguridad.tsx");
const { api } = await cargar("../src/lib/api.ts");
const { VisorDiff } = await cargar("../src/components/VisorDiff.tsx");
const { calcular } = await cargar("../src/components/DiagramaFlujo.tsx");
const { actividadesPendientes, ActividadPipeline } = await cargar("../src/components/ActividadPipeline.tsx");
const { PuertaRequisitos } = await cargar("../src/components/PuertaRequisitos.tsx");
const { mensajeEstado } = await cargar("../src/lib/contracts.ts");

test("mensajes humanos distinguen actividad de una promoción realmente completada", () => {
  for (const [step, message] of Object.entries({researcher:"Analizando", coder:"Escribiendo", run_tests:"Verificando", reviewer:"Revisando"})) {
    assert.match(mensajeEstado(estado({status:"running",next_step:step})),new RegExp(message));
  }
  assert.doesNotMatch(mensajeEstado(estado({status:"completed"})),/Aplicación construida/);
  assert.match(mensajeEstado(estado({status:"completed",promotion_receipt:{status:"promoted"}})),/Aplicación construida/);
});

test("flujo presenta las dos puertas humanas directamente en pantalla", () => {
  const requirements=estado({status:"awaiting_human_requirements_confirmation",
    interpretation:{intent:"modify",confidence:.9,rationale:"Propuesta",constraints:[],scope:{repo_path:"C:/fixture",allowed_paths:[],protected_paths:[]}}});
  assert.match(renderToStaticMarkup(React.createElement(VistaFlujo,{estado:requirements})),/Confirmar y construir/);
  assert.match(renderToStaticMarkup(React.createElement(VistaFlujo,{estado:estado({status:"awaiting_approval"})})),/id="btn-aprobar"/);
});

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
const evento = (kind, seq, data = {}) => ({ kind, seq, at: "2026-10-28T12:00:00Z", data });

test("seguridad distingue fallos de verificación de errores del motor", () => {
  const html = renderToStaticMarkup(React.createElement(VistaSeguridad, {
    estado: estado({evidence: {test_runs: [{target:"pytest.unit",exit_code:2}],findings:[]}}),
    sesion: "autenticado", rol:"admin",
  }));
  assert.match(html,/objetivos de verificación reportaron fallos/);
  assert.doesNotMatch(html,/Sin errores registrados/);
  assert.match(html,/pytest.unit/);
});

test("seguridad usa la última ejecución del objetivo y no un fallo histórico", () => {
  const html = renderToStaticMarkup(React.createElement(VistaSeguridad, {
    estado: estado({evidence: {test_runs: [
      {target:"pytest.unit",exit_code:2},{target:"pytest.unit",exit_code:0},
    ],findings:[]}}), sesion:"autenticado", rol:"admin",
  }));
  assert.doesNotMatch(html,/objetivos de verificación reportaron fallos/);
  assert.match(html,/Sin errores registrados/);
});

test("inspect y PLAN_ONLY muestran No aplica para etapas que no ejecutaran", () => {
  for (const cambios of [{ interpretation: { intent: "inspect" } }, { options: { mode: "PLAN_ONLY" } }]) {
    const run = estado({ status: "completed", artifacts: { diff: "", changed_files: [] }, ...cambios });
    for (const e of calcular(run).filter(e => ["coder", "pruebas", "revisor", "aprobacion", "promocion"].includes(e.id))) {
      assert.equal(e.estado, "omitida", e.id);
      assert.match(e.detalle, /No aplica/);
    }
  }
});
test("bloqueo terminal y Coder vacio no se muestran como completados", () => {
  const run = estado({ status: "needs_human", artifacts: { diff: "", changed_files: [] },
    outputs: { coder_output: { diff: "", rationale: "fallback" }, researcher_output: null, reviewer_output: null } });
  const etapas = calcular(run);
  assert.equal(etapas.find(e => e.id === "coder").estado, "fallida");
  assert.equal(etapas.find(e => e.id === "pruebas").estado, "bloqueada");
});
test("evento de prueba mantiene etapa activa aunque ya exista evidencia de otro objetivo", () => {
  const run = estado({ evidence: { test_runs: [{ target: "pytest.unit", exit_code: 0 }] } });
  const eventos = [evento("test_target_started", 1, { node: "run_tests", target: "ruff.check" })];
  assert.equal(calcular(run, eventos).find(e => e.id === "pruebas").estado, "en-curso");
});
test("actividad empareja objetivos y llamadas reales, sin fingir exito", () => {
  const base = { node: "coder", role: "coder", mode: "remote", model: "Qwen/test", provider: "nscale" };
  const eventos = [evento("node_started", 1, base), evento("model_request_started", 2, base)];
  assert.equal(actividadesPendientes(eventos).length, 2);
  eventos.push(evento("model_response_received", 3, base), evento("node_completed", 4, base));
  assert.equal(actividadesPendientes(eventos).length, 0);
  eventos.push(evento("test_target_started", 5, { node: "run_tests", target: "pytest.unit" }));
  assert.equal(actividadesPendientes(eventos).length, 1);
  eventos.push(evento("test_target_completed", 6, { node: "run_tests", target: "pytest.unit", exit_code: 5, evidence: { stdout: "no tests ran", stderr: "literal stderr" } }));
  const html = renderToStaticMarkup(React.createElement(ActividadPipeline, { eventos, estado: estado() }));
  assert.match(html, /Código de salida: 5/);
  assert.match(html, /no tests ran/);
  assert.match(html, /literal stderr/);
  assert.match(html, /Qwen\/test/);
  assert.doesNotMatch(html, /PASS/);
  assert.equal(actividadesPendientes(eventos).length, 0);
});
test("texto escrito distingue captura literal de intencion heuristica y exige proyecto para modificar", () => {
  const run = estado({ status: "awaiting_human_requirements_confirmation", interpretation: {
    intent: "modify", confidence: 0.5, constraints: [], rationale: "reglas", scope: { repo_path: "(sin repositorio configurado)", allowed_paths: [], protected_paths: [] },
  } });
  const html = renderToStaticMarkup(React.createElement(PuertaRequisitos, { estado: run, alDecidir() {}, alFallo() {} }));
  assert.match(html, /Fidelidad de captura: <strong>100%/);
  assert.match(html, /no calibrada/);
  assert.match(html, /repositorio Git autorizado/);
  assert.match(html, /id="btn-confirmar-requisitos"[^>]*disabled/);
});
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
  assert.equal(e["Promoción al repositorio"].clase, "bloqueada");
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

const { ModelSelector, pricingForSelection } = await cargar("../src/components/ModelConfiguration.tsx");
test("selector distingue la evidencia E2E de candidatos y admite identificador personalizado", () => {
  const html = renderToStaticMarkup(React.createElement(ModelSelector, {
    name: "model_name", label: "Modelo Coder", value: "mi-organizacion/mi-modelo:proveedor", onChange() {},
  }));
  assert.match(html, /Validación E2E previa/);
  assert.match(html, /pendientes de prueba/);
  assert.match(html, /Otro modelo/);
  assert.match(html, /mi-organizacion\/mi-modelo:proveedor/);
  assert.match(html, /id="model_name-custom"/);
  assert.equal((html.match(/<option/g) || []).length, 12); // diez modelos, vacío y personalizado
});
test("selector reviewer conserva la herencia de Coder sin inventar un modelo", () => {
  const html = renderToStaticMarkup(React.createElement(ModelSelector, {
    name: "reviewer_model", label: "Modelo Reviewer", value: "", onChange() {},
  }));
  assert.match(html, /Usar el mismo modelo que Coder/);
  assert.match(html, /name="reviewer_model" value=""/);
});
test("tarifas del catálogo convierten millón a mil y conservan alias de respuesta y entradas propias", () => {
  const old = { model: "modelo-propio", input_per_1k: 2, output_per_1k: 3, currency: "USD" };
  const id = "Qwen/Qwen2.5-Coder-32B-Instruct:nscale";
  const prices = JSON.parse(pricingForSelection([id, id], JSON.stringify([old])));
  assert.equal(prices.length, 3);
  assert.deepEqual(prices.find(p => p.model === "modelo-propio"), old);
  for (const alias of [id, id.split(":")[0]]) {
    const price = prices.find(p => p.model === alias);
    assert.equal(price.input_per_1k, 0.00006);
    assert.equal(price.output_per_1k, 0.0002);
  }
  assert.throws(() => pricingForSelection(["modelo-no-catalogado"], ""), /propias tarifas/);
  assert.throws(() => pricingForSelection([id], "{}"), /lista JSON/);
});

const { delivery } = await cargar("../src/lib/delivery.ts");
const { PublicarGitHubModal } = await cargar("../src/components/PublicarGitHubModal.tsx");
const { GuiaEjecucion } = await cargar("../src/components/GuiaEjecucion.tsx");
test("publicación procesa progreso real dividido entre bloques UTF-8", async () => {
  const original = globalThis.fetch;
  const stages = [];
  globalThis.fetch = async (url, init) => {
    assert.match(url, /publish-github\?stream=true$/);
    assert.equal(JSON.parse(init.body).organization, "fixture-org");
    const bytes = new TextEncoder().encode([
      JSON.stringify({stage:"validating"}), JSON.stringify({stage:"creating"}),
      JSON.stringify({stage:"uploading"}),
      JSON.stringify({published:true,url:"https://github.com/fixture/app",note:"éxito"}),
    ].join("\n") + "\n");
    return new Response(new ReadableStream({start(controller) {
      for (let i=0;i<bytes.length;i+=3) controller.enqueue(bytes.slice(i,i+3));
      controller.close();
    }}), {headers:{"Content-Type":"application/x-ndjson"}});
  };
  try {
    const result = await delivery.publish("fixture", {repo_name:"app",pat_token:"offline",private:true,organization:"fixture-org"}, stage => stages.push(stage));
    assert.deepEqual(stages,["validating","creating","uploading"]);
    assert.equal(result.published,true);
  } finally { globalThis.fetch = original; }
});
test("publicación no presenta éxito si falla o se corta el stream", async () => {
  const original = globalThis.fetch;
  try {
    for (const body of ['{"stage":"creating"}\n{"error":"Nombre existente"}\n', '{"stage":"uploading"}\n']) {
      globalThis.fetch = async () => new Response(body,{headers:{"Content-Type":"application/x-ndjson"}});
      await assert.rejects(delivery.publish("fixture",{repo_name:"app",pat_token:"offline",private:true},()=>{}), /Nombre existente|sin confirmación/);
    }
  } finally { globalThis.fetch = original; }
});
test("modal pide PAT clásico y mantiene oculta la entrada de credenciales", () => {
  const html=renderToStaticMarkup(React.createElement(PublicarGitHubModal,{projectId:"fixture",alCerrar(){}}));
  assert.match(html,/PAT clásico/); assert.match(html,/type="password"/);
  assert.match(html,/Organización \(opcional\)/); assert.match(html,/scopes=repo/);
});
test("un borrador puede revisarse pero no publicarse antes de la promoción", () => {
  const html=renderToStaticMarkup(React.createElement(GuiaEjecucion,{estado:estado({status:"needs_human"}),projectId:"fixture",puedeOperar:true,alPedirCambios(){}}));
  assert.match(html,/aún no está aprobado ni verificado/);
  assert.match(html,/<button disabled="">🚀 Subir a GitHub<\/button>/);
});

test("selector muestra evidencia real por rol sin confundir JSON-mode con esquema nativo o E2E", () => {
  const html=renderToStaticMarkup(React.createElement(ModelSelector,{name:"model_name",label:"Modelo Coder",value:"deepseek-ai/DeepSeek-V3.2:deepinfra",onChange(){}}));
  assert.match(html,/Coder 1\/1/); assert.match(html,/Reviewer 1\/1/);
  assert.match(html,/modo JSON con validación local/);
  assert.match(html,/todavía falta construir/);
  assert.match(html,/aplicaciones E2E pendientes de prueba/);
  assert.doesNotMatch(html,/<option[^>]*disabled/);
});

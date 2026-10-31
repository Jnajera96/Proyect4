import { useState } from "react";
import catalog from "../lib/modelCatalog.json";

const CUSTOM = "__custom__";
const HF_ROUTER = "https://router.huggingface.co/v1";

export function pricingForSelection(ids: string[], previous: string): string {
  const entries = JSON.parse(previous.trim() || "[]");
  if (!Array.isArray(entries)) throw new Error("Las tarifas deben ser una lista JSON.");
  const prices = new Map(entries.map(entry => [String(entry.model).toLowerCase(), entry]));
  for (const id of new Set(ids.filter(Boolean))) {
    const model = catalog.models.find(item => item.id === id);
    if (!model) throw new Error("El modelo personalizado necesita sus propias tarifas declaradas.");
    for (const alias of [model.id, model.baseModel]) {
      prices.set(alias.toLowerCase(), {
        model: alias, input_per_1k: Number((model.inputPerMillion / 1000).toPrecision(12)),
        output_per_1k: Number((model.outputPerMillion / 1000).toPrecision(12)), currency: "USD",
      });
    }
  }
  return JSON.stringify([...prices.values()], null, 2);
}

export function ModelSelector({ name, label, value, onChange }: {
  name: string; label: string; value: string; onChange: (value: string) => void;
}) {
  const [custom, setCustom] = useState(Boolean(value) && !catalog.models.some(m => m.id === value));
  const selected = catalog.models.find(m => m.id === value);
  return <div className="profile-model-selector">
    <label htmlFor={`${name}-selector`}>{label}</label>
    <select id={`${name}-selector`} value={custom ? CUSTOM : value}
      onChange={event => {
        const next = event.target.value;
        setCustom(next === CUSTOM);
        onChange(next === CUSTOM ? "" : next);
      }}>
      <option value="">{name === "reviewer_model" ? "Usar el mismo modelo que Coder" : "Seleccionar modelo"}</option>
      <optgroup label="Validación E2E previa en este proyecto">
        {catalog.models.filter(m => m.projectValidated).map(m =>
          <option key={m.id} value={m.id}>{m.label} · {m.provider}</option>)}
      </optgroup>
      <optgroup label="Contratos comprobados · aplicaciones E2E pendientes de prueba">
        {catalog.models.filter(m => !m.projectValidated).map(m =>
          <option key={m.id} value={m.id}>{m.label} · {m.provider} · Coder {m.probe.coderPassed}/{m.probe.coderTotal} · Reviewer {m.probe.reviewerPassed}/{m.probe.reviewerTotal}</option>)}
      </optgroup>
      <option value={CUSTOM}>Otro modelo — escribir identificador HF</option>
    </select>
    <input type="hidden" name={name} value={value.trim()} />
    {custom && <label htmlFor={`${name}-custom`}>Identificador personalizado de {label}
      <input id={`${name}-custom`} value={value} required maxLength={120}
        placeholder="organización/modelo:proveedor"
        onChange={event => onChange(event.target.value)} />
    </label>}
    {selected && <p className="profile-model-note">
      {selected.purpose}. {selected.projectValidated
        ? "Funcionó en la validación E2E histórica y sus pruebas de contrato se actualizaron."
        : "Respondió en pruebas reales de contrato; todavía falta construir y verificar una aplicación completa con esta ruta."}
      <br />Pruebas del {selected.probe.checkedAt}: Coder {selected.probe.coderPassed}/{selected.probe.coderTotal}, Reviewer {selected.probe.reviewerPassed}/{selected.probe.reviewerTotal}. Una ejecución por caso; no es una garantía de calidad general.
      {!selected.supportsStructuredOutput && <><br />El proveedor no declara esquema nativo, pero respondió correctamente en las sondas de modo JSON con validación local.</>}
      {" "}<a href={selected.source} target="_blank" rel="noreferrer">Ficha en Hugging Face</a>
      <br />{selected.inputPerMillion} USD / millón de entrada · {selected.outputPerMillion} USD / millón de salida.
    </p>}
    {custom && <p className="profile-model-note">Debe estar servido por un proveedor compatible con el router HF.
      Escribir el nombre no despliega el modelo. Declara también sus tarifas.</p>}
  </div>;
}

export function ModelConfiguration({ coder = "", reviewer = "", pricing = "" }: {
  coder?: string; reviewer?: string; pricing?: string;
}) {
  const [coderModel, setCoderModel] = useState(coder);
  const [reviewerModel, setReviewerModel] = useState(reviewer);
  const [prices, setPrices] = useState(pricing);
  const [notice, setNotice] = useState("");
  return <>
    <ModelSelector name="model_name" label="Modelo Coder" value={coderModel} onChange={setCoderModel} />
    <ModelSelector name="reviewer_model" label="Modelo Reviewer" value={reviewerModel} onChange={setReviewerModel} />
    <p className="profile-model-note">Diez opciones por especialidad, sin clasificación universal de «mejores».
      Solo Qwen2.5 Coder 32B tiene una prueba E2E registrada en este proyecto.
      Catálogo y tarifas consultados el {catalog.checkedAt}; pueden cambiar.
      Elegir un modelo no activa llamadas ni comprueba tu token.</p>
    <button type="button" disabled={!coderModel} onClick={event => {
      try {
        const form = event.currentTarget.form;
        const endpoint = new FormData(form ?? undefined).get("model_base_url");
        if (String(endpoint).trim().replace(/\/$/, "") !== HF_ROUTER) {
          throw new Error("Estas tarifas corresponden al router HF; declara las de tu endpoint.");
        }
        setPrices(pricingForSelection([coderModel, reviewerModel || coderModel], prices));
        setNotice(`Tarifas publicadas el ${catalog.checkedAt} aplicadas. Revísalas antes de guardar.`);
      } catch (error) { setNotice((error as Error).message); }
    }}>Aplicar tarifas del catálogo a los modelos elegidos</button>
    {notice && <p role="status">{notice}</p>}
    <label>Tarifas declaradas en USD (JSON)<textarea name="model_pricing" rows={6}
      value={prices} onChange={event => setPrices(event.target.value)}
      placeholder={'[{"model":"organización/modelo:proveedor","input_per_1k":0.001,"output_per_1k":0.002,"currency":"USD"}]'} /></label>
    <p className="profile-model-note">Después marca coder/reviewer en «Activar llamadas remotas»,
      configura el presupuesto y guarda la bóveda. La disponibilidad pública no garantiza
      acceso con tu cuenta ni una respuesta válida al contrato de esta aplicación.</p>
  </>;
}

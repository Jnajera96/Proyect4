import { useEffect, useState, type FormEvent } from "react";
import { App } from "../App";
import { borrarClave } from "../lib/auth";
import { profileRequest, setProfileCsrf } from "../lib/profile";
import { ModelConfiguration } from "./ModelConfiguration";
import { PasswordField } from "./PasswordField";
import { RestaurarPerfil } from "./RestaurarPerfil";
import "../profiles.css";

type Status = { profile_mode: boolean; authenticated: boolean;
  user?: { id: string; name: string }; csrf_token?: string };
type Vault = { has_token: boolean; model_name?: string; reviewer_model?: string;
  model_base_url?: string; remote_model_roles?: string[]; model_pricing?: string;
  budget_limit?: number; max_cost_per_run?: number; max_cost_per_hour?: number | null;
  ledger: { limit: number | null; consumed: number; reserved: number; available: number | null } };

export function ProfileRoot() {
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState("");
  const [register, setRegister] = useState(false);
  const [restore, setRestore] = useState(false);
  const [recover, setRecover] = useState(false);
  const [recoverySetup, setRecoverySetup] = useState(false);
  const [recoveryCode, setRecoveryCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [vault, setVault] = useState<Vault | null>(null);
  const [notice, setNotice] = useState("");
  const [configurationRevision, setConfigurationRevision] = useState(0);
  const apply = (next: Status) => {
    setProfileCsrf(next.csrf_token ?? null);
    if (next.profile_mode) borrarClave();
    setStatus(next);
  };
  useEffect(() => {
    let current = true;
    profileRequest<Status>("/auth/status").then(s => { if (current) apply(s); })
      .catch(e => { if (current) setError(String(e.message)); });
    const expired = () => {
      setRecoveryCode(""); setRecoverySetup(false);
      setVault(null); setRegister(false);
      setStatus({ profile_mode: true, authenticated: false });
      setError("La sesión terminó. Vuelve a entrar a tu perfil.");
    };
    window.addEventListener("aiswe-profile-expired", expired);
    return () => { current = false; window.removeEventListener("aiswe-profile-expired", expired); };
  }, []);

  async function authenticate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    if ((register || recover) && fields.get("password") !== fields.get("password_confirmation")) {
      setError("Las contraseñas no coinciden."); return;
    }
    if (Array.from(String(fields.get("password") ?? "")).length < 12) {
      setError("La contraseña debe tener al menos 12 caracteres."); return;
    }
    setBusy(true); setError("");
    try {
      if (recover) {
        await profileRequest("/auth/recover", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: fields.get("name"), password: fields.get("password"),
            recovery_code: fields.get("recovery_code") }),
        });
        form.reset(); setRecover(false);
        setNotice("Contraseña actualizada. Entra con la nueva contraseña y genera otra clave de rescate.");
        return;
      }
      const next = await profileRequest<Status>(register ? "/auth/register" : "/auth/login", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: fields.get("name"), password: fields.get("password") }),
      });
      form.reset(); apply(next);
      if (register) setRecoverySetup(true);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  async function logout() {
    setBusy(true); setError("");
    try {
      await profileRequest("/auth/logout", { method: "POST" });
      setVault(null); setNotice(""); setRegister(false); setRecoveryCode(""); setRecoverySetup(false);
      apply({ profile_mode: true, authenticated: false });
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  async function generateRecovery(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const password = new FormData(form).get("password");
    setBusy(true); setError(""); setRecoveryCode("");
    try {
      const result = await profileRequest<{ recovery_code: string }>("/auth/recovery-key", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      form.reset(); setRecoveryCode(result.recovery_code);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  async function saveVault(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    setBusy(true); setError(""); setNotice("");
    try {
      await profileRequest("/auth/vault", { method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          hf_token: fields.get("clear_token") ? "" : (fields.get("hf_token") || null),
          model_name: fields.get("model_name"), reviewer_model: fields.get("reviewer_model"),
          model_provider: "openai_compatible", model_base_url: fields.get("model_base_url"),
          remote_model_roles: fields.getAll("roles"), model_pricing: fields.get("model_pricing"),
          budget_limit: Number(fields.get("budget_limit")),
          max_cost_per_run: Number(fields.get("max_cost_per_run")),
          max_cost_per_hour: fields.get("max_cost_per_hour") === "" ? null : Number(fields.get("max_cost_per_hour")),
        }),
      });
      form.reset(); setVault(null); setConfigurationRevision(n => n + 1);
      setNotice("Bóveda guardada. Configuración aplicada a tu perfil.");
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  if (!status) return <main className="profile-access"><h1>AI Software Engineering</h1>
    <p role={error ? "alert" : "status"}>{error || "Comprobando acceso…"}</p>
    {error && <button onClick={() => window.location.reload()}>Reintentar</button>}</main>;
  if (!status.profile_mode) return <App />;
  if (!status.authenticated && restore) return <RestaurarPerfil
    alVolver={() => setRestore(false)}
    alRestaurar={async () => {
      apply(await profileRequest<Status>("/auth/status")); setRestore(false);
      setNotice("Perfil restaurado. Revisa tu historial antes de reanudar. Genera una nueva clave de rescate.");
    }} />;
  if (!status.authenticated) return <main className="profile-access">
    <p className="profile-eyebrow">Tu espacio local</p>
    <h1>{recover ? "Recuperar acceso" : register ? "Crear perfil" : "Entrar a tu perfil"}</h1>
    <p>Proyectos, historial y credenciales separados para cada persona.</p>
    <form onSubmit={authenticate} onInvalid={event => {
      event.preventDefault();
      const input = event.target as HTMLInputElement;
      const labels: Record<string, string> = { name: "Nombre de perfil", password: "Contraseña",
        password_confirmation: "Repetir contraseña", recovery_code: "Clave de rescate" };
      setError(input.validity.valueMissing
        ? `${labels[input.name] ?? "Campo"}: completa este campo.`
        : `${labels[input.name] ?? "Campo"}: revisa la longitud (mínimo 12 caracteres para contraseñas).`);
    }}>
      <label>Nombre de perfil<input name="name" autoComplete="username" required maxLength={64} /></label>
      <p>Nombre: letras, números, espacios, guiones o guion bajo. No uses un correo electrónico ni puntos.</p>
      {recover && <PasswordField name="recovery_code" label="Clave de rescate" autoComplete="off" />}
      <PasswordField key={recover ? "recover" : register ? "register" : "login"} name="password"
        label={recover ? "Nueva contraseña" : "Contraseña"}
        autoComplete={register || recover ? "new-password" : "current-password"} />
      {(register || recover) && <PasswordField name="password_confirmation" label="Repetir contraseña" autoComplete="new-password" />}
      {register && <p>Usa al menos 12 caracteres. Después de entrar, genera tu clave de rescate y guárdala fuera de este equipo.</p>}
      {recover && <p>Necesitas la clave de rescate generada previamente. Sin contraseña ni clave,
        no se puede descifrar la bóveda. Una pregunta de seguridad no sustituye esa clave.</p>}
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      <button type="submit" disabled={busy}>{busy ? "Un momento…" : recover ? "Restablecer contraseña" : register ? "Crear perfil y entrar" : "Entrar"}</button>
      <button type="button" disabled={busy} onClick={() => { setRecover(false); setRegister(!register); setError(""); }}>
        {register ? "Ya tengo un perfil" : "Crear un perfil nuevo"}</button>
      <button type="button" disabled={busy} onClick={() => { setRecover(!recover); setRegister(false); setError(""); }}>
        {recover ? "Volver al inicio de sesión" : "Olvidé mi contraseña"}</button>
      <button type="button" disabled={busy} onClick={() => setRestore(true)}>Restaurar desde un respaldo</button>
    </form>
  </main>;
  return <>
    <header className="profile-bar" aria-label="Perfil activo">
      <strong>Perfil: {status.user?.name}</strong>
      <button onClick={() => { setError(""); profileRequest<Vault>("/auth/vault").then(setVault)
        .catch(e => setError(e.message)); }}>Configurar bóveda</button>
      <button onClick={logout} disabled={busy}>Cerrar sesión</button>
      <button onClick={() => { setRecoverySetup(true); setRecoveryCode(""); setError(""); }}>Recuperación de acceso</button>
    </header>
    {error && <p className="profile-message" role="alert">{error}</p>}
    {notice && <p className="profile-message" role="status">{notice}</p>}
    {recoverySetup && <section className="profile-vault" aria-label="Recuperación de acceso">
      <h2>Generar clave de rescate</h2>
      <p>Guárdala fuera de este equipo. Permite cambiar tu contraseña sin perder la bóveda;
        no reemplaza un respaldo de tus archivos. Generar otra invalida la anterior.</p>
      <form onSubmit={generateRecovery}>
        <PasswordField name="password" label="Contraseña actual" />
        <button type="submit" disabled={busy}>Generar clave de rescate</button>
      </form>
      {recoveryCode && <div role="status"><p>Se muestra solo ahora. No la compartas.</p>
        <label>Clave de rescate generada<input readOnly value={recoveryCode} autoComplete="off" /></label></div>}
      <button onClick={() => { setRecoverySetup(false); setRecoveryCode(""); }}>He guardado mi clave · cerrar</button>
    </section>}
    {vault ? <section className="profile-vault" aria-label="Configuración de bóveda">
      <h1>Proveedor y presupuesto de tu perfil</h1>
      <p>Token: {vault.has_token ? "guardado" : "sin configurar"}. Nunca se muestra el valor guardado.</p>
      <p>Consumo declarado: {vault.ledger.consumed} USD · Reservado: {vault.ledger.reserved} USD ·
        Disponible: {vault.ledger.available ?? "sin límite declarado"}</p>

      <div style={{ background: "rgba(255,255,255,0.05)", padding: "0.8rem", borderRadius: "8px", marginBottom: "1rem" }}>
        <strong>Configuración rápida por proveedor:</strong>
        <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem", flexWrap: "wrap" }}>
          <button type="button" onClick={() => {
            const form = document.querySelector(".profile-vault form") as HTMLFormElement | null;
            if (form) {
              const urlInput = form.querySelector('[name="model_base_url"]') as HTMLInputElement | null;
              if (urlInput) urlInput.value = "https://generativelanguage.googleapis.com/v1beta/openai";
              const budgetInput = form.querySelector('[name="budget_limit"]') as HTMLInputElement | null;
              if (budgetInput) budgetInput.value = "50";
              const runBudgetInput = form.querySelector('[name="max_cost_per_run"]') as HTMLInputElement | null;
              if (runBudgetInput) runBudgetInput.value = "10";
              const checkboxes = form.querySelectorAll<HTMLInputElement>('input[name="roles"]');
              checkboxes.forEach(cb => { cb.checked = true; });
              const pricingText = form.querySelector('[name="model_pricing"]') as HTMLTextAreaElement | null;
              if (pricingText) {
                pricingText.value = JSON.stringify([
                  { model: "gemini-1.5-flash", input_per_1k: 0.000075, output_per_1k: 0.0003, currency: "USD" },
                  { model: "gemini-2.0-flash", input_per_1k: 0.0001, output_per_1k: 0.0004, currency: "USD" }
                ], null, 2);
              }
              const coderSelect = form.querySelector('#model_name-selector') as HTMLSelectElement | null;
              if (coderSelect) { coderSelect.value = "gemini-1.5-flash"; coderSelect.dispatchEvent(new Event('change', { bubbles: true })); }
              const reviewerSelect = form.querySelector('#reviewer_model-selector') as HTMLSelectElement | null;
              if (reviewerSelect) { reviewerSelect.value = "gemini-1.5-flash"; reviewerSelect.dispatchEvent(new Event('change', { bubbles: true })); }
            }
            setNotice("Preset Google Gemini aplicado con gemini-1.5-flash y presupuesto holgado ($50 / $10 por ejecución). Pega tu clave de API y guarda la bóveda.");
          }}>✨ Usar Google Gemini (API Key)</button>
          <button type="button" onClick={() => {
            const form = document.querySelector(".profile-vault form") as HTMLFormElement | null;
            if (form) {
              const urlInput = form.querySelector('[name="model_base_url"]') as HTMLInputElement | null;
              if (urlInput) urlInput.value = "https://router.huggingface.co/v1";
              const budgetInput = form.querySelector('[name="budget_limit"]') as HTMLInputElement | null;
              if (budgetInput && (!budgetInput.value || Number(budgetInput.value) <= 0)) budgetInput.value = "5";
              const checkboxes = form.querySelectorAll<HTMLInputElement>('input[name="roles"]');
              checkboxes.forEach(cb => { cb.checked = true; });
              const pricingText = form.querySelector('[name="model_pricing"]') as HTMLTextAreaElement | null;
              if (pricingText) {
                pricingText.value = JSON.stringify([
                  { model: "Qwen/Qwen2.5-Coder-32B-Instruct:nscale", input_per_1k: 0.00006, output_per_1k: 0.0002, currency: "USD" }
                ], null, 2);
              }
              const coderSelect = form.querySelector('#model_name-selector') as HTMLSelectElement | null;
              if (coderSelect) { coderSelect.value = "Qwen/Qwen2.5-Coder-32B-Instruct:nscale"; coderSelect.dispatchEvent(new Event('change', { bubbles: true })); }
              const reviewerSelect = form.querySelector('#reviewer_model-selector') as HTMLSelectElement | null;
              if (reviewerSelect) { reviewerSelect.value = ""; reviewerSelect.dispatchEvent(new Event('change', { bubbles: true })); }
            }
            setNotice("Preset Hugging Face aplicado. Pega tu HF Token y guarda la bóveda.");
          }}>🤗 Usar Hugging Face (Router)</button>
        </div>
      </div>

      <form onSubmit={saveVault}>
        <label>Token HF / Clave de API Gemini<input name="hf_token" type="password" autoComplete="off" placeholder="Pega tu clave AIzaSy... o token HF (vacío conserva)" /></label>
        <label className="profile-check"><input type="checkbox" name="clear_token" />Eliminar el token guardado</label>
        <label>Endpoint HTTPS<input name="model_base_url" type="url" required
          defaultValue={vault.model_base_url ?? "https://generativelanguage.googleapis.com/v1beta/openai"} /></label>
        <ModelConfiguration coder={vault.model_name || "gemini-1.5-flash"} reviewer={vault.reviewer_model} pricing={vault.model_pricing} />
        <fieldset><legend>Activar llamadas remotas (IA)</legend>
          {[
            { id: "coder", label: "coder (Generación de código)" },
            { id: "reviewer", label: "reviewer (Revisión técnica)" },
            { id: "supervisor", label: "supervisor (Planificación de tareas)" },
            { id: "requirements_analyst", label: "requirements_analyst (Interpretación de requisitos)" },
          ].map(r => <label className="profile-check" key={r.id}>
            <input type="checkbox" name="roles" value={r.id} defaultChecked={vault.remote_model_roles ? vault.remote_model_roles.includes(r.id) : true} />{r.label}</label>)}
        </fieldset>
        <label>Límite acumulado del perfil (USD)<input name="budget_limit" type="number" required
          min="0" step="any" defaultValue={vault.budget_limit && vault.budget_limit > 0 ? vault.budget_limit : 50} /></label>
        <label>Máximo por ejecución (USD)<input name="max_cost_per_run" type="number" required
          min="0.000001" step="any" defaultValue={vault.max_cost_per_run ?? 10} /></label>
        <p>Las reservas son estimaciones locales, no cargos reales. Si falta el consumo del proveedor,
          el límite horario también conserva las reservas desconocidas. Para admitir una corrida,
          su máximo debe caber en el saldo horario disponible.</p>
        <label>Máximo por hora (USD, opcional)<input name="max_cost_per_hour" type="number"
          min="0" step="any" defaultValue={vault.max_cost_per_hour ?? ""} /></label>
        <p>Si falta el consumo del proveedor,
          se conserva la reserva. Este control no garantiza la factura de un tercero.</p>
        <button type="submit" disabled={busy}>{busy ? "Guardando…" : "Guardar bóveda"}</button>
        <button type="button" disabled={busy} onClick={() => setVault(null)}>Volver al espacio</button>
      </form>
    </section> : null}
    <div hidden={vault !== null}>
    <App key={status.user?.id} profile={{ name: status.user?.name ?? "", configurationRevision,
      onLogout: () => void logout(), onVault: () => {
        setError(""); profileRequest<Vault>("/auth/vault").then(setVault)
          .catch(e => setError(e.message));
      },
    }} />
    </div>
  </>;
}

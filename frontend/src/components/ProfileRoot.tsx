import { useEffect, useRef, useState, type FormEvent } from "react";
import { App } from "../App";
import { borrarClave } from "../lib/auth";
import { profileRequest, setProfileCsrf } from "../lib/profile";
import { isLocalEndpoint, ModelConfiguration } from "./ModelConfiguration";
import { PasswordField } from "./PasswordField";
import { RestaurarPerfil } from "./RestaurarPerfil";
import "../profiles.css";

type Status = { profile_mode: boolean; authenticated: boolean;
  user?: { id: string; name: string }; csrf_token?: string };
export type Vault = { has_token: boolean; model_name?: string; reviewer_model?: string;
  model_base_url?: string; remote_model_roles?: string[]; model_pricing?: string;
  budget_limit?: number; max_cost_per_run?: number; max_cost_per_hour?: number | null;
  ledger: { limit: number | null; consumed: number; reserved: number; available: number | null } };

export function ProfileVaultSection({
  vault,
  setVault,
  busy,
  onSave,
  onClose,
  setNotice,
}: {
  vault: Vault;
  setVault: React.Dispatch<React.SetStateAction<Vault | null>>;
  busy: boolean;
  onSave: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onClose: () => void;
  setNotice: (msg: string) => void;
}) {
  const [formRevision, setFormRevision] = useState(0);
  const formRef = useRef<HTMLFormElement>(null);
  const [tokenDraft, setTokenDraft] = useState("");
  const [clearTokenDraft, setClearTokenDraft] = useState(false);
  const [replacingToken, setReplacingToken] = useState(!vault.has_token);
  const [endpoint, setEndpoint] = useState(vault.model_base_url ?? "");
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [checking, setChecking] = useState(false);
  const [connectionMessage, setConnectionMessage] = useState("");
  const connectionVersion = useRef(0);
  const [resolvedModels, setResolvedModels] = useState<{ coder: string; reviewer: string }>();
  const local = isLocalEndpoint(endpoint);

  function applyPreset(preset: {
    model_base_url: string;
    model_name: string;
    reviewer_model: string;
    model_pricing: string;
    notice: string;
  }) {
    let currentBudget = vault.budget_limit;
    let currentRun = vault.max_cost_per_run;
    let currentHour = vault.max_cost_per_hour;
    let currentRoles = vault.remote_model_roles;
    let currentToken = tokenDraft;
    let currentClear = clearTokenDraft;

    if (formRef.current) {
      const fd = new FormData(formRef.current);
      const b = fd.get("budget_limit");
      if (b !== null && b !== "") currentBudget = Number(b);
      const r = fd.get("max_cost_per_run");
      if (r !== null && r !== "") currentRun = Number(r);
      const h = fd.get("max_cost_per_hour");
      if (h === "") currentHour = null;
      else if (h !== null) currentHour = Number(h);

      const roles = fd.getAll("roles").map(String);
      currentRoles = roles;

      const t = fd.get("hf_token");
      if (typeof t === "string") currentToken = t;
      currentClear = Boolean(fd.get("clear_token"));
    }

    const changedProvider = endpoint.replace(/\/$/, "") !== preset.model_base_url.replace(/\/$/, "");
    setTokenDraft(changedProvider ? "" : currentToken);
    setClearTokenDraft(changedProvider || currentClear);
    setReplacingToken(changedProvider || replacingToken);
    setEndpoint(preset.model_base_url);
    connectionVersion.current += 1;
    setResolvedModels(undefined);
    setAvailableModels([]);
    setConnectionMessage("");
    setVault(prev => prev ? {
      ...prev,
      budget_limit: currentBudget,
      max_cost_per_run: currentRun,
      max_cost_per_hour: currentHour,
      remote_model_roles: currentRoles,
      model_base_url: preset.model_base_url,
      model_name: preset.model_name,
      reviewer_model: preset.reviewer_model,
      model_pricing: preset.model_pricing,
    } : null);
    setFormRevision(r => r + 1);
    setNotice(preset.notice);
  }

  return (
    <section className="profile-vault" aria-label="Configuración de bóveda">
      <h1>Proveedor y presupuesto de tu perfil</h1>
      <p>La credencial guardada permanece oculta. Los cambios se aplican al guardar la bóveda.</p>
      <p>Consumo declarado: {vault.ledger.consumed} USD · Reservado: {vault.ledger.reserved} USD ·
        Disponible: {vault.ledger.available ?? "sin límite declarado"}</p>

      <div style={{ background: "rgba(255,255,255,0.05)", padding: "0.8rem", borderRadius: "8px", marginBottom: "1rem" }}>
        <strong>Configuración rápida por proveedor:</strong>
        <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem", flexWrap: "wrap" }}>
          <button type="button" onClick={() => applyPreset({
            model_base_url: "https://generativelanguage.googleapis.com/v1beta/openai",
            model_name: "gemini-3.8-flash",
            reviewer_model: "gemini-3.8-flash",
            model_pricing: JSON.stringify([
              { model: "gemini-3.8-flash", input_per_1k: 0.00075, output_per_1k: 0.00375, currency: "USD" },
              { model: "gemini-2.5-flash", input_per_1k: 0.00015, output_per_1k: 0.0006, currency: "USD" }
            ], null, 2),
            notice: "Preset Google Gemini aplicado con gemini-3.8-flash. Límites conservados. Pega tu clave de API Gemini y guarda la bóveda.",
          })}>✨ Usar Google Gemini (API Key)</button>
          <button type="button" onClick={() => applyPreset({
            model_base_url: "https://router.huggingface.co/v1",
            model_name: "Qwen/Qwen2.5-Coder-32B-Instruct:nscale",
            reviewer_model: "",
            model_pricing: JSON.stringify([
              { model: "Qwen/Qwen2.5-Coder-32B-Instruct:nscale", input_per_1k: 0.00006, output_per_1k: 0.0002, currency: "USD" }
            ], null, 2),
            notice: "Preset Hugging Face aplicado. Límites conservados. Pega tu HF Token y guarda la bóveda.",
          })}>🤗 Usar Hugging Face (Router)</button>
          <button type="button" onClick={() => applyPreset({
            model_base_url: "http://localhost:20128/v1",
            model_name: "omniroute-combo",
            reviewer_model: "",
            model_pricing: JSON.stringify([
              { model: "omniroute-combo", input_per_1k: 0.0, output_per_1k: 0.0, currency: "USD" },
              { model: "qwen2.5-coder", input_per_1k: 0.0, output_per_1k: 0.0, currency: "USD" },
              { model: "llama3.3-70b", input_per_1k: 0.0, output_per_1k: 0.0, currency: "USD" },
              { model: "gemini-3.8-flash", input_per_1k: 0.0, output_per_1k: 0.0, currency: "USD" },
              { model: "gemini/gemini-3.8-flash", input_per_1k: 0.0, output_per_1k: 0.0, currency: "USD" }
            ], null, 2),
            notice: "Preset OmniRoute / Local aplicado (coste cero, 0 USD). Límites conservados. Guarda la bóveda para confirmar.",
          })}>Usar OmniRoute local</button>
          <button type="button" onClick={() => applyPreset({
            model_base_url: "http://localhost:11434/v1",
            model_name: "",
            reviewer_model: "",
            model_pricing: "[]",
            notice: "Ollama seleccionado. Consulta los modelos instalados y elige uno antes de activar IA.",
          })}>Usar Ollama local</button>
          <button type="button" onClick={async () => {
            try {
              setNotice("Comprobando y lanzando OmniRoute...");
              const data = await profileRequest<{ status: string; message: string }>("/system/launch-omniroute", { method: "POST" });
              setNotice(data.message || "OmniRoute iniciado.");
            } catch (err) {
              setNotice("Error al invocar launcher: " + (err as Error).message);
            }
          }} style={{ background: "rgba(59, 130, 246, 0.2)", borderColor: "rgba(59, 130, 246, 0.5)" }}>⚡ Iniciar OmniRoute en PowerShell</button>
        </div>
      </div>

      <form ref={formRef} key={formRevision} onChange={() => { connectionVersion.current += 1; }}
        onSubmit={onSave}>
        <label>Endpoint del proveedor<input name="model_base_url" type="url" required
          value={endpoint} onChange={e => {
            setEndpoint(e.target.value); setTokenDraft(""); setClearTokenDraft(true);
            setReplacingToken(true); setAvailableModels([]); setConnectionMessage("");
          }} /></label>
        <p>{local ? "Sin credencial para este endpoint local." :
          clearTokenDraft && !tokenDraft ? "Sin token para esta configuración. Se eliminará el anterior al guardar." :
          !clearTokenDraft && vault.has_token ? "Token configurado (••••••••)." : "Sin token configurado."}</p>
        <input type="hidden" name="clear_token" value={clearTokenDraft && !tokenDraft ? "1" : ""} />
        {!local && <>
          <button type="button" onClick={() => setReplacingToken(true)}>Reemplazar token</button>
          <button type="button" onClick={() => {
            setTokenDraft(""); setClearTokenDraft(true); setReplacingToken(false);
            connectionVersion.current += 1;
          }}>Eliminar token</button>
        </>}
        {!local && replacingToken && <label>Clave del proveedor<input name="hf_token" type="password" autoComplete="off"
          value={tokenDraft} onChange={e => setTokenDraft(e.target.value)}
          placeholder="Ingresa la nueva credencial" /></label>}
        <ModelConfiguration coder={vault.model_name || ""} reviewer={vault.reviewer_model}
          pricing={vault.model_pricing} endpoint={endpoint} available={availableModels} resolved={resolvedModels} />
        <button type="button" disabled={checking || busy} onClick={async () => {
          if (!formRef.current) return;
          const fields = new FormData(formRef.current);
          const version = connectionVersion.current;
          setChecking(true); setConnectionMessage("Comprobando conexión y catálogo…");
          try {
            const result = await profileRequest<{ ok: boolean; message: string; models: string[];
              resolved_coder_model?: string | null; resolved_reviewer_model?: string | null }>(
              "/auth/vault/test-connection", { method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ model_base_url: endpoint,
                  model_name: fields.get("model_name"), reviewer_model: fields.get("reviewer_model"),
                  hf_token: local || (clearTokenDraft && !tokenDraft) ? "" : tokenDraft || null }) });
            if (version !== connectionVersion.current) {
              setConnectionMessage("La configuración cambió durante la prueba. Vuelve a comprobarla.");
              return;
            }
            setAvailableModels([...new Set([...result.models,
              ...[result.resolved_coder_model, result.resolved_reviewer_model]
                .filter((model): model is string => Boolean(model))])]);
            setConnectionMessage(result.message);
            if (result.models.length) {
              setResolvedModels({
                coder: result.resolved_coder_model || result.models[0],
                reviewer: result.resolved_reviewer_model || result.resolved_coder_model || result.models[0],
              });
            }
          } catch (err) { setConnectionMessage((err as Error).message); }
          finally { setChecking(false); }
        }}>{checking ? "Comprobando…" : "Probar conexión y consultar modelos"}</button>
        {connectionMessage && <p role="status">{connectionMessage}</p>}
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
          min="0" step="any" defaultValue={vault.budget_limit !== undefined && vault.budget_limit !== null ? vault.budget_limit : 50} /></label>
        <label>Máximo por ejecución (USD)<input name="max_cost_per_run" type="number" required
          min="0.000001" step="any" defaultValue={vault.max_cost_per_run !== undefined && vault.max_cost_per_run !== null ? vault.max_cost_per_run : 10} /></label>
        <p>Las reservas son estimaciones locales, no cargos reales. Si falta el consumo del proveedor,
          el límite horario también conserva las reservas desconocidas. Para admitir una corrida,
          su máximo debe caber en el saldo horario disponible.</p>
        <label>Máximo por hora (USD, opcional)<input name="max_cost_per_hour" type="number"
          min="0" step="any" defaultValue={vault.max_cost_per_hour !== undefined && vault.max_cost_per_hour !== null ? vault.max_cost_per_hour : ""} /></label>
        <p>Si falta el consumo del proveedor,
          se conserva la reserva. Este control no garantiza la factura de un tercero.</p>
        <button type="submit" disabled={busy}>{busy ? "Guardando…" : "Guardar bóveda"}</button>
        <button type="button" disabled={busy} onClick={onClose}>Volver al espacio</button>
      </form>
    </section>
  );
}

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
    {vault ? (
      <ProfileVaultSection
        vault={vault}
        setVault={setVault}
        busy={busy}
        onSave={saveVault}
        onClose={() => setVault(null)}
        setNotice={setNotice}
      />
    ) : null}
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

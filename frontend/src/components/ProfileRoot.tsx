import { useEffect, useState, type FormEvent } from "react";
import { App } from "../App";
import { borrarClave } from "../lib/auth";
import { profileRequest, setProfileCsrf } from "../lib/profile";
import "../profiles.css";

type Status = { profile_mode: boolean; authenticated: boolean;
  user?: { id: string; name: string }; csrf_token?: string };
type Vault = { has_token: boolean; model_name?: string; reviewer_model?: string;
  model_base_url?: string; remote_model_roles?: string[]; model_pricing?: string;
  budget_limit?: number; max_cost_per_run?: number;
  ledger: { limit: number | null; consumed: number; reserved: number; available: number | null } };

export function ProfileRoot() {
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState("");
  const [register, setRegister] = useState(false);
  const [busy, setBusy] = useState(false);
  const [vault, setVault] = useState<Vault | null>(null);
  const [notice, setNotice] = useState("");
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
    setBusy(true); setError("");
    try {
      const next = await profileRequest<Status>(register ? "/auth/register" : "/auth/login", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: fields.get("name"), password: fields.get("password") }),
      });
      form.reset(); apply(next);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  async function logout() {
    setBusy(true); setError("");
    try {
      await profileRequest("/auth/logout", { method: "POST" });
      setVault(null); setNotice(""); setRegister(false);
      apply({ profile_mode: true, authenticated: false });
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
        }),
      });
      form.reset(); setVault(null); setNotice("Bóveda guardada. Configuración aplicada a tu perfil.");
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  if (!status) return <main className="profile-access"><h1>AI Software Engineering</h1>
    <p role={error ? "alert" : "status"}>{error || "Comprobando acceso…"}</p>
    {error && <button onClick={() => window.location.reload()}>Reintentar</button>}</main>;
  if (!status.profile_mode) return <App />;
  if (!status.authenticated) return <main className="profile-access">
    <p className="profile-eyebrow">Tu espacio local</p>
    <h1>{register ? "Crear perfil" : "Entrar a tu perfil"}</h1>
    <p>Proyectos, historial y credenciales separados para cada persona.</p>
    <form onSubmit={authenticate}>
      <label>Nombre de perfil<input name="name" autoComplete="username" required maxLength={64} /></label>
      <label>Contraseña<input name="password" type="password" required minLength={12} maxLength={1024}
        autoComplete={register ? "new-password" : "current-password"} /></label>
      {register && <p>Usa al menos 12 caracteres. Sin esta contraseña no se puede recuperar la bóveda.</p>}
      {error && <p role="alert">{error}</p>}
      <button type="submit" disabled={busy}>{busy ? "Un momento…" : register ? "Crear perfil y entrar" : "Entrar"}</button>
      <button type="button" disabled={busy} onClick={() => { setRegister(!register); setError(""); }}>
        {register ? "Ya tengo un perfil" : "Crear un perfil nuevo"}</button>
    </form>
  </main>;
  return <>
    <header className="profile-bar" aria-label="Perfil activo">
      <strong>Perfil: {status.user?.name}</strong>
      <button onClick={() => { setError(""); profileRequest<Vault>("/auth/vault").then(setVault)
        .catch(e => setError(e.message)); }}>Configurar bóveda</button>
      <button onClick={logout} disabled={busy}>Cerrar sesión</button>
    </header>
    {error && <p className="profile-message" role="alert">{error}</p>}
    {notice && <p className="profile-message" role="status">{notice}</p>}
    {vault ? <section className="profile-vault" aria-label="Configuración de bóveda">
      <h1>Proveedor y presupuesto de tu perfil</h1>
      <p>Token: {vault.has_token ? "guardado" : "sin configurar"}. Nunca se muestra el valor guardado.</p>
      <p>Consumo declarado: {vault.ledger.consumed} USD · Reservado: {vault.ledger.reserved} USD ·
        Disponible: {vault.ledger.available ?? "sin límite declarado"}</p>
      <form onSubmit={saveVault}>
        <label>Token HF / API<input name="hf_token" type="password" autoComplete="off" placeholder="Vacío conserva el token" /></label>
        <label className="profile-check"><input type="checkbox" name="clear_token" />Eliminar el token guardado</label>
        <label>Endpoint HTTPS<input name="model_base_url" type="url" required
          defaultValue={vault.model_base_url ?? "https://router.huggingface.co/v1"} /></label>
        <label>Modelo Coder<input name="model_name" defaultValue={vault.model_name ?? ""} /></label>
        <label>Modelo Reviewer (vacío usa Coder)<input name="reviewer_model" defaultValue={vault.reviewer_model ?? ""} /></label>
        <fieldset><legend>Activar llamadas remotas</legend>
          {["coder", "reviewer"].map(role => <label className="profile-check" key={role}>
            <input type="checkbox" name="roles" value={role} defaultChecked={vault.remote_model_roles?.includes(role)} />{role}</label>)}
        </fieldset>
        <label>Tarifas declaradas en USD (JSON)<textarea name="model_pricing" rows={4}
          defaultValue={vault.model_pricing ?? ""}
          placeholder={'[{"model":"modelo","input_per_1k":0,"output_per_1k":0,"currency":"USD"}]'} /></label>
        <label>Límite acumulado del perfil (USD)<input name="budget_limit" type="number" required
          min="0" step="any" defaultValue={vault.budget_limit ?? 0} /></label>
        <label>Máximo por ejecución (USD)<input name="max_cost_per_run" type="number" required
          min="0.000001" step="any" defaultValue={vault.max_cost_per_run ?? 1} /></label>
        <p>Las reservas son estimaciones locales, no cargos reales. Si falta el consumo del proveedor,
          se conserva la reserva. Este control no garantiza la factura de un tercero.</p>
        <button type="submit" disabled={busy}>{busy ? "Guardando…" : "Guardar bóveda"}</button>
        <button type="button" disabled={busy} onClick={() => setVault(null)}>Volver al espacio</button>
      </form>
    </section> : <App key={status.user?.id} profile={{ name: status.user?.name ?? "",
      onLogout: () => void logout(), onVault: () => {
        setError(""); profileRequest<Vault>("/auth/vault").then(setVault)
          .catch(e => setError(e.message));
      },
    }} />}
  </>;
}

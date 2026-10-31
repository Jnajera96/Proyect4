import { useState, type FormEvent } from "react";
import { profileRequest } from "../lib/profile";
import { PasswordField } from "./PasswordField";

export function RestaurarPerfil({ alRestaurar, alVolver }: {
  alRestaurar: () => Promise<void>; alVolver: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState<{ archive_b64: string; repositories: string[] } | null>(null);
  async function inspect(form: HTMLFormElement) {
    const data = new FormData(form);
    const file = data.get("archive") as File;
    if (!file?.size || file.size > 512 * 1024 * 1024) {
      setError("Selecciona un respaldo no vacío de hasta 512 MiB."); return;
    }
    setBusy(true); setError(""); setPreview(null);
    try {
      const bytes = new Uint8Array(await file.arrayBuffer());
      const chunks: string[] = [];
      for (let i = 0; i < bytes.length; i += 8192) {
        chunks.push(String.fromCharCode(...bytes.subarray(i, i + 8192)));
      }
      const archive_b64 = btoa(chunks.join(""));
      const result = await profileRequest<{ repositories: string[] }>("/auth/inspect-vault", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ archive_b64, password: data.get("archive_password") }),
      });
      setPreview({ archive_b64, repositories: result.repositories });
    } catch (cause) { setError((cause as Error).message); }
    finally { setBusy(false); }
  }
  async function restore(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    if (data.get("new_password") !== data.get("confirmation")) {
      setError("Las contraseñas nuevas no coinciden."); return;
    }
    if (!preview) { setError("Primero lee el respaldo y autoriza sus carpetas."); return; }
    setBusy(true); setError("");
    try {
      await profileRequest("/auth/import-vault", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ archive_b64: preview.archive_b64,
          password: data.get("archive_password"), name: data.get("name"),
          new_password: data.get("new_password"),
          repo_mapping: Object.fromEntries(preview.repositories.map((repo, index) =>
            [repo, String(data.get(`repository-${index}`) ?? "").trim()])) }),
      });
      form.reset();
      await alRestaurar();
    } catch (cause) { setError((cause as Error).message); }
    finally { setBusy(false); }
  }
  return <main className="profile-access">
    <h1>Restaurar desde un respaldo</h1>
    <p>Recupera tu perfil sin crear uno vacío antes. Se creará un perfil nuevo;
      no se reemplazará uno existente ni se reanudarán tareas automáticamente.</p>
    <form onSubmit={restore}>
      <fieldset disabled={busy}>
        <legend>Datos de recuperación</legend>
        <label>Archivo de respaldo<input name="archive" type="file" accept=".aiswe-vault" required onChange={() => setPreview(null)} /></label>
        <div onChange={() => setPreview(null)}><PasswordField name="archive_password" label="Contraseña del respaldo" minLength={8} autoComplete="off" /></div>
        <button type="button" onClick={event => void inspect(event.currentTarget.form!)}>
          {busy ? "Leyendo…" : "Leer respaldo"}</button>
        {preview && <section aria-label="Repositorios del respaldo">
          <h2>Elige dónde recuperar tus proyectos</h2>
          {preview.repositories.length === 0 && <p>Este respaldo no contiene repositorios.</p>}
          {preview.repositories.map((repo, index) => <label key={repo}>
            Carpeta autorizada del repositorio {index + 1}<span className="mono">{repo}</span>
            <input name={`repository-${index}`} aria-label={`Carpeta autorizada del repositorio ${index + 1}`} required />
          </label>)}
          <p>Elige una ruta absoluta distinta para cada proyecto: carpeta nueva vacía
            o repositorio compatible sin cambios. No uses carpetas personales con archivos.</p>
        </section>}
        <label>Nombre del perfil recuperado<input name="name" required maxLength={64} autoComplete="username" /></label>
        <PasswordField name="new_password" label="Nueva contraseña del perfil" autoComplete="new-password" />
        <PasswordField name="confirmation" label="Repetir nueva contraseña" autoComplete="new-password" />
        <button type="submit" disabled={!preview}>{busy ? "Restaurando…" : "Restaurar perfil y entrar"}</button>
      </fieldset>
      {error && <p role="alert">{error}</p>}
      <button type="button" disabled={busy} onClick={alVolver}>Volver al inicio de sesión</button>
    </form>
  </main>;
}

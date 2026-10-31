import { useState, type FormEvent } from "react";
import { profileRequest } from "../lib/profile";
import { PasswordField } from "./PasswordField";

export function RestaurarPerfil({ alRestaurar, alVolver }: {
  alRestaurar: () => Promise<void>; alVolver: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function restore(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    if (data.get("new_password") !== data.get("confirmation")) {
      setError("Las contraseñas nuevas no coinciden."); return;
    }
    const file = data.get("archive") as File;
    if (!file?.size || file.size > 512 * 1024 * 1024) {
      setError("Selecciona un respaldo no vacío de hasta 512 MiB."); return;
    }
    setBusy(true); setError("");
    try {
      const bytes = new Uint8Array(await file.arrayBuffer());
      const chunks: string[] = [];
      for (let i = 0; i < bytes.length; i += 8192) {
        chunks.push(String.fromCharCode(...bytes.subarray(i, i + 8192)));
      }
      await profileRequest("/auth/import-vault", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ archive_b64: btoa(chunks.join("")),
          password: data.get("archive_password"), name: data.get("name"),
          new_password: data.get("new_password"),
          repo_mapping: { "*": String(data.get("repository") ?? "").trim() } }),
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
        <label>Archivo de respaldo<input name="archive" type="file" accept=".aiswe-vault" required /></label>
        <PasswordField name="archive_password" label="Contraseña del respaldo" minLength={8} autoComplete="off" />
        <label>Nombre del perfil recuperado<input name="name" required maxLength={64} autoComplete="username" /></label>
        <PasswordField name="new_password" label="Nueva contraseña del perfil" autoComplete="new-password" />
        <PasswordField name="confirmation" label="Repetir nueva contraseña" autoComplete="new-password" />
        <label>Carpeta autorizada del repositorio<input name="repository" required /></label>
        <p>Para respaldos de un solo repositorio, elige una carpeta nueva vacía
          o un repositorio compatible y sin cambios. No uses carpetas personales con archivos.</p>
        <button type="submit">{busy ? "Restaurando…" : "Restaurar perfil y entrar"}</button>
      </fieldset>
      {error && <p role="alert">{error}</p>}
      <button type="button" disabled={busy} onClick={alVolver}>Volver al inicio de sesión</button>
    </form>
  </main>;
}

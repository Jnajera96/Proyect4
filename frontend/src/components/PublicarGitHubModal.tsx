import { useEffect, useRef, useState, type FormEvent } from "react";
import { delivery } from "../lib/delivery";

export function PublicarGitHubModal({ projectId, alCerrar }: { projectId: string; alCerrar: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [token, setToken] = useState("");
  const [name, setName] = useState("");
  const [privado, setPrivado] = useState(true);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [url, setUrl] = useState("");
  useEffect(() => {
    const previous = document.activeElement;
    dialog.current?.showModal();
    return () => { dialog.current?.close(); if (previous instanceof HTMLElement) previous.focus(); };
  }, []);
  function close() { if (!busy) { setToken(""); alCerrar(); } }
  async function publish(event: FormEvent) {
    event.preventDefault();
    if (!confirmed || busy) return;
    setBusy(true); setError("");
    try {
      const result = await delivery.publish(projectId, { repo_name: name, pat_token: token, private: privado });
      if (!result.published || !/^https:\/\/github\.com\/[A-Za-z0-9-]+\/[A-Za-z0-9_.-]+$/.test(result.url)) {
        throw new Error("La publicación no devolvió una confirmación válida.");
      }
      setUrl(result.url);
    } catch (cause) { setError((cause as Error).message); }
    finally { setToken(""); setBusy(false); }
  }
  return <dialog ref={dialog} className="inspector-etapa" aria-labelledby="publicar-titulo"
    onCancel={event => { event.preventDefault(); close(); }}>
    <header className="inspector-cabecera"><h2 id="publicar-titulo">Publicar en GitHub</h2>
      <button disabled={busy} onClick={close}>Cerrar</button></header>
    <p>GitHub permite guardar y compartir el código de tu aplicación. Esto guarda una copia en tu cuenta;
      no convierte automáticamente tu programa en un sitio público.</p>
    <p>Solo se envían archivos revisados y README. El token y el iniciador específico de tu equipo no se envían.</p>
    {url ? <p role="status">Tu código está guardado en <a href={url} target="_blank" rel="noopener noreferrer">Ver proyecto en GitHub</a>.</p> :
      <form onSubmit={publish} className="stack">
        <label>Nombre en GitHub<input required pattern="[A-Za-z0-9][A-Za-z0-9_.-]{0,99}" value={name}
          onChange={event => setName(event.target.value)} autoComplete="off" /></label>
        <p>Crea un token para tu cuenta con permisos de administración y contenido de repositorios,
          lectura y escritura, que permita crear el repositorio. Dale una fecha de vencimiento corta.</p>
        <a href="https://github.com/settings/personal-access-tokens/new?name=AI%20SWE&contents=write&administration=write"
          target="_blank" rel="noopener noreferrer">Crear token en GitHub</a>
        <label>Token de GitHub (PAT)<input type="password" required value={token}
          onChange={event => setToken(event.target.value)} autoComplete="off" /></label>
        <p>No se guarda en archivos. El formulario se vacía al terminar. No pegues tu token de Hugging Face aquí.</p>
        <label><input type="checkbox" checked={privado} onChange={event => setPrivado(event.target.checked)} />Repositorio privado</label>
        <label><input type="checkbox" required checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />
          Revisé los archivos y quiero enviarlos a mi cuenta de GitHub.</label>
        {error && <p role="alert">{error}</p>}
        <button className="primario" disabled={busy || !confirmed}>{busy ? "Publicando…" : "🚀 Publicar en GitHub ahora"}</button>
      </form>}
  </dialog>;
}

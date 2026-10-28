/**
 * Sesion: la credencial de esta pestana, portabilidad .aiswe-vault y lo que el servidor declara.
 */
import { useEffect, useState } from "react";
import type { EstadoConexion } from "../hooks/useEventosRun";
import { api, mensajeVisible } from "../lib/api";
import type { EstadoSesion } from "../lib/auth";
import type { Health } from "../lib/contracts";
import { numero } from "../lib/formato";
import { Chip, Fila, Panel, Seccion } from "../components/ui";

export function VistaSesion({
  sesion,
  profileName,
  rol,
  credencial,
  conexion,
  salud,
  saludError,
  alCambiarCredencial,
  alCerrarSesion,
}: {
  sesion: EstadoSesion;
  profileName?: string;
  rol: string | null;
  /** Credencial enmascarada, o `null` si no hay ninguna. */
  credencial: string | null;
  conexion: EstadoConexion;
  salud: Health | null;
  saludError: boolean;
  alCambiarCredencial: () => void;
  alCerrarSesion: () => void;
}) {
  const [backupDir, setBackupDir] = useState("");
  const [backupStatus, setBackupStatus] = useState<{
    enabled: boolean;
    backup_dir: string | null;
    deferred: boolean;
    last_backup_path: string | null;
    last_backup_at: string | null;
    status: string;
    error: string | null;
  } | null>(null);
  const [exportPass, setExportPass] = useState("");
  const [importPass, setImportPass] = useState("");
  const [importRepoPath, setImportRepoPath] = useState("");
  const [importArchiveB64, setImportArchiveB64] = useState("");
  const [importFileName, setImportFileName] = useState("");
  const [mensajePortabilidad, setMensajePortabilidad] = useState<string | null>(null);
  const [errorPortabilidad, setErrorPortabilidad] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    void api
      .estadoContinuidad()
      .then((st) => {
        setBackupStatus(st);
        if (st.backup_dir) setBackupDir(st.backup_dir);
      })
      .catch(() => {});
  }, []);

  async function guardarAutoRespaldo(enabled: boolean) {
    setOcupado(true);
    setErrorPortabilidad(null);
    setMensajePortabilidad(null);
    try {
      const st = await api.configurarRespaldo(enabled ? backupDir.trim() : null, enabled);
      setBackupStatus(st);
      setMensajePortabilidad(
        enabled
          ? `Auto-respaldo activado en ${st.backup_dir ?? backupDir}`
          : "Auto-respaldo desactivado",
      );
    } catch (e) {
      setErrorPortabilidad(mensajeVisible(e, true));
    } finally {
      setOcupado(false);
    }
  }

  async function exportarArchivo() {
    if (!exportPass) return;
    setOcupado(true);
    setErrorPortabilidad(null);
    setMensajePortabilidad(null);
    try {
      const res = await api.exportarBoveda(exportPass);
      const bin = atob(res.archive_b64.replace(/-/g, "+").replace(/_/g, "/"));
      const bytes = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i += 1) bytes[i] = bin.charCodeAt(i);
      const blob = new Blob([bytes], { type: "application/octet-stream" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = res.filename || "sesion.aiswe-vault";
      a.click();
      URL.revokeObjectURL(url);
      setMensajePortabilidad(`Respaldo cifrado exportado (${res.filename}, ${numero(res.size)} bytes).`);
      setExportPass("");
    } catch (e) {
      setErrorPortabilidad(mensajeVisible(e, true));
    } finally {
      setOcupado(false);
    }
  }

  async function leerArchivoVault(file: File | null) {
    if (!file) return;
    const buffer = await file.arrayBuffer();
    const bytes = new Uint8Array(buffer);
    let binary = "";
    for (let i = 0; i < bytes.length; i += 1) binary += String.fromCharCode(bytes[i]);
    const b64 = btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
    setImportArchiveB64(b64);
    setImportFileName(file.name);
  }

  async function importarArchivo() {
    if (!importArchiveB64 || !importPass || !importRepoPath.trim()) return;
    setOcupado(true);
    setErrorPortabilidad(null);
    setMensajePortabilidad(null);
    try {
      const res = await api.importarBoveda(importArchiveB64, importPass, {
        "*": importRepoPath.trim(),
      });
      setMensajePortabilidad(
        `Sesión restaurada: ${res.restored_runs.length} ejecución(es) recuperadas sin reejecutar nodos completados.`,
      );
      setImportPass("");
    } catch (e) {
      setErrorPortabilidad(mensajeVisible(e, true));
    } finally {
      setOcupado(false);
    }
  }

  const panelPortabilidad = (
    <Seccion
      titulo="Portabilidad y recuperación (.aiswe-vault)"
      nota="Exporta e importa checkpoints LangGraph, memoria FTS5, worktrees y presupuesto con cifrado Scrypt + AES-256-GCM."
    >
      <Panel>
        {mensajePortabilidad ? (
          <p className="banner ok" role="status">
            {mensajePortabilidad}
          </p>
        ) : null}
        {errorPortabilidad ? (
          <p className="banner error" role="alert">
            {errorPortabilidad}
          </p>
        ) : null}
        <div className="rejilla rejilla-doble">
          <div className="stack">
            <h3 className="panel-titulo">Exportar respaldo cifrado</h3>
            <p className="tenue">
              Empaqueta la base SQLite (con copia consistente), objetos Git base y el inventario de worktrees.
            </p>
            <label htmlFor="vault-export-pass">Contraseña de cifrado (mín. 8 caracteres)</label>
            <input
              id="vault-export-pass"
              type="password"
              value={exportPass}
              onChange={(e) => setExportPass(e.target.value)}
              placeholder="Contraseña del archivo .aiswe-vault"
            />
            <Fila>
              <button
                id="btn-exportar-vault"
                className="primario"
                disabled={ocupado || exportPass.length < 8}
                onClick={() => void exportarArchivo()}
              >
                Exportar .aiswe-vault
              </button>
            </Fila>
          </div>

          <div className="stack">
            <h3 className="panel-titulo">Restaurar desde .aiswe-vault</h3>
            <p className="tenue">
              Revincula rutas de repositorio y reconstruye worktrees conservando puertas de aprobación pendientes.
            </p>
            <label htmlFor="vault-import-file">Archivo .aiswe-vault</label>
            <input
              id="vault-import-file"
              type="file"
              accept=".aiswe-vault,application/json,application/octet-stream"
              onChange={(e) => void leerArchivoVault(e.target.files?.[0] ?? null)}
            />
            {importFileName ? <p className="tenue mono">{importFileName}</p> : null}
            <label htmlFor="vault-import-repo">Ruta local autorizada para el repositorio</label>
            <input
              id="vault-import-repo"
              type="text"
              value={importRepoPath}
              onChange={(e) => setImportRepoPath(e.target.value)}
              placeholder="C:\ruta\autorizada\repositorio"
            />
            <label htmlFor="vault-import-pass">Contraseña del respaldo</label>
            <input
              id="vault-import-pass"
              type="password"
              value={importPass}
              onChange={(e) => setImportPass(e.target.value)}
              placeholder="Contraseña con la que se cifró"
            />
            <Fila>
              <button
                id="btn-importar-vault"
                disabled={ocupado || !importArchiveB64 || importPass.length < 8 || !importRepoPath.trim()}
                onClick={() => void importarArchivo()}
              >
                Restaurar sesión
              </button>
            </Fila>
          </div>
        </div>

        <div className="plegable" style={{ marginTop: "1.25rem" }}>
          <h3 className="panel-titulo">Carpeta de auto-respaldo</h3>
          <p className="tenue">
            Estado actual: <span className="mono">{backupStatus?.status ?? "not_configured"}</span>
            {backupStatus?.last_backup_path ? ` · Última copia: ${backupStatus.last_backup_path}` : ""}
          </p>
          <div className="rejilla rejilla-doble" style={{ alignItems: "end" }}>
            <div>
              <label htmlFor="vault-backup-dir">Carpeta local o sincronizada</label>
              <input
                id="vault-backup-dir"
                type="text"
                value={backupDir}
                onChange={(e) => setBackupDir(e.target.value)}
                placeholder="C:\Users\...\Backups\AISWE"
              />
            </div>
            <Fila>
              <button
                id="btn-activar-respaldo"
                disabled={ocupado || !backupDir.trim()}
                onClick={() => void guardarAutoRespaldo(true)}
              >
                Activar auto-respaldo
              </button>
              {backupStatus?.enabled ? (
                <button disabled={ocupado} onClick={() => void guardarAutoRespaldo(false)}>
                  Desactivar
                </button>
              ) : null}
            </Fila>
          </div>
        </div>
      </Panel>
    </Seccion>
  );

  if (profileName) {
    return (
      <>
        <Seccion titulo="Sesión del perfil">
          <Panel nota="La sesión caduca y se revoca al cerrar sesión. Los trabajos ya aceptados terminan antes de cerrar su contexto.">
            <dl className="datos">
              <dt>perfil</dt>
              <dd>{profileName}</dd>
              <dt>permisos</dt>
              <dd>Administrador de su propio espacio</dd>
              <dt>acceso</dt>
              <dd>Cookie de sesión protegida; las escrituras requieren CSRF.</dd>
            </dl>
            <Fila sep>
              <button onClick={alCambiarCredencial}>Configurar bóveda</button>
              <button onClick={alCerrarSesion}>Cerrar sesión</button>
            </Fila>
          </Panel>
        </Seccion>
        {panelPortabilidad}
      </>
    );
  }
  const autenticado = sesion === "autenticado";

  return (
    <>
      <Seccion titulo="Credencial de esta pestaña">
        <Panel nota="La credencial vive en memoria: no se guarda en el navegador y al recargar la página se pide otra vez.">
          {autenticado && credencial ? (
            <>
              <dl className="datos">
                <dt>credencial</dt>
                <dd>
                  <span className="mono" title="Credencial enmascarada">
                    {credencial}
                  </span>{" "}
                  <span className="tenue">(solo se muestran los dos últimos caracteres)</span>
                </dd>
                <dt>rol</dt>
                <dd>
                  {rol ? (
                    <>
                      {rol}{" "}
                      <span className="tenue">
                        · deducido de un rechazo real, no declarado por la API
                      </span>
                    </>
                  ) : (
                    <span className="tenue">
                      no conocido: la API no expone el rol de la credencial y todavía
                      ninguna acción ha sido rechazada
                    </span>
                  )}
                </dd>
                <dt>almacenamiento</dt>
                <dd>en memoria, solo en esta pestaña</dd>
              </dl>
              <Fila sep>
                <button id="btn-cambiar-clave" onClick={alCambiarCredencial}>
                  Cambiar credencial
                </button>
                <button id="btn-cerrar-sesion" className="peligro" onClick={alCerrarSesion}>
                  Cerrar sesión
                </button>
              </Fila>
              <p className="tenue">
                Cerrar sesión olvida la credencial de esta pestaña. No hay ninguna
                petición al servidor porque no hay nada que revocar: la clave sigue
                siendo válida hasta que se quite del servidor.
              </p>
            </>
          ) : (
            <>
              <p className="tenue">
                {sesion === "sin-autenticacion"
                  ? "El servidor no exige credencial: la API está abierta en este proceso."
                  : "No hay ninguna credencial utilizable en esta pestaña."}
              </p>
              <Fila sep>
                <button className="primario" onClick={alCambiarCredencial}>
                  Introducir credencial
                </button>
              </Fila>
            </>
          )}
        </Panel>
      </Seccion>

      {panelPortabilidad}

      <Seccion titulo="Estado del servidor" nota="Leído de GET /health, que está abierto en los dos modos.">
        <Panel>
          <dl className="datos">
            <dt>estado</dt>
            <dd>
              {saludError ? (
                <Chip tono="error">sin respuesta</Chip>
              ) : salud ? (
                <Chip tono="ok">{salud.status}</Chip>
              ) : (
                "comprobando…"
              )}
            </dd>
            <dt>fase</dt>
            <dd className="mono">{salud?.fase ?? "—"}</dd>
            <dt>reconocimiento de voz</dt>
            <dd>
              {salud ? (
                <Chip tono={salud.stt ? "ok" : "aviso"}>
                  {salud.stt ? "adaptador disponible (modelo no comprobado)" : "adaptador no disponible"}
                </Chip>
              ) : (
                "—"
              )}
            </dd>
            <dt>ejecuciones guardadas</dt>
            <dd>{salud ? numero(salud.ejecuciones) : "—"}</dd>
            <dt>proyectos registrados</dt>
            <dd>{salud ? numero(salud.proyectos) : "—"}</dd>
            <dt>flujo de eventos</dt>
            <dd>
              {conexion === "conectado" ? (
                <Chip tono="ok">conectado</Chip>
              ) : conexion === "error" ? (
                <Chip tono="error">interrumpido</Chip>
              ) : (
                <span className="tenue">sin ejecución abierta</span>
              )}
            </dd>
          </dl>
        </Panel>
      </Seccion>
    </>
  );
}

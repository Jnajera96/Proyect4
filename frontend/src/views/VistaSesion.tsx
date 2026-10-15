/**
 * Sesion: la credencial de esta pestana y lo que el servidor declara de si mismo.
 *
 * **No hay ajustes que guardar.** El backend no tiene un endpoint de configuracion:
 * lo que se ve aqui es lo que `/health` publica y lo que esta pestana sabe de su
 * propia sesion. Se evita por tanto la seccion de "Settings" con interruptores que
 * no cambian nada -que es peor que no tenerla, porque promete un control que no
 * existe-.
 *
 * **Cerrar sesion no llama a ningun endpoint.** Una credencial es una clave, no una
 * sesion con estado: olvidarla en memoria **es** cerrar la sesion. Inventar un
 * `POST /logout` que el backend no tiene seria mentir sobre el mecanismo.
 */
import type { EstadoConexion } from "../hooks/useEventosRun";
import type { EstadoSesion } from "../lib/auth";
import type { Health } from "../lib/contracts";
import { numero } from "../lib/formato";
import { Chip, Fila, Panel, Seccion } from "../components/ui";

export function VistaSesion({
  sesion,
  rol,
  credencial,
  conexion,
  salud,
  saludError,
  alCambiarCredencial,
  alCerrarSesion,
}: {
  sesion: EstadoSesion;
  rol: string | null;
  /** Credencial enmascarada, o `null` si no hay ninguna. */
  credencial: string | null;
  conexion: EstadoConexion;
  salud: Health | null;
  saludError: boolean;
  alCambiarCredencial: () => void;
  alCerrarSesion: () => void;
}) {
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

      <Seccion titulo="Lo que este sistema no tiene">
        <Panel nota="Se dice para que no se busque donde no hay.">
          <ul className="limpia">
            <li>
              No hay ajustes que guardar: el servidor no expone ningún endpoint de
              configuración.
            </li>
            <li>
              No hay usuarios, ni contraseñas, ni registro, ni recuperación de cuenta:
              el mecanismo es una clave de API.
            </li>
            <li>
              No hay cancelación de una ejecución en curso: el endpoint responde 501.
            </li>
            <li>
              No hay borrado de ejecuciones ni de proyectos: no existe el endpoint.
            </li>
          </ul>
        </Panel>
      </Seccion>
    </>
  );
}

/**
 * Seguridad: lo que el sistema registro sobre sus propios limites.
 *
 * Reune tres cosas reales: las clases de error que el motor emite (`POLICY_DENIED`,
 * `SANDBOX_PATH_DENIED`, `PROMOTION_DENIED`, `BUDGET_EXCEEDED`, `MODEL_FALLBACK`),
 * el **aislamiento** declarado en la ejecucion (rutas permitidas y protegidas, el
 * worktree del sandbox y el commit base) y el estado de la sesion.
 *
 * El aislamiento y el recuento de incidencias los pinta `PanelSeguridadRun`, que
 * es el mismo panel que usa el detalle de la ejecucion: es la misma informacion, y
 * con dos copias habria bastado tocar una para que dijeran cosas distintas.
 *
 * **No se ensena nada que pueda ser un secreto.** Ni la credencial, ni la URL del
 * flujo de eventos -que la lleva en la query-, ni cabeceras, ni rutas absolutas
 * innecesarias. La ruta del worktree es un dato del aislamiento y se muestra
 * acortada.
 */
import type { EstadoSesion } from "../lib/auth";
import type { RunState } from "../lib/contracts";
import { PanelErrores, PanelPresupuesto, PanelSeguridadRun } from "../components/evidencia";
import { EstadoVacio, Panel, Seccion } from "../components/ui";

export function VistaSeguridad({
  estado,
  sesion,
  rol,
}: {
  estado: RunState | null;
  sesion: EstadoSesion;
  rol: string | null;
}) {
  return (
    <>
      <Seccion titulo="Sesión" nota="El estado de acceso de esta pestaña.">
        <Panel>
          <dl className="datos">
            <dt>Autenticación</dt>
            <dd>
              {sesion === "autenticado"
                ? "activa: el servidor exige credencial y esta pestaña la presenta"
                : sesion === "sin-autenticacion"
                  ? "desactivada en el servidor: no hace falta credencial"
                  : "sin credencial utilizable"}
            </dd>
            <dt>Autorización por roles</dt>
            <dd>
              {sesion === "sin-autenticacion" ? "No se exige rol en el modo local sin autenticación." : rol
                ? `activa · rol de la credencial: ${rol}`
                : "activa en el servidor; el rol no se conoce hasta que una acción sea rechazada"}
            </dd>
            <dt>Credencial</dt>
            <dd>en memoria, solo en esta pestaña; nunca se guarda ni se muestra</dd>
          </dl>
        </Panel>
      </Seccion>

      {!estado ? (
        <Panel>
          <EstadoVacio titulo="Ninguna ejecución seleccionada">
            Los límites que se registran -política, aislamiento, presupuesto- son de una
            ejecución concreta. Elige una para ver lo que el sistema anotó sobre ella.
          </EstadoVacio>
        </Panel>
      ) : (
        <>
          {/* El aislamiento y el recuento de incidencias salen del panel
              compartido con el detalle de la ejecucion: es la misma informacion y
              con dos copias habria bastado tocar una para que dijeran cosas
              distintas. */}
          <PanelSeguridadRun estado={estado} />

          <Seccion titulo="Registro de errores">
            <PanelErrores errores={estado.errors} />
          </Seccion>

          <Seccion titulo="Presupuesto">
            <PanelPresupuesto budget={estado.budget} />
          </Seccion>
        </>
      )}
    </>
  );
}

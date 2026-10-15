/**
 * Pantalla de acceso.
 *
 * Se muestra cuando el servidor **exige** credencial y no hay ninguna utilizable.
 * No es decorativa ni opcional: sin credencial, cada panel de la aplicacion
 * quedaria vacio o en error, asi que la pantalla sustituye al contenido en lugar
 * de convivir con el.
 *
 * **Un solo campo.** El mecanismo real es una clave de API: no hay usuario, ni
 * contrasena, ni registro, ni recuperacion de cuenta, y por eso no hay campos
 * para nada de eso. Un formulario que pidiera mas de lo que el backend usa
 * mentiria sobre como funciona el sistema.
 *
 * **La credencial no se ensena.** El campo es de tipo `password` y no hay boton
 * para revelarla: quien la pego puede comprobarla por su mascara una vez
 * aceptada, que es para lo que sirve la mascara.
 *
 * Los identificadores (`#api-key`, `#btn-continuar`) son estables a proposito: la
 * verificacion del navegador rellena este formulario como lo haria una persona.
 */
import { useState } from "react";

export function PantallaAcceso({
  validando,
  mensaje,
  onEntrar,
  onCancelar,
}: {
  /** La credencial se esta comprobando contra el servidor. */
  validando: boolean;
  /** Texto del ultimo intento fallido, si lo hubo. */
  mensaje: string | null;
  onEntrar: (clave: string) => void;
  /** Solo existe cuando ya habia sesion y se esta cambiando la credencial. */
  onCancelar?: () => void;
}) {
  const [clave, setClave] = useState("");

  return (
    <div className="acceso">
      <div className="acceso-tarjeta">
        <h1 className="acceso-titulo">AI Software Engineering System</h1>
        <p className="acceso-lema">Espacio de trabajo local seguro</p>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!validando) onEntrar(clave);
          }}
        >
          <label htmlFor="api-key">Clave API</label>
          <input
            id="api-key"
            type="password"
            value={clave}
            onChange={(e) => setClave(e.target.value)}
            placeholder="pegar aquí la credencial"
            autoComplete="off"
            spellCheck={false}
            autoFocus
          />

          <div className="fila fila-sep">
            <button
              id="btn-continuar"
              type="submit"
              className="primario"
              disabled={validando || !clave.trim()}
            >
              {validando ? "Comprobando…" : "Continuar"}
            </button>
            {onCancelar ? (
              <button type="button" className="sutil" onClick={onCancelar}>
                Cancelar
              </button>
            ) : null}
          </div>
        </form>

        {mensaje ? (
          <p className="aviso" role="alert">
            {mensaje}
          </p>
        ) : null}

        <p className="acceso-pie">
          La credencial permanece en memoria, solo en esta pestaña. Al cerrar o
          recargar la página se olvida.
        </p>
      </div>
    </div>
  );
}

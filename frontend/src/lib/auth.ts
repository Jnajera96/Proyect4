/**
 * Credencial de la sesion del dashboard (Fase 4, `AUD-06`).
 *
 * **Cuando hace falta.** El servidor acepta dos modos: con `AI_SWE_API_KEYS`
 * vacio la autenticacion esta **desactivada** y no hace falta ninguna credencial;
 * con al menos una clave declarada, toda la API -menos `GET /health`- exige
 * credenciales y sin ellas responde 401. Cual de los dos modos es **no se
 * adivina**: se deduce de la respuesta real de la primera peticion protegida (ver
 * `App`). Esta capa solo guarda el valor.
 *
 * **En memoria, y por que.** La credencial vive en una variable de modulo: dura
 * lo que dura la pestana y **no** se escribe en `localStorage`, `sessionStorage`,
 * IndexedDB ni en una cookie propia. Nada de eso aporta nada aqui -no hay sesion
 * que reanudar ni varios usuarios en el mismo navegador- y todo eso deja el
 * secreto en un sitio que sobrevive a la pestana y que cualquier script del
 * origen puede leer. El precio es que recargar la pagina pide la credencial otra
 * vez; es el precio correcto y esta escrito en la interfaz.
 *
 * **La clave de build tambien se retiro.** `VITE_AI_SWE_API_KEY` existia para
 * incrustar una credencial al construir. Incrustar un secreto en el bundle es
 * publicarlo -el JS se sirve a cualquiera que abra la pagina-, asi que
 * desaparecio junto con el almacenamiento.
 *
 * **Como se propaga un cambio.** `guardarClave` y `borrarClave` avisan a quien
 * este suscrito. El flujo SSE lo necesita: lleva la credencial en la URL del
 * `EventSource` y tiene que reconectar cuando cambia.
 */
import { useEffect, useState } from "react";

/** La credencial de esta pestana. `null` = no hay ninguna. */
let claveEnMemoria: string | null = null;

/** Quien quiere enterarse de un cambio de credencial. */
const suscriptores = new Set<() => void>();

function avisar(): void {
  for (const notificar of suscriptores) notificar();
}

/**
 * Estado de acceso de la interfaz.
 *
 * Son los estados que el flujo real puede producir, ni uno mas:
 *
 *   - `comprobando`      — aun no se sabe si el servidor exige credencial.
 *   - `sin-autenticacion`— el servidor no la exige; la aplicacion esta abierta.
 *   - `sin-credencial`   — la exige y no hay ninguna (UNAUTHENTICATED).
 *   - `validando`        — se esta comprobando la que se acaba de introducir
 *                          (AUTHENTICATING).
 *   - `autenticado`      — las peticiones pasan (AUTHENTICATED).
 *   - `clave-invalida`   — se presento una y el servidor la rechazo
 *                          (INVALID_CREDENTIALS).
 *   - `sesion-caida`     — la que valia dejo de valer, p. ej. revocada
 *                          (SESSION/KEY_ERROR).
 *   - `sin-servidor`     — no se pudo preguntar; no es un problema de credencial.
 *
 * `UNAUTHORIZED` (403) **no** es un estado de sesion: la sesion sigue siendo
 * valida y lo que falta es permiso para una accion concreta. Se lleva aparte, en
 * `App`, porque es ortogonal y puede ocurrir con cualquiera de los estados
 * autenticados.
 */
export type EstadoSesion =
  | "comprobando"
  | "sin-autenticacion"
  | "sin-credencial"
  | "validando"
  | "autenticado"
  | "clave-invalida"
  | "sesion-caida"
  | "sin-servidor";

/** La credencial en uso, o `null`. La lee `api.ts` en **cada** peticion. */
export function claveActiva(): string | null {
  return claveEnMemoria;
}

/** `true` si hay una credencial en memoria. */
export function hayClave(): boolean {
  return claveEnMemoria !== null;
}

/** Fija la credencial de la sesion. Una cadena vacia no cambia nada. */
export function guardarClave(clave: string): void {
  const limpia = clave.trim();
  if (!limpia) return;
  claveEnMemoria = limpia;
  avisar();
}

/**
 * Olvida la credencial y vuelve al estado no autenticado.
 *
 * No hay peticion de por medio porque no hay nada que pedirle al servidor: la
 * credencial es una clave, no una sesion con estado. Borrarla aqui **es** cerrar
 * la sesion.
 */
export function borrarClave(): void {
  if (claveEnMemoria === null) return;
  claveEnMemoria = null;
  avisar();
}

/**
 * Representacion **enmascarada** de una credencial, para la interfaz.
 *
 * Muestra solo los dos ultimos caracteres: sirve para que quien la introdujo
 * confirme que es la suya y no para reconstruirla. El resto se tapa con un punto
 * por caracter, de modo que tampoco se anade informacion sobre la longitud que el
 * sistema no diga ya: el registro de auditoria del servidor publica
 * `clav...len26`. Con dos caracteres o menos no hay nada que ocultar que merezca
 * la pena ensenar, y se tapa entero.
 *
 * Es una funcion pura de la credencial, no una lectura del estado del modulo:
 * quien la pinta ya esta suscrito con `useClaveApi`, y asi la mascara no puede
 * quedarse desfasada respecto a lo que se esta enviando.
 */
export function enmascarar(clave: string | null): string | null {
  if (clave === null) return null;
  const visibles = 2;
  if (clave.length <= visibles) return "\u2022".repeat(clave.length);
  return "\u2022".repeat(clave.length - visibles) + clave.slice(-visibles);
}

/** Suscripcion al cambio de credencial, para componentes React. */
export function useClaveApi(): string | null {
  const [clave, setClave] = useState<string | null>(claveActiva);

  useEffect(() => {
    const refrescar = () => setClave(claveActiva());
    suscriptores.add(refrescar);
    // Por si el valor cambio entre el primer render y la suscripcion.
    refrescar();
    return () => {
      suscriptores.delete(refrescar);
    };
  }, []);

  return clave;
}

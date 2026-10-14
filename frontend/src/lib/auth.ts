/**
 * Clave de API del dashboard (Fase 4, `AUD-06`).
 *
 * **Cuando hace falta.** El servidor acepta dos modos: con `AI_SWE_API_KEYS`
 * vacio la autenticacion esta **desactivada** y esta clave se ignora; con al
 * menos una clave declarada, toda la API -menos `GET /health`- exige credenciales
 * y sin ella las peticiones responden 401. El cliente no puede saber en que modo
 * esta hasta que recibe el primer 401, asi que la clave se guarda aqui y se manda
 * siempre que exista: en el modo sin autenticacion el servidor la ignora.
 *
 * **Donde se guarda.** En `localStorage`, no en una variable de modulo: una
 * recarga de pagina no debe pedirla otra vez, y este dashboard es de una sola
 * persona en su propia maquina. Es un secreto en el navegador, con lo que eso
 * significa -cualquier script de la pagina puede leerlo-; por eso la interfaz lo
 * trata como dato sensible y ofrece borrarlo.
 *
 * **La clave de entorno manda menos.** `VITE_AI_SWE_API_KEY` existe para
 * despliegues donde la clave se conoce al construir (y queda **incrustada en el
 * build**, que es publico: sirve para el bucle local, no para un secreto real).
 * La clave guardada en el navegador, si existe, tiene prioridad.
 *
 * **Como se propaga un cambio.** Guardar u olvidar la clave emite un evento
 * `ai_swe:clave` en `window`. Quien necesite reaccionar -el flujo SSE, que lleva
 * la clave en la URL- se suscribe con `useClaveApi`, que tambien escucha
 * `storage` para que dos pestanas abiertas se queden sincronizadas.
 */

import { useEffect, useState } from "react";

const CLAVE_STORAGE = "ai_swe.api_key";
const EVENTO_CAMBIO = "ai_swe:clave";

function almacen(): Storage | null {
  try {
    // `localStorage` puede lanzar (modo privado de Safari, cookies bloqueadas,
    // origen `file://`). Un dashboard que no puede guardar la clave debe seguir
    // funcionando en modo sin autenticacion.
    return window.localStorage;
  } catch {
    return null;
  }
}

/** Clave fijada al construir el frontend, si se declaro. */
export function claveDeEntorno(): string | null {
  const valor = import.meta.env.VITE_AI_SWE_API_KEY;
  return typeof valor === "string" && valor.trim() ? valor.trim() : null;
}

/** Clave guardada en este navegador, o `null`. */
export function claveGuardada(): string | null {
  const valor = almacen()?.getItem(CLAVE_STORAGE);
  return valor && valor.trim() ? valor : null;
}

/** La clave en uso: la guardada manda sobre la de entorno. */
export function claveActiva(): string | null {
  return claveGuardada() ?? claveDeEntorno();
}

/** Guarda la clave y avisa a la interfaz. */
export function guardarClave(clave: string): void {
  almacen()?.setItem(CLAVE_STORAGE, clave);
  window.dispatchEvent(new Event(EVENTO_CAMBIO));
}

/** La borra y avisa. Sin clave guardada no se emite evento: no ha cambiado nada. */
export function borrarClave(): void {
  if (claveGuardada() === null) return;
  almacen()?.removeItem(CLAVE_STORAGE);
  window.dispatchEvent(new Event(EVENTO_CAMBIO));
}

/**
 * Suscripcion al cambio de clave, para componentes React.
 *
 * Se escuchan el evento propio y `storage`: el primero cubre esta pestana, el
 * segundo otra pestana que guarde o borre la clave mientras esta esta abierta.
 */
export function useClaveApi(): string | null {
  const [clave, setClave] = useState<string | null>(claveActiva);

  useEffect(() => {
    const refrescar = () => setClave(claveActiva());
    window.addEventListener(EVENTO_CAMBIO, refrescar);
    window.addEventListener("storage", refrescar);
    return () => {
      window.removeEventListener(EVENTO_CAMBIO, refrescar);
      window.removeEventListener("storage", refrescar);
    };
  }, []);

  return clave;
}

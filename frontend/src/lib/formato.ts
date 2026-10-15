/**
 * Formato de numeros, fechas y rutas.
 *
 * Un solo sitio para las reglas, por dos razones: que un mismo dato no se vea
 * distinto en dos paneles, y que las decisiones delicadas -cuanto de una ruta se
 * ensena- se tomen una vez y no en cada componente.
 */

/** Numero con separador de millares en castellano: `1.234`. */
export function numero(valor: number): string {
  return new Intl.NumberFormat("es-ES").format(valor);
}

/**
 * Porcentaje consumido, acotado a `[0, 100]`.
 *
 * Se acota porque un limite puede superarse -el presupuesto se comprueba antes de
 * gastar, no despues- y una barra de progreso al 137% no significa nada.
 */
export function porcentaje(usado: number, maximo: number): number {
  if (maximo <= 0) return 0;
  return Math.min(100, Math.max(0, (usado / maximo) * 100));
}

/** Duracion legible: `2 min 05 s`, `12,4 s`, `340 ms`. */
export function duracion(segundos: number): string {
  if (!Number.isFinite(segundos) || segundos < 0) return "—";
  if (segundos < 1) return `${Math.round(segundos * 1000)} ms`;
  if (segundos < 60) return `${segundos.toFixed(1).replace(".", ",")} s`;
  const minutos = Math.floor(segundos / 60);
  const resto = Math.round(segundos % 60);
  return `${minutos} min ${String(resto).padStart(2, "0")} s`;
}

/** Fecha y hora cortas: `13 oct, 18:04`. */
export function fechaHora(iso: string): string {
  const fecha = new Date(iso);
  if (Number.isNaN(fecha.getTime())) return iso;
  return fecha.toLocaleString("es-ES", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Hash acortado para leerlo en pantalla: los ocho primeros caracteres.
 *
 * El valor completo no cabe y no aporta: lo que hace falta es poder **comparar**
 * dos hashes de un vistazo. El completo viaja en el atributo `title`.
 */
export function hashCorto(hash: string): string {
  return hash.length > 8 ? `${hash.slice(0, 8)}…` : hash;
}

/**
 * Ruta acortada: los dos ultimos segmentos.
 *
 * **Por que no se ensena la ruta entera por defecto.** Una ruta absoluta revela el
 * nombre de usuario, la estructura de discos y donde vive el repositorio: nada de
 * eso hace falta para leer una pantalla, y todo eso es informacion del entorno de
 * quien la mira. La ruta completa sigue disponible en el `title` -es un dato real,
 * no se esconde-, pero no ocupa el sitio principal.
 */
export function rutaCorta(ruta: string): string {
  const limpia = ruta.replace(/[\\/]+$/, "");
  const partes = limpia.split(/[\\/]+/).filter(Boolean);
  if (partes.length <= 2) return limpia;
  return `…/${partes.slice(-2).join("/")}`;
}

/** `true` si la ejecucion esta en un estado terminal. */
export function esTerminal(estado: string): boolean {
  return ["completed", "failed", "needs_human", "cancelled"].includes(estado);
}

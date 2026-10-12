/**
 * Visor de diffs unificados.
 *
 * Recibe el texto de un `diff -u` y lo pinta con las lineas de adicion y borrado
 * coloreadas. **No reescribe el diff**: muestra las lineas que hay, con su
 * prefijo. Un visor que "limpia" el diff puede ocultar una linea, y una linea
 * oculta en un visor de aprobacion es exactamente lo que no puede pasar.
 *
 * Se separa por ficheros (`diff --git` o `--- `) cuando el texto contiene varios.
 */
import { type ReactNode } from "react";

function claseDeLinea(linea: string): string {
  if (linea.startsWith("+++") || linea.startsWith("---")) return "meta";
  if (linea.startsWith("@@")) return "meta";
  if (linea.startsWith("diff ") || linea.startsWith("index ")) return "meta";
  if (linea.startsWith("+")) return "add";
  if (linea.startsWith("-")) return "del";
  return "ctx";
}

export function Diff({
  texto,
  maxFilas,
}: {
  texto: string;
  maxFilas?: number;
}) {
  if (!texto.trim()) {
    return <p className="vacio">sin cambios</p>;
  }
  const lineas = texto.split("\n");
  const visibles = maxFilas ? lineas.slice(0, maxFilas) : lineas;
  const truncado = maxFilas ? lineas.length - visibles.length : 0;

  return (
    <>
      <div className="diff">
        {visibles.map((linea, i) => (
          <div key={i} className={claseDeLinea(linea)}>
            {linea || " "}
          </div>
        ))}
      </div>
      {truncado > 0 ? (
        <p className="tenue fila-sep">… y {truncado} línea(s) más</p>
      ) : null}
    </>
  );
}

/** Cabecera de un fichero cambiado, con su recuento de lineas. */
export function CabeceraFichero({
  ruta,
  added,
  removed,
}: {
  ruta: string;
  added?: number;
  removed?: number;
}): ReactNode {
  return (
    <div className="fichero-cabecera">
      <span className="ruta">{ruta}</span>
      {added !== undefined ? <span className="mas">+{added}</span> : null}
      {removed !== undefined ? <span className="menos">−{removed}</span> : null}
    </div>
  );
}

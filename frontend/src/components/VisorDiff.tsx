/**
 * Visor de diffs unificados.
 *
 * **No reescribe el diff.** Muestra las lineas que hay, con su prefijo y su
 * numero, porque una linea que el visor "limpie" es una linea que puede ocultarse
 * -y una linea oculta en una pantalla de aprobacion es justo lo que no puede
 * pasar-. Lo que si hace es **leerlo**: separa los ficheros, cuenta anadidas y
 * borradas y numera cada lado.
 *
 * El numero de linea de cada lado se lleva por separado: en un `-` avanza el
 * izquierdo y en un `+` el derecho, que es como se lee un diff de verdad. Sin eso
 * los numeros mienten en cuanto hay una linea de contexto.
 */
import { useMemo } from "react";
import { rutaCorta } from "../lib/formato";

type Tipo = "add" | "del" | "ctx" | "meta";

interface Linea {
  tipo: Tipo;
  texto: string;
  viejo: number | null;
  nuevo: number | null;
}

interface Fichero {
  ruta: string;
  lineas: Linea[];
  anadidas: number;
  borradas: number;
}

function tipoDeLinea(linea: string): Tipo {
  if (
    linea.startsWith("+++") ||
    linea.startsWith("---") ||
    linea.startsWith("@@") ||
    linea.startsWith("diff ") ||
    linea.startsWith("index ") ||
    linea.startsWith("new file") ||
    linea.startsWith("deleted file") ||
    linea.startsWith("similarity index") ||
    linea.startsWith("rename ")
  ) {
    return "meta";
  }
  if (linea.startsWith("+")) return "add";
  if (linea.startsWith("-")) return "del";
  return "ctx";
}

/** Cabecera de hunk: `@@ -12,7 +12,9 @@` da los dos contadores de arranque. */
function rangoDeHunk(linea: string): { viejo: number; nuevo: number } | null {
  const m = /^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/.exec(linea);
  if (!m) return null;
  return { viejo: Number(m[1]), nuevo: Number(m[2]) };
}

function parsear(texto: string): Fichero[] {
  const ficheros: Fichero[] = [];
  let actual: Fichero | null = null;
  let viejo = 0;
  let nuevo = 0;

  for (const linea of texto.split("\n")) {
    if (linea.startsWith("diff --git ")) {
      // `diff --git a/ruta b/ruta`: se toma el lado derecho, que es el resultado.
      const partes = linea.split(" ");
      const ruta = (partes[partes.length - 1] || "").replace(/^b\//, "");
      actual = { ruta, lineas: [], anadidas: 0, borradas: 0 };
      ficheros.push(actual);
      continue;
    }
    if (!actual) {
      actual = { ruta: "", lineas: [], anadidas: 0, borradas: 0 };
      ficheros.push(actual);
    }
    if (linea.startsWith("+++ ") && !actual.ruta) {
      actual.ruta = linea.slice(4).replace(/^b\//, "").trim();
    }

    const hunk = rangoDeHunk(linea);
    if (hunk) {
      viejo = hunk.viejo;
      nuevo = hunk.nuevo;
      actual.lineas.push({ tipo: "meta", texto: linea, viejo: null, nuevo: null });
      continue;
    }

    const tipo = tipoDeLinea(linea);
    if (tipo === "add") {
      actual.lineas.push({ tipo, texto: linea, viejo: null, nuevo });
      actual.anadidas += 1;
      nuevo += 1;
    } else if (tipo === "del") {
      actual.lineas.push({ tipo, texto: linea, viejo, nuevo: null });
      actual.borradas += 1;
      viejo += 1;
    } else if (tipo === "ctx") {
      actual.lineas.push({ tipo, texto: linea, viejo, nuevo });
      viejo += 1;
      nuevo += 1;
    } else {
      actual.lineas.push({ tipo, texto: linea, viejo: null, nuevo: null });
    }
  }

  // Un fichero sin lineas de contenido no aporta nada a la revision.
  return ficheros.filter((f) => f.lineas.some((l) => l.tipo !== "meta"));
}

export function VisorDiff({
  texto,
  ficheros,
}: {
  texto: string;
  /** Recuentos por fichero que manda el backend (`changed_files`). */
  ficheros?: { path: string; added: number; removed: number; sha256: string }[];
}) {
  const partes = useMemo(() => parsear(texto), [texto]);

  if (!texto.trim()) {
    return <p className="vacio">Sin cambios que mostrar.</p>;
  }

  const totalAnadidas = ficheros?.reduce((s, f) => s + f.added, 0) ?? partes.reduce((s, f) => s + f.anadidas, 0);
  const totalBorradas = ficheros?.reduce((s, f) => s + f.removed, 0) ?? partes.reduce((s, f) => s + f.borradas, 0);

  return (
    <div className="visor-diff">
      <div className="diff-resumen">
        <span className="mono">{partes.length}</span> fichero(s)
        <span className="mas">+{totalAnadidas}</span>
        <span className="menos">−{totalBorradas}</span>
      </div>

      {partes.map((f, i) => (
        <article className="fichero-diff" key={`${f.ruta}-${i}`}>
          <header className="fichero-cabecera">
            <span className="ruta" title={f.ruta}>
              {f.ruta ? rutaCorta(f.ruta) : "(fichero sin nombre en el diff)"}
            </span>
            <span className="fila" style={{ marginLeft: "auto" }}>
              <span className="mas">+{f.anadidas}</span>
              <span className="menos">−{f.borradas}</span>
            </span>
          </header>
          <div className="diff">
            {f.lineas.map((l, j) => (
              <div className={l.tipo} key={j}>
                <span className="n">{l.viejo ?? ""}</span>
                <span className="n">{l.nuevo ?? ""}</span>
                <span className="c">{l.texto || " "}</span>
              </div>
            ))}
          </div>
        </article>
      ))}
    </div>
  );
}

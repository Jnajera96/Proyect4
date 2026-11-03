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
import { useMemo, useState } from "react";
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
  let enHunk = false;

  for (const linea of texto.split("\n")) {
    if (linea.startsWith("diff --git ")) {
      actual = { ruta: "", lineas: [{ tipo: "meta", texto: linea, viejo: null, nuevo: null }], anadidas: 0, borradas: 0 };
      ficheros.push(actual);
      enHunk = false;
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
      enHunk = true;
      viejo = hunk.viejo;
      nuevo = hunk.nuevo;
      actual.lineas.push({ tipo: "meta", texto: linea, viejo: null, nuevo: null });
      continue;
    }

    const tipo = enHunk && (linea.startsWith("+") || linea.startsWith("-"))
      ? tipoDeLinea(linea) : enHunk && linea.startsWith(" ") ? "ctx" : "meta";
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

  // Tambien se conservan renombres, binarios y metadatos sin hunks.
  return ficheros;
}

/**
 * Filas de la vista dividida: cada bloque de `-` se empareja con el bloque de `+`
 * que le sigue, que es como se lee una sustitución. Una línea sin pareja deja la
 * otra columna vacía; **ninguna línea se omite ni se fusiona**.
 */
interface FilaDividida {
  meta?: Linea;
  izq: Linea | null;
  der: Linea | null;
}

function filasDivididas(lineas: Linea[]): FilaDividida[] {
  const filas: FilaDividida[] = [];
  let i = 0;
  while (i < lineas.length) {
    const l = lineas[i];
    if (l.tipo === "meta") { filas.push({ meta: l, izq: null, der: null }); i += 1; continue; }
    if (l.tipo === "ctx") { filas.push({ izq: l, der: l }); i += 1; continue; }
    const borradas: Linea[] = [];
    const anadidas: Linea[] = [];
    while (i < lineas.length && lineas[i].tipo === "del") borradas.push(lineas[i++]);
    while (i < lineas.length && lineas[i].tipo === "add") anadidas.push(lineas[i++]);
    for (let k = 0; k < Math.max(borradas.length, anadidas.length); k += 1) {
      filas.push({ izq: borradas[k] ?? null, der: anadidas[k] ?? null });
    }
  }
  return filas;
}

/** `\ No newline at end of file`: metadato del protocolo que se resalta, no se oculta. */
function claseLinea(l: Linea): string {
  return l.texto.startsWith("\\") ? `${l.tipo} eof` : l.tipo;
}

function idFichero(i: number): string {
  return `diff-fichero-${i}`;
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
  const [modo, setModo] = useState<"unificado" | "dividido">("unificado");
  const [plegados, setPlegados] = useState<ReadonlySet<number>>(() => new Set());

  if (!texto.trim()) {
    return <p className="vacio">Sin cambios que mostrar.</p>;
  }

  const totalAnadidas = ficheros?.reduce((s, f) => s + f.added, 0) ?? partes.reduce((s, f) => s + f.anadidas, 0);
  const totalBorradas = ficheros?.reduce((s, f) => s + f.removed, 0) ?? partes.reduce((s, f) => s + f.borradas, 0);

  function alternar(i: number) {
    setPlegados((previos) => {
      const siguiente = new Set(previos);
      if (siguiente.has(i)) siguiente.delete(i); else siguiente.add(i);
      return siguiente;
    });
  }

  return (
    <div className={`visor-diff modo-${modo}`}>
      <div className="diff-barra">
        <div className="diff-resumen">
          <span className="mono">{partes.length}</span> fichero(s)
          <span className="mas">+{totalAnadidas}</span>
          <span className="menos">−{totalBorradas}</span>
        </div>
        <div className="diff-controles">
          <div className="segmentado" role="group" aria-label="Modo de visualización del diff">
            <button type="button" aria-pressed={modo === "unificado"} onClick={() => setModo("unificado")}>Unificado</button>
            <button type="button" aria-pressed={modo === "dividido"} onClick={() => setModo("dividido")}>Dividido</button>
          </div>
          {partes.length > 1 ? (
            <button type="button" className="sutil" onClick={() => setPlegados(plegados.size ? new Set() : new Set(partes.map((_, i) => i)))}>
              {plegados.size ? "Expandir todo" : "Plegar todo"}
            </button>
          ) : null}
        </div>
      </div>

      {partes.length > 1 ? (
        <nav className="diff-indice" aria-label="Ficheros del cambio">
          {partes.map((f, i) => (
            <a key={`${f.ruta}-${i}`} href={`#${idFichero(i)}`} className="diff-indice-item"
              onClick={(e) => { e.preventDefault(); document.getElementById(idFichero(i))?.scrollIntoView({ behavior: "smooth", block: "start" }); }}>
              <span className="ruta mono" title={f.ruta}>{f.ruta ? rutaCorta(f.ruta) : "(sin nombre)"}</span>
              <span className="mas">+{f.anadidas}</span>
              <span className="menos">−{f.borradas}</span>
            </a>
          ))}
        </nav>
      ) : null}

      {partes.map((f, i) => {
        const plegado = plegados.has(i);
        return (
          <article className={`fichero-diff${plegado ? " plegado" : ""}`} key={`${f.ruta}-${i}`} id={idFichero(i)}>
            <header className="fichero-cabecera">
              <button type="button" className="fichero-plegar" aria-expanded={!plegado}
                aria-label={`${plegado ? "Expandir" : "Plegar"} ${f.ruta || "fichero"}`} onClick={() => alternar(i)}>
                <span aria-hidden="true">{plegado ? "▸" : "▾"}</span>
              </button>
              <span className="ruta" title={f.ruta}>
                {f.ruta ? rutaCorta(f.ruta) : "(fichero sin nombre en el diff)"}
              </span>
              <span className="fila" style={{ marginLeft: "auto" }}>
                <span className="mas">+{f.anadidas}</span>
                <span className="menos">−{f.borradas}</span>
              </span>
            </header>
            {plegado ? null : modo === "unificado" ? (
              <div className="diff">
                {f.lineas.map((l, j) => (
                  <div className={claseLinea(l)} key={j}>
                    <span className="n">{l.viejo ?? ""}</span>
                    <span className="n">{l.nuevo ?? ""}</span>
                    <span className="c">{l.texto || " "}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="diff diff-dividido">
                {filasDivididas(f.lineas).map((fila, j) => fila.meta ? (
                  <div className={`fila-meta ${claseLinea(fila.meta)}`} key={j}><span className="c">{fila.meta.texto || " "}</span></div>
                ) : (
                  <div className="fila-dividida" key={j}>
                    <div className={fila.izq ? (fila.izq.tipo === "ctx" ? "ctx" : "del") : "vacia"}>
                      <span className="n">{fila.izq?.viejo ?? ""}</span>
                      <span className="c">{fila.izq?.texto || " "}</span>
                    </div>
                    <div className={fila.der ? (fila.der.tipo === "ctx" ? "ctx" : "add") : "vacia"}>
                      <span className="n">{fila.der?.nuevo ?? ""}</span>
                      <span className="c">{fila.der?.texto || " "}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </article>
        );
      })}
      <details className="plegable"><summary>Diff original completo</summary><pre className="salida">{texto}</pre></details>
    </div>
  );
}

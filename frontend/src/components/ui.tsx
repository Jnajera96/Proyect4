/** Piezas de interfaz reutilizables, pequenas y sin estado. */
import type { ReactNode } from "react";

export function Chip({
  children,
  tono = "",
  pulsa = false,
}: {
  children: ReactNode;
  tono?: "" | "ok" | "aviso" | "error" | "acento" | "violeta";
  pulsa?: boolean;
}) {
  const clases = ["chip", tono].filter(Boolean).join(" ");
  return (
    <span className={clases}>
      <span className={pulsa ? "punto pulsa" : "punto"} />
      {children}
    </span>
  );
}

export function Panel({
  titulo,
  nota,
  children,
  acciones,
}: {
  titulo?: string;
  nota?: string;
  children: ReactNode;
  acciones?: ReactNode;
}) {
  return (
    <section className="panel">
      {titulo || acciones ? (
        <div className="panel-cabecera">
          {titulo ? <h2 className="panel-titulo">{titulo}</h2> : <span />}
          {acciones ? <div className="fila">{acciones}</div> : null}
        </div>
      ) : null}
      {nota ? <p className="panel-nota">{nota}</p> : null}
      {children}
    </section>
  );
}

/**
 * Seccion de una vista: rotulo, explicacion y contenido.
 *
 * Existe para que el rotulo, el espaciado y la jerarquia sean los mismos en las
 * vistas. Antes cada vista repetia su propio `<div class="seccion-titulo">` y
 * bastaba olvidarse en una para que la pagina se viera distinta.
 */
export function Seccion({
  titulo,
  nota,
  children,
  acciones,
}: {
  titulo: string;
  nota?: string;
  children: ReactNode;
  acciones?: ReactNode;
}) {
  return (
    <section className="seccion" aria-label={titulo}>
      <div className="seccion-cabecera">
        <h2 className="seccion-titulo">{titulo}</h2>
        {acciones ? <div className="fila">{acciones}</div> : null}
      </div>
      {nota ? <p className="seccion-nota">{nota}</p> : null}
      {children}
    </section>
  );
}

/** Dato suelto: rotulo pequeno y valor grande. Para la franja de estado. */
export function Tarjeta({
  rotulo,
  valor,
  pie,
  tono = "",
}: {
  rotulo: string;
  valor: ReactNode;
  pie?: ReactNode;
  tono?: "" | "ok" | "aviso" | "error" | "acento";
}) {
  return (
    <div className={`tarjeta ${tono}`.trim()}>
      <p className="tarjeta-rotulo">{rotulo}</p>
      <p className="tarjeta-valor">{valor}</p>
      {pie ? <p className="tarjeta-pie">{pie}</p> : null}
    </div>
  );
}

export function Fila({ children, sep = false }: { children: ReactNode; sep?: boolean }) {
  return <div className={sep ? "fila fila-sep" : "fila"}>{children}</div>;
}

export function Vacio({ children }: { children: ReactNode }) {
  return <p className="vacio">{children}</p>;
}

/**
 * Estado vacio con contexto.
 *
 * Una tabla sin filas no dice si el sistema esta roto, si no hay nada todavia o si
 * el filtro no encontro nada. Aqui se dice cual de las tres cosas es y, si se puede
 * hacer algo, se ofrece el boton.
 */
export function EstadoVacio({
  titulo,
  children,
  accion,
}: {
  titulo: string;
  children?: ReactNode;
  accion?: ReactNode;
}) {
  return (
    <div className="estado-vacio">
      <p className="estado-vacio-titulo">{titulo}</p>
      {children ? <p className="estado-vacio-texto">{children}</p> : null}
      {accion ? <div className="fila fila-sep">{accion}</div> : null}
    </div>
  );
}

/**
 * Esqueleto de carga.
 *
 * Se prefiere a un indicador giratorio porque conserva la forma de lo que va a
 * llegar: la pagina no salta cuando el dato entra, y quien mira sabe donde mirar.
 */
export function Esqueleto({ lineas = 3, alto = "0.9rem" }: { lineas?: number; alto?: string }) {
  return (
    <div className="esqueleto" aria-hidden="true">
      {Array.from({ length: lineas }, (_, i) => (
        <span
          key={i}
          className="esqueleto-linea"
          style={{ height: alto, width: `${100 - (i % 3) * 12}%` }}
        />
      ))}
    </div>
  );
}

/** Barra de progreso con el valor en texto, para el presupuesto. */
export function Barra({
  valor,
  maximo,
  tono = "",
  etiqueta,
}: {
  valor: number;
  maximo: number;
  tono?: "" | "aviso" | "error";
  etiqueta?: string;
}) {
  const pct = maximo > 0 ? Math.min(100, Math.max(0, (valor / maximo) * 100)) : 0;
  return (
    <div
      className={`barra ${tono}`.trim()}
      role="progressbar"
      aria-valuenow={Math.round(pct)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={etiqueta}
    >
      <span className="barra-relleno" style={{ width: `${pct}%` }} />
    </div>
  );
}

/** Formatea una marca de tiempo ISO en hora local corta. */
export function hora(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString();
  } catch {
    return iso;
  }
}

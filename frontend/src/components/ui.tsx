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
}: {
  titulo?: string;
  nota?: string;
  children: ReactNode;
}) {
  return (
    <section className="panel">
      {titulo ? <h2 className="panel-titulo">{titulo}</h2> : null}
      {nota ? <p className="panel-nota">{nota}</p> : null}
      {children}
    </section>
  );
}

export function Fila({ children, sep = false }: { children: ReactNode; sep?: boolean }) {
  return <div className={sep ? "fila fila-sep" : "fila"}>{children}</div>;
}

export function Vacio({ children }: { children: ReactNode }) {
  return <p className="vacio">{children}</p>;
}

/** Formatea una marca de tiempo ISO en hora local corta. */
export function hora(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString();
  } catch {
    return iso;
  }
}

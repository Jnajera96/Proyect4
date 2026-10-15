/**
 * Navegacion principal.
 *
 * Botones, no enlaces: no hay rutas ni historial -el estado vive en React-, y
 * fingir una URL que no existe daria un boton "atras" que no funciona. Cada boton
 * es enfocable con el teclado y anuncia cual esta activo con `aria-current`.
 */
export type VistaId =
  | "general"
  | "proyectos"
  | "ejecuciones"
  | "detalle"
  | "flujo"
  | "seguridad"
  | "sesion";

export interface ItemNav {
  id: VistaId;
  etiqueta: string;
  /** Aviso discreto: hay algo que requiere atencion en esa seccion. */
  aviso?: boolean;
}

export function Navegacion({
  vista,
  items,
  alCambiar,
}: {
  vista: VistaId;
  items: ItemNav[];
  alCambiar: (v: VistaId) => void;
}) {
  return (
    <nav className="navegacion" aria-label="Secciones de la aplicación">
      {items.map((item) => {
        const activo = item.id === vista;
        return (
          <button
            key={item.id}
            type="button"
            className={activo ? "nav-item activo" : "nav-item"}
            aria-current={activo ? "page" : undefined}
            onClick={() => alCambiar(item.id)}
          >
            {item.etiqueta}
            {item.aviso ? (
              <span className="nav-aviso" title="Requiere tu decisión" aria-label="Requiere tu decisión" />
            ) : null}
          </button>
        );
      })}
    </nav>
  );
}

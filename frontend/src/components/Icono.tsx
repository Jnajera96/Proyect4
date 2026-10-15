import type { CSSProperties } from "react";

const trazos: Record<string, string> = {
  general: "M3 10 12 3l9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1Z",
  proyectos: "M3 7V5h6l2 2h10v13H3Z",
  ejecuciones: "m9 5 11 7-11 7Z",
  detalle: "M6 3h9l4 4v14H6ZM9 11h7M9 15h7M9 18h4",
  flujo: "M5 5h4v4H5ZM15 15h4v4h-4ZM7 9v8h8M9 7h8v8",
  seguridad: "m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6ZM9 12l2 2 4-4",
  sesion: "M12 3v8M6 6a9 9 0 1 0 12 0",
  microfono: "M9 5a3 3 0 0 1 6 0v7a3 3 0 0 1-6 0ZM5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8",
  flecha: "M4 12h16m-6-6 6 6-6 6",
  menu: "M4 6h16M4 12h16M4 18h16",
  cerrar: "m6 6 12 12M18 6 6 18",
  sol: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1 1M18 18l1 1M5 19l1-1M18 6l1-1",
  codigo: "m8 7-5 5 5 5m8-10 5 5-5 5M14 4l-4 16",
  buscar: "M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14m5 12 6 6",
  pruebas: "m5 12 4 4L19 6M5 4h5M7 4v4",
};
export function Icono({ nombre, style }: { nombre: string; style?: CSSProperties }) {
  return <svg className="icono" style={style} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d={trazos[nombre] ?? trazos.detalle} />
  </svg>;
}

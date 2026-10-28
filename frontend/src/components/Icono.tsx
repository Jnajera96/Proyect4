import type { CSSProperties } from "react";

const trazos: Record<string, string> = {
  general: "M3 10 12 3l9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1Z",
  proyectos: "M3 7V5h6l2 2h10v13H3Z",
  ejecuciones: "m9 5 11 7-11 7Z",
  detalle: "M6 3h9l4 4v14H6ZM9 11h7M9 15h7M9 18h4",
  flujo: "M5 5h4v4H5ZM15 15h4v4h-4ZM7 9v8h8M9 7h8v8",
  actividad: "M3 12h4l3-7 4 14 3-7h4",
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
  cubo: "M12 2 3 7l9 5 9-5-9-5ZM3 7v10l9 5 9-5V7M12 12v10",
  play: "M8 5.5v13l11-6.5-11-6.5Z",
  campana: "M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0",
  ajustes: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9c.26.6.77 1.02 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z",
  basedatos: "M12 3c4.97 0 9 1.34 9 3s-4.03 3-9 3-9-1.34-9-3 4.03-3 9-3ZM3 6v6c0 1.66 4.03 3 9 3s9-1.34 9-3V6M3 12v6c0 1.66 4.03 3 9 3s9-1.34 9-3v-6",
  destello: "m12 3 1.9 5.8L20 10.7l-6.1 1.9L12 18.4l-1.9-5.8L4 10.7l6.1-1.9L12 3Z",
  audio: "M4 10v4M8 7v10M12 4v16M16 7v10M20 10v4",
};
export function Icono({ nombre, style }: { nombre: string; style?: CSSProperties }) {
  return <svg className="icono" style={style} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d={trazos[nombre] ?? trazos.detalle} />
  </svg>;
}

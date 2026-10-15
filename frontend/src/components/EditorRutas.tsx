import { useState } from "react";

export function EditorRutas({ id, titulo, rutas, alCambiar }: {
  id: string; titulo: string; rutas: string[]; alCambiar: (rutas: string[]) => void;
}) {
  const [entrada, setEntrada] = useState("");
  function agregar() {
    const ruta = entrada.trim();
    if (ruta && !rutas.includes(ruta)) alCambiar([...rutas, ruta]);
    setEntrada("");
  }
  return <div className="editor-rutas">
    <label htmlFor={id}>{titulo}</label>
    <div className="ruta-chips">{rutas.map(r => <span className="ruta-chip" key={r}>
      <code>{r}</code><button type="button" aria-label={`Quitar ${r} de ${titulo}`}
        onClick={() => alCambiar(rutas.filter(v => v !== r))}>×</button>
    </span>)}</div>
    <div className="fila"><input id={id} value={entrada} placeholder="Ruta relativa al repositorio"
      onChange={e => setEntrada(e.target.value)} onKeyDown={e => {
        if (e.key === "Enter") { e.preventDefault(); agregar(); }
      }} /><button type="button" onClick={agregar} disabled={!entrada.trim()}>Añadir</button></div>
  </div>;
}

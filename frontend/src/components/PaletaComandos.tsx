/**
 * Paleta de comandos (Ctrl/⌘ + K).
 *
 * El atajo que cualquier herramienta profesional ofrece: saltar a una vista, abrir
 * una ejecución o cambiar de proyecto **sin soltar el teclado**. Es solo una
 * capa de navegación: cada comando llama a las mismas funciones que los botones
 * de la barra lateral, así que no hay un segundo camino con reglas distintas.
 *
 * Accesibilidad: diálogo modal con `aria-modal`, campo con `role="combobox"`,
 * lista con `role="listbox"` y opción activa anunciada con
 * `aria-activedescendant`. Flechas para moverse, Enter para ejecutar, Escape para
 * cerrar; al cerrar, el foco vuelve a donde estaba.
 */
import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { ETIQUETA_ESTADO, type Project, type RunSummary } from "../lib/contracts";
import { Icono } from "./Icono";
import type { ItemNav, VistaId } from "./Navegacion";

export interface Comando {
  id: string;
  grupo: string;
  titulo: string;
  detalle?: string;
  icono: string;
  atajo?: string;
  ejecutar: () => void;
}

/** Coincidencia tolerante: sin acentos ni mayúsculas, todas las palabras deben aparecer. */
function normalizar(texto: string): string {
  return texto.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

export function comandosBase({
  items,
  proyectos,
  runs,
  alVista,
  alProyecto,
  alRun,
  alTema,
}: {
  items: ItemNav[];
  proyectos: Project[];
  runs: RunSummary[];
  alVista: (v: VistaId) => void;
  alProyecto: (id: string) => void;
  alRun: (id: string) => void;
  alTema: (t: "oscuro" | "claro" | "sistema") => void;
}): Comando[] {
  return [
    ...items.map((item, i) => ({
      id: `vista-${item.id}`,
      grupo: "Ir a",
      titulo: item.etiqueta,
      detalle: item.aviso ? "Requiere tu decisión" : undefined,
      icono: item.id,
      atajo: i < 9 ? `Alt ${i + 1}` : undefined,
      ejecutar: () => alVista(item.id),
    })),
    ...runs.slice(0, 8).map((run) => ({
      id: `run-${run.run_id}`,
      grupo: "Ejecuciones recientes",
      titulo: run.run_id,
      detalle: ETIQUETA_ESTADO[run.status],
      icono: "ejecuciones",
      ejecutar: () => alRun(run.run_id),
    })),
    ...proyectos.slice(0, 8).map((p) => ({
      id: `proyecto-${p.project_id}`,
      grupo: "Proyectos",
      titulo: p.name,
      detalle: p.repo_path,
      icono: "proyectos",
      ejecutar: () => alProyecto(p.project_id),
    })),
    { id: "tema-oscuro", grupo: "Apariencia", titulo: "Tema oscuro", icono: "sol", ejecutar: () => alTema("oscuro") },
    { id: "tema-claro", grupo: "Apariencia", titulo: "Tema claro", icono: "sol", ejecutar: () => alTema("claro") },
    { id: "tema-sistema", grupo: "Apariencia", titulo: "Tema del sistema", icono: "sol", ejecutar: () => alTema("sistema") },
  ];
}

export function PaletaComandos({
  abierta,
  comandos,
  alCerrar,
}: {
  abierta: boolean;
  comandos: Comando[];
  alCerrar: () => void;
}) {
  const [consulta, setConsulta] = useState("");
  const [activo, setActivo] = useState(0);
  const campo = useRef<HTMLInputElement | null>(null);
  const previo = useRef<HTMLElement | null>(null);

  const filtrados = useMemo(() => {
    const palabras = normalizar(consulta).split(/\s+/).filter(Boolean);
    if (!palabras.length) return comandos;
    return comandos.filter((c) => {
      const texto = normalizar(`${c.grupo} ${c.titulo} ${c.detalle ?? ""}`);
      return palabras.every((p) => texto.includes(p));
    });
  }, [comandos, consulta]);

  useEffect(() => {
    if (!abierta) return;
    previo.current = document.activeElement as HTMLElement | null;
    setConsulta("");
    setActivo(0);
    window.requestAnimationFrame(() => campo.current?.focus());
    return () => previo.current?.focus?.();
  }, [abierta]);

  useEffect(() => setActivo(0), [consulta]);

  useEffect(() => {
    document.getElementById(`cmd-${filtrados[activo]?.id}`)?.scrollIntoView({ block: "nearest" });
  }, [activo, filtrados]);

  if (!abierta) return null;

  function ejecutar(c: Comando | undefined) {
    if (!c) return;
    alCerrar();
    c.ejecutar();
  }

  function teclado(e: KeyboardEvent) {
    if (e.key === "ArrowDown") { e.preventDefault(); setActivo((i) => Math.min(filtrados.length - 1, i + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActivo((i) => Math.max(0, i - 1)); }
    else if (e.key === "Enter") { e.preventDefault(); ejecutar(filtrados[activo]); }
    else if (e.key === "Escape") { e.preventDefault(); alCerrar(); }
    else if (e.key === "Tab") { e.preventDefault(); }
  }

  let grupoAnterior = "";
  return (
    <div className="paleta-fondo" onMouseDown={(e) => { if (e.target === e.currentTarget) alCerrar(); }}>
      <div className="paleta" role="dialog" aria-modal="true" aria-label="Paleta de comandos" onKeyDown={teclado}>
        <div className="paleta-entrada">
          <Icono nombre="buscar" />
          <input
            ref={campo}
            role="combobox"
            aria-expanded="true"
            aria-controls="paleta-lista"
            aria-activedescendant={filtrados[activo] ? `cmd-${filtrados[activo].id}` : undefined}
            aria-autocomplete="list"
            placeholder="Busca una vista, ejecución o proyecto…"
            value={consulta}
            onChange={(e) => setConsulta(e.target.value)}
          />
          <kbd>Esc</kbd>
        </div>
        <ul id="paleta-lista" className="paleta-lista" role="listbox" aria-label="Comandos">
          {filtrados.length === 0 ? <li className="paleta-vacio">Sin coincidencias para «{consulta}».</li> : null}
          {filtrados.map((c, i) => {
            const cabecera = c.grupo !== grupoAnterior ? c.grupo : null;
            grupoAnterior = c.grupo;
            return (
              <li key={c.id} role="presentation">
                {cabecera ? <div className="paleta-grupo" aria-hidden="true">{cabecera}</div> : null}
                <div
                  id={`cmd-${c.id}`}
                  role="option"
                  aria-selected={i === activo}
                  className={`paleta-opcion${i === activo ? " activa" : ""}`}
                  onMouseMove={() => setActivo(i)}
                  onClick={() => ejecutar(c)}
                >
                  <Icono nombre={c.icono} />
                  <span className="paleta-titulo">{c.titulo}</span>
                  {c.detalle ? <span className="paleta-detalle">{c.detalle}</span> : null}
                  {c.atajo ? <kbd>{c.atajo}</kbd> : null}
                </div>
              </li>
            );
          })}
        </ul>
        <footer className="paleta-pie">
          <span><kbd>↑</kbd><kbd>↓</kbd> moverse</span>
          <span><kbd>Enter</kbd> abrir</span>
          <span><kbd>Esc</kbd> cerrar</span>
        </footer>
      </div>
    </div>
  );
}

"""Genera el diagrama arquitectonico del Proyecto 4.

Principio de diseno: **una sola definicion de layout, validada antes de dibujar.**

Un diagrama puede estar geometricamente mal y verse bien: una etiqueta con fondo
opaco tapa limpiamente lo que invade. Por eso la validacion se ejecuta sobre la
definicion del layout, no sobre el resultado, y el build aborta si algo falla.

Comprobaciones:
  1. Toda arista referencia nodos que existen.
  2. Todo nodo cabe dentro del lienzo.
  3. No hay dos nodos solapados.
  4. Ninguna etiqueta pisa una caja de nodo ni cruza el borde de una zona.
  5. Ninguna etiqueta cruza el trazo de una arista.

Uso:
    python tools/build_diagram.py [salida.svg]
"""

from __future__ import annotations

import sys
from pathlib import Path

CANVAS_W = 1400
CANVAS_H = 1080

# Se inserta al probar rectangulos: una arista que termina exactamente en el
# borde de una caja no debe contarse como cruce.
INSET = 2.0
LABEL_BOX_H = 17.0

# ---------------------------------------------------------------- paleta ----
# Modo claro: relleno 50, trazo 600, titulo 900, subtitulo 600.
RAMP = {
    "gray":   ("#F1EFE8", "#5F5E5A", "#2C2C2A"),
    "purple": ("#EEEDFE", "#534AB7", "#26215C"),
    "teal":   ("#E1F5EE", "#0F6E56", "#04342C"),
    "blue":   ("#E6F1FB", "#185FA5", "#042C53"),
    "amber":  ("#FAEEDA", "#854F0B", "#412402"),
    "green":  ("#EAF3DE", "#3B6D11", "#173404"),
}

ZONE_STYLE = {
    "app": ("#FCFCFA", "#8A8A82", "#2C2C2A"),
    "ext": ("#F6FBF9", "#0F6E56", "#04342C"),
}

# ---------------------------------------------------------------- layout ----
# (x0, y0, x1, y1)
ZONES = {
    "app": (70, 130, 985, 995),
    "ext": (1060, 130, 1380, 995),
}

ZONE_TITLES = {
    "app": "LIMITE DE CONFIANZA - APLICACION",
    "ext": "SERVICIOS EXTERNOS",
}

# key: (x0, y0, x1, y1, ramp, titulo, subtitulo)
NODES = {
    "user":       (400, 60, 720, 116, "gray", "Usuario", "dicta o escribe la tarea"),
    "frontend":   (400, 150, 720, 212, "purple", "Frontend", "captura audio - confirma transcripcion"),
    "stt":        (400, 246, 720, 308, "teal", "Speech-to-Text (adaptador)", "faster-whisper local | API cloud"),
    "api":        (400, 342, 720, 404, "blue", "API / Backend - FastAPI", "valida - crea run_id - publica progreso"),
    "supervisor": (150, 438, 950, 506, "purple", "Supervisor - LangGraph", "interpreta - planifica - enruta - controla presupuesto"),
    "researcher": (150, 545, 400, 613, "purple", "Researcher", "lee repo - reune evidencia"),
    "coder":      (425, 545, 675, 613, "purple", "Coder", "parche en worktree aislado"),
    "reviewer":   (700, 545, 950, 613, "purple", "Reviewer", "diff - pruebas - criterios"),
    "tools":      (150, 660, 560, 740, "blue", "Tools / MCP", "filesystem - git - run_tests (allowlist)"),
    "policy":     (600, 660, 950, 740, "amber", "Policy Engine y Guardrails", "allow | deny | require_approval"),
    "state":      (150, 790, 560, 870, "gray", "Shared State", "checkpointer - plan - artefactos - evidencia"),
    "hitl":       (600, 790, 950, 870, "amber", "Human-in-the-Loop", "aprobacion de acciones con efectos"),
    "result":     (400, 910, 720, 970, "green", "Resultado validado", "resumen - diff - pruebas"),
    "llm":        (1080, 438, 1360, 613, "teal", "Foundation Model", "API gestionada o local (Ollama/vLLM)"),
    "langfuse":   (1080, 660, 1360, 740, "gray", "Observabilidad - Langfuse", "traces - tokens - costo - latencia"),
    "tts":        (1080, 910, 1360, 970, "teal", "Text-to-Speech (opcional)", "solo salida - desactivable"),
}

# key: (origen, destino, [(x, y), ...])
EDGES = {
    "user_frontend":     ("user", "frontend", [(560, 116), (560, 150)]),
    "frontend_stt":      ("frontend", "stt", [(560, 212), (560, 246)]),
    "stt_api":           ("stt", "api", [(560, 308), (560, 342)]),
    "api_supervisor":    ("api", "supervisor", [(560, 404), (560, 438)]),
    "sup_researcher":    ("supervisor", "researcher", [(550, 506), (550, 528), (275, 528), (275, 545)]),
    "sup_coder":         ("supervisor", "coder", [(550, 506), (550, 545)]),
    "sup_reviewer":      ("supervisor", "reviewer", [(550, 506), (550, 528), (825, 528), (825, 545)]),
    "researcher_tools":  ("researcher", "tools", [(275, 613), (275, 660)]),
    "coder_tools":       ("coder", "tools", [(550, 613), (550, 660)]),
    "reviewer_tools":    ("reviewer", "tools", [(825, 613), (825, 640), (490, 640), (490, 660)]),
    "sup_state":         ("supervisor", "state", [(150, 472), (120, 472), (120, 830), (150, 830)]),
    "tools_state":       ("tools", "state", [(275, 740), (275, 790)]),
    "tools_policy":      ("tools", "policy", [(560, 700), (600, 700)]),
    "policy_hitl":       ("policy", "hitl", [(775, 740), (775, 790)]),
    "hitl_result":       ("hitl", "result", [(775, 870), (775, 890), (560, 890), (560, 910)]),
    "result_tts":        ("result", "tts", [(720, 940), (1080, 940)]),
    "result_frontend":   ("result", "frontend", [(400, 940), (100, 940), (100, 181), (400, 181)]),
    "sup_llm":           ("supervisor", "llm", [(950, 472), (1080, 472)]),
    "reviewer_llm":      ("reviewer", "llm", [(950, 579), (1080, 579)]),
    "sup_langfuse":      ("supervisor", "langfuse", [(950, 490), (1000, 490), (1000, 700), (1080, 700)]),
}

# (arista, texto, x, y, anchor)
LABELS = [
    ("stt_api", "texto confirmado", 596, 322, "start"),
    ("result_frontend", "respuesta al usuario", 150, 170, "start"),
    ("sup_langfuse", "traces", 1004, 636, "start"),
    ("policy_hitl", "aprobacion", 790, 765, "start"),
    ("sup_researcher", "plan y subtareas", 556, 524, "start"),
]

# La leyenda se emite y se valida igual que las etiquetas de arista. Si no
# estuviera en el modelo, podria pisar una caja y nadie lo detectaria.
LEGEND = [
    ("Linea continua: flujo principal. Linea discontinua: flujo opcional o transversal.", 80, 1014),
    ("El repositorio del usuario no se modifica hasta que se aprueba la promocion desde el worktree.", 80, 1032),
    ("Todos los agentes comparten el proveedor de modelo. El Policy Engine decide antes de cada llamada a herramienta.", 80, 1050),
]

# Aristas discontinuas (flujo opcional o transversal).
DASHED = {"result_tts", "sup_langfuse", "sup_state", "reviewer_llm"}


# ------------------------------------------------------------ validacion ----
def label_width(text: str) -> float:
    """Ancho estimado del fondo de la etiqueta. Se sobreestima a proposito."""
    return len(text) * 6.2 + 8


def free_label_rect(text: str, x: float, y: float) -> tuple[float, float, float, float]:
    """Rectangulo de una etiqueta suelta (leyenda), anclada a la izquierda."""
    w = label_width(text)
    return (x - 4, y - LABEL_BOX_H + 5, x - 4 + w, y + 5)


def label_rect(label) -> tuple[float, float, float, float]:
    _, text, lx, ly, anchor = label
    w = label_width(text)
    rx = lx - w / 2 if anchor == "middle" else (lx - 4 if anchor == "start" else lx - w)
    return (rx, ly - LABEL_BOX_H + 5, rx + w, ly + 5)


def overlaps(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def seg_hits_rect(p, q, r) -> bool:
    """Los segmentos del layout son ortogonales: solo hay dos casos."""
    x0, y0, x1, y1 = r
    (px, py), (qx, qy) = p, q
    if px == qx:
        return x0 <= px <= x1 and not (max(py, qy) < y0 or min(py, qy) > y1)
    if py == qy:
        return y0 <= py <= y1 and not (max(px, qx) < x0 or min(px, qx) > x1)
    return False


def _inset(rect, d=INSET):
    return (rect[0] + d, rect[1] + d, rect[2] - d, rect[3] - d)


def _contains(outer, inner) -> bool:
    return (outer[0] <= inner[0] and outer[1] <= inner[1]
            and outer[2] >= inner[2] and outer[3] >= inner[3])


def validate() -> list[str]:
    errors: list[str] = []

    # Control positivo: si el layout queda vacio, la validacion no comprueba nada.
    if len(NODES) != 16:
        errors.append(f"se esperaban 16 nodos, hay {len(NODES)}")
    if len(EDGES) != 20:
        errors.append(f"se esperaban 20 aristas, hay {len(EDGES)}")
    if len(LABELS) != 5:
        errors.append(f"se esperaban 5 etiquetas, hay {len(LABELS)}")
    if len(LEGEND) != 3:
        errors.append(f"se esperaban 3 lineas de leyenda, hay {len(LEGEND)}")

    # 1. Toda arista referencia nodos existentes.
    for key, (a, b, pts) in EDGES.items():
        if a not in NODES:
            errors.append(f"arista {key}: origen inexistente '{a}'")
        if b not in NODES:
            errors.append(f"arista {key}: destino inexistente '{b}'")
        if len(pts) < 2:
            errors.append(f"arista {key}: menos de dos puntos")

    # 2. Todo nodo cabe en el lienzo.
    for name, n in NODES.items():
        if not (0 <= n[0] < n[2] <= CANVAS_W and 0 <= n[1] < n[3] <= CANVAS_H):
            errors.append(f"nodo {name}: fuera del lienzo {n[:4]}")

    # 3. No hay dos nodos solapados.
    names = list(NODES)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            if overlaps(NODES[names[i]][:4], NODES[names[j]][:4]):
                errors.append(f"solape de nodos: {names[i]} / {names[j]}")

    # Zonas: no se solapan entre si y cada nodo esta dentro o fuera por completo.
    zone_keys = list(ZONES)
    for i in range(len(zone_keys)):
        for j in range(i + 1, len(zone_keys)):
            if overlaps(ZONES[zone_keys[i]], ZONES[zone_keys[j]]):
                errors.append(f"solape de zonas: {zone_keys[i]} / {zone_keys[j]}")
    for name, n in NODES.items():
        for zname, z in ZONES.items():
            r = n[:4]
            if overlaps(r, z) and not _contains(z, r):
                errors.append(f"nodo {name} cruza el borde de la zona {zname}")

    # 4 y 5. Etiquetas.
    for label in LABELS:
        key, text, lx, ly, anchor = label
        if key not in EDGES:
            errors.append(f"etiqueta '{text}': arista inexistente '{key}'")
            continue
        lr = label_rect(label)

        for name, n in NODES.items():
            if overlaps(lr, n[:4]):
                errors.append(f"etiqueta '{text}' pisa el nodo {name}")
        for zname, z in ZONES.items():
            if overlaps(lr, z) and not _contains(z, lr):
                errors.append(f"etiqueta '{text}' cruza el borde de la zona {zname}")

        # Se inserta el rectangulo antes de probar cruces: una etiqueta anclada
        # en 'start' tiene su borde izquierdo sobre la linea por construccion.
        lr_i = _inset(lr)
        a, b, pts = EDGES[key]
        for p, q in zip(pts, pts[1:]):
            if seg_hits_rect(p, q, lr_i):
                errors.append(f"etiqueta '{text}' cruza el trazo de {key}")

    # La leyenda se valida con el mismo criterio que las etiquetas.
    for text, lx, ly in LEGEND:
        lr = free_label_rect(text, lx, ly)
        for name, n in NODES.items():
            if overlaps(lr, n[:4]):
                errors.append(f"leyenda '{text[:24]}...' pisa el nodo {name}")
        for zname, z in ZONES.items():
            if overlaps(lr, z) and not _contains(z, lr):
                errors.append(f"leyenda '{text[:24]}...' cruza el borde de la zona {zname}")

    return errors


# ------------------------------------------------------------------ svg -----
def _esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _box(name, n) -> str:
    x0, y0, x1, y1, ramp, title, sub = n
    fill, stroke, dark = RAMP[ramp]
    cx = (x0 + x1) / 2
    cy = (y0 + y1) / 2
    title_y = cy - 9
    sub_y = cy + 11
    return (
        f'<g><rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" rx="10" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="1"/>\n'
        f'<text x="{cx}" y="{title_y}" fill="{dark}" font-family="Segoe UI, Arial, sans-serif" '
        f'font-size="15" font-weight="600" text-anchor="middle" dominant-baseline="central">{_esc(title)}</text>\n'
        f'<text x="{cx}" y="{sub_y}" fill="{stroke}" font-family="Segoe UI, Arial, sans-serif" '
        f'font-size="12" font-weight="400" text-anchor="middle" dominant-baseline="central">{_esc(sub)}</text></g>'
    )


def _zone(name, z) -> str:
    x0, y0, x1, y1 = z
    fill, stroke, dark = ZONE_STYLE[name]
    return (
        f'<g><rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" rx="18" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="1" stroke-dasharray="7 5"/>\n'
        f'<text x="{x0 + 16}" y="{y0 + 22}" fill="{dark}" font-family="Segoe UI, Arial, sans-serif" '
        f'font-size="12" font-weight="600" letter-spacing="0.6">{_esc(ZONE_TITLES[name])}</text></g>'
    )


def _edge(key, e) -> str:
    _, _, pts = e
    d = "M" + " L".join(f"{x} {y}" for x, y in pts)
    dash = ' stroke-dasharray="6 4"' if key in DASHED else ""
    return (f'<path d="{d}" fill="none" stroke="#5F5E5A" stroke-width="1.6" '
            f'stroke-linejoin="round" marker-end="url(#arrow)"{dash}/>')


def _label(label) -> str:
    _, text, lx, ly, anchor = label
    return (f'<text x="{lx}" y="{ly}" fill="#2C2C2A" font-family="Segoe UI, Arial, sans-serif" '
            f'font-size="12" font-weight="400" text-anchor="{anchor}">{_esc(text)}</text>')


def emit_svg() -> str:
    parts: list[str] = []
    parts.append(f'<?xml version="1.0" encoding="UTF-8"?>')
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CANVAS_W} {CANVAS_H}" '
        f'width="{CANVAS_W}" height="{CANVAS_H}" role="img" '
        f'aria-labelledby="dtitle ddesc">'
    )
    parts.append(
        '<title id="dtitle">Arquitectura del AI Software Engineering System</title>'
    )
    parts.append(
        '<desc id="ddesc">Entrada por voz o texto; el adaptador Speech-to-Text convierte '
        'audio en texto confirmado por el usuario. La API FastAPI entrega la tarea al '
        'Supervisor en LangGraph, que coordina Researcher, Coder y Reviewer sobre un '
        'worktree aislado. Las herramientas se exponen por MCP y pasan por el Policy '
        'Engine. El estado compartido permite reanudar la ejecucion y la aprobacion humana '
        'protege las acciones con efectos. La observabilidad y el proveedor de modelo son '
        'servicios externos; el Text-to-Speech es opcional.</desc>'
    )
    parts.append(
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        'markerHeight="7" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="#5F5E5A" '
        'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></marker></defs>'
    )
    parts.append(
        f'<rect x="0" y="0" width="{CANVAS_W}" height="{CANVAS_H}" fill="#FFFFFF"/>'
    )
    parts.append(
        '<text x="40" y="34" fill="#2C2C2A" font-family="Segoe UI, Arial, sans-serif" '
        'font-size="20" font-weight="600">AI Software Engineering System - Proyecto 4, Equipo 4</text>'
    )
    parts.append(
        '<text x="40" y="56" fill="#5F5E5A" font-family="Segoe UI, Arial, sans-serif" '
        'font-size="13">Agentic Workflows - Multi-Agent - MCP - Shared State - Human-in-the-Loop</text>'
    )

    for zname, z in ZONES.items():
        parts.append(_zone(zname, z))

    for key, e in EDGES.items():
        parts.append(_edge(key, e))

    for name, n in NODES.items():
        parts.append(_box(name, n))

    for label in LABELS:
        parts.append(_label(label))


    for text, lx, ly in LEGEND:
        parts.append(
            f'<text x="{lx}" y="{ly}" fill="#5F5E5A" font-family="Segoe UI, Arial, sans-serif" '
            f'font-size="12">{_esc(text)}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "docs" / "diagrama-arquitectura.svg"

    errors = validate()
    if errors:
        print("VALIDACION FALLIDA:")
        for e in errors:
            print(f"  - {e}")
        return 1

    svg = emit_svg()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg, encoding="utf-8")

    print(f"geometria OK: {len(NODES)} nodos, {len(EDGES)} aristas, "
          f"{len(LABELS)} etiquetas, {len(ZONES)} zonas")
    print(f"escrito: {out} ({len(svg)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

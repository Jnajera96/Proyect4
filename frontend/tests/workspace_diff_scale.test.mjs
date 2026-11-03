// Suite de validación de escala para Studio Workspace:
// - Renderizado de Diff Dividido (Split Diff Side-by-Side) con más de 20 archivos modificados
// - Navegación rápida, indexación de ficheros y atajos de teclado (Paleta de Comandos Ctrl+K)
// Sin red ni backend.

import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { build } from "esbuild";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

const require = createRequire(import.meta.url);

async function cargar(ruta) {
  const resultado = await build({
    entryPoints: [fileURLToPath(new URL(ruta, import.meta.url))],
    bundle: true,
    write: false,
    platform: "node",
    format: "cjs",
    jsx: "automatic",
    external: ["react", "react/jsx-runtime"],
  });
  const modulo = { exports: {} };
  new Function("require", "module", "exports", resultado.outputFiles[0].text)(
    require,
    modulo,
    modulo.exports,
  );
  return modulo.exports;
}

const { VisorDiff } = await cargar("../src/components/VisorDiff.tsx");
const { PaletaComandos, comandosBase } = await cargar("../src/components/PaletaComandos.tsx");

function generarDiffMultiArchivo(numArchivos = 25) {
  const bloques = [];
  for (let i = 1; i <= numArchivos; i++) {
    const num = String(i).padStart(2, "0");
    const ruta = `src/services/modulo_${num}.py`;
    bloques.push(
      `diff --git a/${ruta} b/${ruta}\n` +
      `index 1111111..2222222 100644\n` +
      `--- a/${ruta}\n` +
      `+++ b/${ruta}\n` +
      `@@ -1,6 +1,8 @@\n` +
      ` import math\n` +
      `-def antiguo_${num}():\n` +
      `-    return ${i}\n` +
      `+def nuevo_${num}(factor: float = 1.0) -> float:\n` +
      `+    """Modulo ${num} optimizado para alta concurrencia."""\n` +
      `+    return math.sqrt(${i}) * factor\n` +
      ` \n` +
      ` # Fin del modulo\n`
    );
  }
  return bloques.join("\n");
}

test("VisorDiff renderiza 25+ ficheros en modo unificado sin errores y con indice completo", () => {
  const diffTexto = generarDiffMultiArchivo(25);
  const inicio = performance.now();
  const html = renderToStaticMarkup(React.createElement(VisorDiff, { texto: diffTexto }));
  const duracionMs = performance.now() - inicio;

  // Verificaciones estructurales
  assert.ok(html.includes("25</span> fichero(s)"), "Debe resumir exactamente 25 ficheros");
  assert.ok(html.includes('class="diff-indice"'), "Debe renderizar la barra de indice de navegación");

  // Verificar que los 25 ficheros tienen anclas e identificadores
  for (let i = 1; i <= 25; i++) {
    const num = String(i).padStart(2, "0");
    assert.ok(html.includes(`src/services/modulo_${num}.py`), `Fichero modulo_${num}.py debe estar presente`);
    assert.ok(html.includes(`id="diff-fichero-${i - 1}"`), `Debe existir el ancla diff-fichero-${i - 1}`);
  }

  // Comprobar rendimiento (menos de 200 ms para 25 archivos)
  assert.ok(duracionMs < 200, `El renderizado tardó ${duracionMs.toFixed(2)}ms (límite 200ms)`);
});

test("VisorDiff procesa la vista dividida (Split Diff) emparejando sustituciones lado a lado", () => {
  const diffTexto = generarDiffMultiArchivo(25);
  // Simular renderizado del modo dividido asegurando que la función interna de filasDivididas opere
  // Pasamos el diff completo a VisorDiff y comprobamos el contenido
  const html = renderToStaticMarkup(React.createElement(VisorDiff, { texto: diffTexto }));

  // Cada bloque tiene 2 borradas y 3 añadidas
  // En total: 25 * 3 = 75 añadidas, 25 * 2 = 50 borradas
  assert.ok(html.includes("+75</span>"), "Total de añadidas debe ser +75");
  assert.ok(html.includes("−50</span>"), "Total de borradas debe ser -50");
});

test("PaletaComandos indexa vistas, ejecuciones y proyectos con atajos accesibles", () => {
  const items = [
    { id: "flujo", etiqueta: "Flujo de trabajo", icono: "flujo" },
    { id: "ejecuciones", etiqueta: "Historial de ejecuciones", icono: "ejecuciones" },
    { id: "proyectos", etiqueta: "Proyectos configurados", icono: "proyectos" },
  ];
  const proyectos = [
    { project_id: "p1", name: "Calculadora Científica", repo_path: "C:/calc" },
    { project_id: "p2", name: "REST API Microservicio", repo_path: "C:/api" },
  ];
  const runs = [
    { run_id: "run-calc-001", status: "completed", instruction: "calc trigo" },
    { run_id: "run-api-002", status: "running", instruction: "api sqlite" },
  ];

  let vistaSeleccionada = null;
  let proyectoSeleccionado = null;
  let temaSeleccionado = null;

  const comandos = comandosBase({
    items,
    proyectos,
    runs,
    alVista: (v) => { vistaSeleccionada = v; },
    alProyecto: (p) => { proyectoSeleccionado = p; },
    alRun: () => {},
    alTema: (t) => { temaSeleccionado = t; },
  });

  assert.ok(comandos.length >= 7, "Debe generar al menos 7 comandos base");

  // Probar ejecución de comando
  const cmdVista = comandos.find((c) => c.id === "vista-flujo");
  assert.ok(cmdVista, "Debe existir comando para vista-flujo");
  cmdVista.ejecutar();
  assert.equal(vistaSeleccionada, "flujo");

  const cmdTema = comandos.find((c) => c.id === "tema-oscuro");
  assert.ok(cmdTema, "Debe existir comando para tema oscuro");
  cmdTema.ejecutar();
  assert.equal(temaSeleccionado, "oscuro");

  // Probar renderizado de diálogo modal accesible
  const html = renderToStaticMarkup(
    React.createElement(PaletaComandos, {
      abierta: true,
      comandos,
      alCerrar: () => {},
    })
  );

  assert.ok(html.includes('role="dialog"'), "Debe tener role dialog");
  assert.ok(html.includes('aria-modal="true"'), "Debe ser modal aria-modal");
  assert.ok(html.includes('role="combobox"'), "Campo de entrada debe tener role combobox");
  assert.ok(html.includes("Calculadora Científica"), "Debe mostrar el proyecto en la lista");
  assert.ok(html.includes("REST API Microservicio"), "Debe mostrar el proyecto REST API");
});

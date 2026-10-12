/// <reference types="vite/client" />

// `contracts.json` es un artefacto generado (`tools/export_contracts.py`), no un
// modulo tipado. Se importa por su ruta y su forma se estrecha en
// `src/lib/contracts.ts` con `as const`-style derivations. La declaracion de abajo
// evita que TypeScript intente inferir un tipo enorme del literal y deja que el
// archivo de contratos sea quien imponga la forma.
declare module "*.json" {
  const valor: {
    endpoints: Record<string, unknown>;
    schemas: {
      EventKind: { enum: readonly string[] };
      RunStatus: { enum: readonly string[] };
      Intent: { enum: readonly string[] };
      ApprovalDecision: { enum: readonly string[] };
      [clave: string]: unknown;
    };
    [clave: string]: unknown;
  };
  export default valor;
}

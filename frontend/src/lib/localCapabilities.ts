import { pedir } from "./api";

export interface LocalCapabilities {
  mcp: { enabled: boolean; tools: string[]; transport: string };
  tts: { enabled: boolean; provider: string };
  observability: { local: boolean; langfuse_enabled: boolean; langfuse_configured: boolean };
}
export interface LocalTrace {
  run_id: string; trace_id: string; truncated: boolean; status: string;
  usage: { input_tokens: number; output_tokens: number; model_calls: number; used_cost: number; cost_available: boolean };
  events: { seq: number; kind: string; at: string; data: Record<string, unknown> }[];
  errors: string[]; verification_failures: string[];
}
export interface ContextGraph {
  provenance: string; truncated: boolean; graphify_integrated: boolean;
  nodes: { id: string; label: string; kind: string }[];
  edges: { source: string; target: string; kind: string }[];
  errors: { path: string; reason: string }[];
}
export const localCapabilities = {
  status: () => pedir<LocalCapabilities>("/capabilities/local"),
  trace: (run: string) => pedir<LocalTrace>(`/runs/${encodeURIComponent(run)}/observability`),
  graph: (run: string) => pedir<ContextGraph>(`/runs/${encodeURIComponent(run)}/context-graph`),
  export: (run: string) => pedir<{exported: boolean; spans: number}>(
    `/runs/${encodeURIComponent(run)}/observability/langfuse`, {method:"POST"}),
};

export function iniciarLectura(text: string, synthesis: SpeechSynthesis, utterance: SpeechSynthesisUtterance) {
  const local = synthesis.getVoices().filter(v => v.localService);
  const voice = local.find(v => v.lang.toLowerCase().startsWith("es")) ?? local[0];
  if (!voice) throw new Error("No hay voces locales instaladas. No se utilizará una voz remota.");
  if (!text.trim()) throw new Error("Todavía no hay un resultado para leer.");
  utterance.text = text.slice(0, 4000);
  utterance.voice = voice;
  utterance.lang = voice.lang;
  synthesis.cancel();
  synthesis.speak(utterance);
}

export function descargarJson(data: unknown, filename: string) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], {type:"application/json"}));
  const link = document.createElement("a"); link.href = url; link.download = filename;
  link.click(); URL.revokeObjectURL(url);
}

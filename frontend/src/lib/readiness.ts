import { pedir } from "./api";
export interface ReadinessReport {
  ready: boolean;
  checks: { code: string; ready: boolean; message: string; action: string | null }[];
}
export const readiness = {
  check: (id: string, mode: string) => pedir<ReadinessReport>(`/projects/${encodeURIComponent(id)}/readiness?mode=${encodeURIComponent(mode)}`),
  initialize: (id: string) => pedir<ReadinessReport>(`/projects/${encodeURIComponent(id)}/initialize-head`, { method: "POST" }),
};

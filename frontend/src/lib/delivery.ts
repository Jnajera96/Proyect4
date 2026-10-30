import { pedir } from "./api";

export interface LaunchGuide {
  available: boolean; kind: string; summary_es: string; launch_action: string;
  command: string; instructions: string[]; repo_path: string; entrypoint: string;
  prepared: boolean; launcher_path: string;
}
const post = (body?: unknown): RequestInit => ({ method: "POST",
  headers: { "Content-Type": "application/json" }, body: JSON.stringify(body ?? {}) });
export const delivery = {
  guide: (id: string) => pedir<LaunchGuide>(`/runs/${encodeURIComponent(id)}/launch-guide`),
  prepare: (id: string) => pedir<LaunchGuide>(`/runs/${encodeURIComponent(id)}/launch-guide/prepare`, post()),
  launch: (id: string) => pedir<LaunchGuide>(`/runs/${encodeURIComponent(id)}/launch`, post()),
  publish: (id: string, body: { repo_name: string; pat_token: string; private: boolean }) =>
    pedir<{ published: boolean; url: string }>(`/projects/${encodeURIComponent(id)}/publish-github`, post(body)),
};

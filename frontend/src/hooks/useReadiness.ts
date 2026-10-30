import { useEffect, useState } from "react";
import { useClaveApi } from "../lib/auth";
import { readiness, type ReadinessReport } from "../lib/readiness";

export function useReadiness(projectId: string, mode: string, configurationRevision = 0) {
  const key = useClaveApi();
  const [revision, setRevision] = useState(0);
  const identity = `${projectId}:${mode}:${configurationRevision}:${revision}:${key ?? ""}`;
  const [state, setState] = useState<{ identity: string; report: ReadinessReport | null; error: string }>({ identity: "", report: null, error: "" });
  useEffect(() => {
    let active = true;
    if (projectId) void readiness.check(projectId, mode).then(report => {
      if (active) setState({ identity, report, error: "" });
    }).catch(cause => { if (active) setState({ identity, report: null, error: (cause as Error).message }); });
    return () => { active = false; };
  }, [projectId, mode, identity]);
  const current = state.identity === identity;
  return {
    report: current ? state.report : null,
    error: current ? state.error : "",
    loading: Boolean(projectId) && (!current || (!state.report && !state.error)),
    recheck: () => setRevision(value => value + 1),
  };
}

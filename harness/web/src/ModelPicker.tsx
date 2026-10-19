/** Header model picker: shows the model new runs use and switches it without a restart. */

import { useAgent } from "@copilotkit/react-core/v2";
import { useEffect, useState } from "react";

import { AGENT_ID } from "./agent.ts";
import { api } from "./api.ts";
import type { ModelsResponse } from "./types.ts";

export function ModelPicker() {
  const [data, setData] = useState<ModelsResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { agent } = useAgent({ agentId: AGENT_ID });
  const running = agent.isRunning;

  useEffect(() => {
    api.models().then(setData).catch((e) => setError(String(e)));
  }, []);

  const change = async (id: string) => {
    setBusy(true);
    setError(null);
    try {
      const res = await api.setModel(id);
      setData((d) =>
        d
          ? { ...d, current: res.current, models: d.models.map((m) => ({ ...m, current: m.id === res.current })) }
          : d,
      );
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <label className="model-picker" title={error ?? "Model used for the next runs"}>
      <span className="muted">model</span>
      <select
        data-testid="model-picker"
        value={data?.current ?? ""}
        disabled={!data || busy || running}
        onChange={(e) => void change(e.target.value)}
      >
        {Object.entries(
          (data?.models ?? []).reduce<Record<string, { id: string; label: string }[]>>((groups, m) => {
            (groups[m.provider] ??= []).push(m);
            return groups;
          }, {}),
        ).map(([provider, models]) => (
          <optgroup key={provider} label={provider}>
            {models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
      {error && (
        <span className="error-text model-error" data-testid="model-error" onClick={() => setError(null)}>
          ⚠ {error.slice(0, 60)}
        </span>
      )}
    </label>
  );
}

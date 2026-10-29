/** How full the model's context is for this project.
 *
 * A long agent loop accumulates reasoning and tool results until the window is exhausted, and
 * the run then stalls or dies with a token-limit error. Showing the number makes that visible
 * before it happens. The value is an estimate (prompt size + content produced during the run);
 * the exact figure the provider reports is in the tooltip.
 */

import { useEffect, useState } from "react";

import { api } from "./api.ts";
import type { UsageInfo } from "./types.ts";

function compact(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(n >= 10_000 ? 0 : 1)}k`;
  return String(n);
}

export function ContextMeter({ design }: { design: string | null }) {
  const [usage, setUsage] = useState<UsageInfo | null>(null);

  useEffect(() => {
    if (!design) {
      setUsage(null);
      return;
    }
    let live = true;
    const load = () =>
      api
        .usage(design)
        .then((data) => live && setUsage(data))
        .catch(() => undefined);
    void load();
    // Cheap enough to poll; the run itself updates only when it finishes.
    const timer = setInterval(load, 10_000);
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, [design]);

  if (!design || !usage) return null;

  const used = usage.context_estimate;
  const window = usage.context_window;
  const percent = usage.percent;
  const title = [
    `model: ${usage.model}`,
    `output limit: ${compact(usage.max_output_tokens)} tokens`,
    window ? `context window: ${compact(window)} tokens` : "context window: not advertised by the gateway",
    used ? `in context: ~${used.toLocaleString()} tokens` : "in context: unknown until a run starts",
    usage.last_run?.input_tokens
      ? `last run: ${usage.last_run.input_tokens.toLocaleString()} in / ${(usage.last_run.output_tokens ?? 0).toLocaleString()} out over ${usage.last_run.requests ?? "?"} requests`
      : "",
  ]
    .filter(Boolean)
    .join("\n");

  const tone = percent == null ? "" : percent >= 85 ? "danger" : percent >= 60 ? "warn" : "";

  return (
    <span className={`ctx-meter ${tone}`} data-testid="ctx-meter" title={title}>
      ctx {used ? `~${compact(used)}` : "—"}
      {window ? ` / ${compact(window)}` : ""}
      {percent != null ? ` (${percent}%)` : ""}
    </span>
  );
}

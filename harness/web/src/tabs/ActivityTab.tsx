/** Activity tab: replay any run (UI or CLI) as a transcript, tail the active one live. */

import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "../api.ts";
import { refreshRuns, useHarness } from "../store.ts";
import type { RunEvent, RunInfo } from "../types.ts";

/** Extract readable text from an AG-UI event (camelCase, as logged). */
function eventText(ev: RunEvent): { kind: string; text?: string; image?: string; args?: string; name?: string; level: "info" | "warn" | "error" } {
  const e = ev.event ?? {};
  const type = String(e.type ?? ev.type ?? "");
  switch (type) {
    case "TEXT_MESSAGE_CONTENT": {
      const delta = String(e.delta ?? "");
      return { kind: "text", text: delta, level: "info" };
    }
    case "THINKING_START":
      return { kind: "thinking", level: "info" };
    case "THINKING_CONTENT":
      return { kind: "thinking", text: String(e.delta ?? ""), level: "info" };
    case "TOOL_CALL_START":
      return { kind: "tool", name: String(e.name ?? e.toolCallName ?? ""), level: "info" };
    case "TOOL_CALL_ARGS":
      return { kind: "tool-args", args: String(e.delta ?? ""), level: "info" };
    case "TOOL_CALL_RESULT": {
      let text = String(e.content ?? "");
      let image: string | undefined;
      try {
        const parsed = JSON.parse(text);
        if (Array.isArray(parsed)) {
          const meta = parsed.find((p) => typeof p === "string");
          if (meta) {
            const m = JSON.parse(meta as string);
            if (m?.url) text = m.caption ?? m.url;
          }
          const bin = parsed.find((p) => p?.data && p?.media_type?.startsWith?.("image/"));
          if (bin) image = `data:${bin.media_type};base64,${String(bin.data).replace(/-/g, "+").replace(/_/g, "/")}`;
        }
      } catch {
        // keep raw text
      }
      return { kind: "tool-result", text: text.length > 500 ? text.slice(0, 500) + "…" : text, image, level: "info" };
    }
    case "CUSTOM":
      return { kind: `custom:${e.name ?? ""}`, text: JSON.stringify(e.value ?? e.messages ?? "").slice(0, 300), level: "info" };
    case "RUN_ERROR":
      return { kind: "error", text: String(e.message ?? ""), level: "error" };
    case "RUN_STARTED":
      return { kind: "run-start", text: e.prompt ? String(e.prompt).slice(0, 200) : undefined, level: "info" };
    case "RUN_FINISHED":
      return { kind: "run-finished", text: JSON.stringify(e.outcome ?? {}).slice(0, 200), level: "info" };
    case "STATE_SNAPSHOT":
    case "STATE_DELTA":
      return { kind: type.toLowerCase(), level: "info" };
    default:
      return { kind: type.toLowerCase() || "event", level: "info" };
  }
}

export function ActivityTab({ activeRunId }: { activeRunId: string | null }) {
  const h = useHarness();
  const [selected, setSelected] = useState<string | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const afterRef = useRef(0);

  const runId = selected ?? activeRunId ?? h.runs?.[0]?.run_id ?? null;
  const run: RunInfo | undefined = (h.runs ?? []).find((r) => r.run_id === runId);

  const loadAll = useCallback(async (id: string) => {
    afterRef.current = 0;
    setEvents([]);
    const all = await api.runEvents(id, 0);
    setEvents(all);
    afterRef.current = all.length ? all[all.length - 1].seq : 0;
  }, []);

  // Poll the active run for new events.
  useEffect(() => {
    if (!runId) return;
    let stop = false;
    const active = run?.status === "running" || (!selected && activeRunId === runId && run?.status === "running");
    let timer: ReturnType<typeof setTimeout> | null = null;
    const tick = async () => {
      try {
        const fresh = await api.runEvents(runId, afterRef.current);
        if (!stop && fresh.length) {
          afterRef.current = fresh[fresh.length - 1].seq;
          // loadAll can race with tick; dedup by seq so keys stay unique
          setEvents((prev) => {
            const seen = new Set(prev.map((e) => e.seq));
            return [...prev, ...fresh.filter((e) => !seen.has(e.seq))];
          });
        }
      } catch {
        // run not finished being written; retry
      }
      if (!stop) timer = setTimeout(tick, active ? 1000 : 3000);
    };
    void tick();
    return () => {
      stop = true;
      if (timer) clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId, run?.status, activeRunId, selected]);

  useEffect(() => {
    if (runId && events.length === 0) void loadAll(runId);
  }, [runId, events.length, loadAll]);

  return (
    <div className="activity-tab">
      <div className="run-list" data-testid="run-list">
        {(h.runs ?? []).map((r) => (
          <button
            key={r.run_id}
            className={`run-row ${r.run_id === runId ? "selected" : ""}`}
            data-testid={`run-${r.source}-${r.status}`}
            onClick={() => {
              setSelected(r.run_id);
              setEvents([]);
              afterRef.current = 0;
              void loadAll(r.run_id);
            }}
          >
            <span className={`run-dot run-${r.status}`} />
            <span className="run-info">
              <b>{r.source}</b> {r.prompt.slice(0, 60) || "(no prompt)"}
              <span className="muted"> · {new Date(r.started_at * 1000).toLocaleTimeString()} · {r.event_count} events</span>
            </span>
          </button>
        ))}
        {(h.runs ?? []).length === 0 && <div className="muted">No runs yet.</div>}
      </div>
      <div className="transcript" data-testid="transcript">
        {run && (
          <div className="transcript-head">
            run {run.run_id.slice(0, 8)} · {run.status} · {run.model}
            {run.error ? ` · error: ${run.error}` : ""}
          </div>
        )}
        {events.map((ev) => {
          const t = eventText(ev);
          return (
            <div key={ev.seq} className={`transcript-row tr-${t.level}`} data-testid={`transcript-${t.kind}`}>
              <span className="tr-kind">{t.kind}</span>
              <span className="tr-body">
                {t.text}
                {t.image && <img className="transcript-image" src={t.image} alt="tool render" />}
              </span>
            </div>
          );
        })}
        {events.length === 0 && runId && <div className="muted">Loading events…</div>}
      </div>
    </div>
  );
}

export async function refreshActivity() {
  await refreshRuns();
}

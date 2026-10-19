/** Agent tab: the CopilotKit chat transcript, goal-loop controls and ONE composer.
 *
 *  CopilotKit's own input is hidden (see app.css) — the composer below is the single place to
 *  type. It sends a normal chat message when idle and steers the live run when one is active
 *  (`POST /steer` through the agent bus), so there is no duplicated input box.
 */

import type { ReactNode } from "react";
import { useAgent } from "@copilotkit/react-core/v2";
import { useCallback, useState } from "react";

import { AGENT_ID } from "../agent.ts";
import { sendAgentMessage } from "../agentBus.ts";
import { useHarness } from "../store.ts";

export function AgentTab({ chat, onEditGoal }: { chat: ReactNode; onEditGoal: () => void }) {
  const [draft, setDraft] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "queued">("idle");
  const { agent } = useAgent({ agentId: AGENT_ID });
  const h = useHarness();
  const running = agent.isRunning;
  const goalSummary = h.goal?.summary?.trim();
  const criterionCount = h.goal?.criteria?.length ?? 0;

  const send = useCallback(async () => {
    const message = draft.trim();
    if (!message) return;
    setState("sending");
    try {
      await sendAgentMessage(message);
      setDraft("");
      if (running) {
        setState("queued");
        setTimeout(() => setState("idle"), 4000);
      } else {
        setState("idle");
      }
    } catch {
      setState("idle");
    }
  }, [draft, running]);

  return (
    <div className="agent-tab">
      <div className="agent-controls">
        <button
          className="run-goal-btn"
          data-testid="run-goal"
          disabled={running}
          title={
            running
              ? "A run is active — stop it before starting the goal loop"
              : 'Sends "Work toward the goal; stop when every criterion passes." with the goal loop on'
          }
          onClick={() => void sendAgentMessage("Work toward the goal; stop when every criterion passes.").catch(() => undefined)}
        >
          ▶ Run goal
        </button>
        {running && (
          <span className="composer-mode" data-testid="composer-mode">
            run active · typing steers it
          </span>
        )}
        <button className="goal-chip" data-testid="agent-goal-chip" onClick={onEditGoal} title="Edit the goal the loop checks">
          {goalSummary ? `🎯 ${goalSummary.slice(0, 48)}${goalSummary.length > 48 ? "…" : ""}` : "🎯 no goal set — add one"}
          {criterionCount > 0 && <span className="goal-chip-count">{criterionCount}</span>}
        </button>
      </div>
      <div className="chat-holder" data-testid="chat-holder">
        {chat}
      </div>
      <div className="composer-bar" data-testid="composer-bar" data-mode={running ? "steer" : "chat"}>
        <input
          data-testid="composer-input"
          placeholder={running ? "Steer the running agent…" : "Ask the KiCad agent…"}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void send();
          }}
        />
        <button
          className="composer-send"
          data-testid="composer-send"
          disabled={!draft.trim() || state === "sending"}
          title={running ? "Queue a steering message for the running agent" : "Send a message to the agent"}
          onClick={() => void send()}
        >
          {running ? "Steer" : "Send"}
        </button>
        {state !== "idle" && (
          <span className="steer-status" data-testid="composer-status">
            {state === "sending" ? "sending…" : "queued ✓"}
          </span>
        )}
      </div>
    </div>
  );
}

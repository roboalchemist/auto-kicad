/** Goal tab: edit the goal as a form (summary + criterion rows), see live results, run the loop.
 *
 *  The raw JSON editor is still available under "Advanced", but a goal no longer requires writing
 *  JSON by hand.
 */

import { useEffect, useState } from "react";

import { sendAgentMessage } from "../agentBus.ts";
import { refreshGoal, saveGoal, useHarness } from "../store.ts";
import type { Goal, GoalCriterion } from "../types.ts";

type FieldType = "number" | "text" | "region" | "severities";

interface Field {
  key: string;
  label: string;
  type: FieldType;
  step?: number;
}

interface CriterionSpec {
  label: string;
  docs: string;
  fields: Field[];
  defaults: Record<string, unknown>;
}

/** Mirrors kicad_harness/agent/goal.py CRITERIA. */
export const CRITERION_SPECS: Record<string, CriterionSpec> = {
  drc_errors: {
    label: "DRC errors",
    docs: "KiCad DRC error count",
    fields: [{ key: "max", label: "at most", type: "number", step: 1 }],
    defaults: { max: 0 },
  },
  drc_warnings: {
    label: "DRC warnings",
    docs: "KiCad DRC warning count",
    fields: [{ key: "max", label: "at most", type: "number", step: 1 }],
    defaults: { max: 0 },
  },
  unconnected: {
    label: "Unconnected items",
    docs: "ratsnest / unrouted connections",
    fields: [{ key: "max", label: "at most", type: "number", step: 1 }],
    defaults: { max: 0 },
  },
  board_size: {
    label: "Board size",
    docs: "board outline fits a rectangle",
    fields: [
      { key: "max_w", label: "max width (mm)", type: "number", step: 0.5 },
      { key: "max_h", label: "max height (mm)", type: "number", step: 0.5 },
    ],
    defaults: { max_w: 30, max_h: 25 },
  },
  edge_clearance: {
    label: "Edge clearance",
    docs: "every pad keeps a margin from the board edge",
    fields: [{ key: "min_mm", label: "min mm", type: "number", step: 0.1 }],
    defaults: { min_mm: 0.3 },
  },
  max_distance: {
    label: "Max distance",
    docs: "one entity must stay close to another",
    fields: [
      { key: "a", label: "entity", type: "text" },
      { key: "b", label: "within mm of", type: "text" },
      { key: "max_mm", label: "max mm", type: "number", step: 0.1 },
    ],
    defaults: { a: "U1", b: "D1", max_mm: 5 },
  },
  min_distance: {
    label: "Min distance",
    docs: "one entity must stay away from another",
    fields: [
      { key: "a", label: "entity", type: "text" },
      { key: "b", label: "at least mm from", type: "text" },
      { key: "min_mm", label: "min mm", type: "number", step: 0.1 },
    ],
    defaults: { a: "U1", b: "D1", min_mm: 1 },
  },
  within_region: {
    label: "Inside a region",
    docs: "a footprint must sit entirely inside a rectangle",
    fields: [
      { key: "ref", label: "reference", type: "text" },
      { key: "region", label: "region x1,y1,x2,y2 (mm)", type: "region" },
    ],
    defaults: { ref: "D1", region: [0, 0, 10, 10] },
  },
  open_threads: {
    label: "Open review comments",
    docs: "no more than N open review threads",
    fields: [
      { key: "max", label: "at most", type: "number", step: 1 },
      { key: "severities", label: "only severities (optional)", type: "severities" },
    ],
    defaults: { max: 0 },
  },
};

const PRESETS: { label: string; criteria: GoalCriterion[] }[] = [
  {
    label: "Clean DRC + fully routed",
    criteria: [
      { id: "drc", type: "drc_errors", max: 0 },
      { id: "routed", type: "unconnected", max: 0 },
    ],
  },
  { label: "Board ≤ 30 × 25 mm", criteria: [{ id: "size", type: "board_size", max_w: 30, max_h: 25 }] },
  { label: "No open must-fix comments", criteria: [{ id: "review", type: "open_threads", max: 0, severities: ["must_fix"] }] },
];

function criterionId(type: string, existing: GoalCriterion[]): string {
  const base = type.replace(/_(errors|warnings)$/, "").replace(/_/g, "-");
  let id = base;
  let n = 2;
  while (existing.some((c) => c.id === id)) id = `${base}-${n++}`;
  return id;
}

function draft(type: string, existing: GoalCriterion[]): GoalCriterion {
  const spec = CRITERION_SPECS[type];
  return { id: criterionId(type, existing), type: type as GoalCriterion["type"], ...spec.defaults } as GoalCriterion;
}

export function GoalTab() {
  const h = useHarness();
  const [summary, setSummary] = useState("");
  const [criteria, setCriteria] = useState<GoalCriterion[]>([]);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState("drc_errors");
  const [showJson, setShowJson] = useState(false);
  const [manual, setManual] = useState(false);
  const [deriving, setDeriving] = useState(false);

  // Load the stored goal into the form (until the user starts editing).
  const goal = h.goal;
  useEffect(() => {
    if (dirty || !goal) return;
    setSummary(goal.summary ?? "");
    setCriteria((goal.criteria ?? []) as GoalCriterion[]);
  }, [goal, dirty]);

  const touch = () => setDirty(true);

  const update = (index: number, patch: Record<string, unknown>) => {
    setCriteria((prev) => prev.map((c, i) => (i === index ? ({ ...c, ...patch } as GoalCriterion) : c)));
    touch();
  };

  const changeType = (index: number, type: string) => {
    setCriteria((prev) => {
      const rest = prev.filter((_, i) => i !== index);
      return prev.map((c, i) => (i === index ? draft(type, rest) : c));
    });
    touch();
  };

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      if (!criteria.length) throw new Error("add at least one criterion");
      const next: Goal = { ...(h.goal ?? {}), summary: summary.trim(), criteria };
      await saveGoal(next);
      await refreshGoal();
      setDirty(false);
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setSaving(false);
    }
  };

  const derive = async () => {
    const text = summary.trim();
    if (!text) {
      setError("describe the goal first");
      return;
    }
    setDeriving(true);
    setError(null);
    try {
      await sendAgentMessage(
        `Set up the goal for this design: "${text}". ` +
          "Inspect the board, then call set_goal with that summary and the machine-checkable criteria " +
          "that capture it (DRC, routing, distances/regions/size as appropriate), and finish with check.",
      );
      setDirty(false);
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setDeriving(false);
    }
  };

  const saved = (h.goal?.criteria ?? []) as GoalCriterion[];
  const live = h.agentGoal?.criteria?.length ? h.agentGoal.criteria : h.goalStatus?.criteria ?? [];

  return (
    <div className="goal-tab">
      <div className="goal-summary" data-testid="goal-summary">
        <div className="section-title">What should the agent achieve?</div>
        <textarea
          className="goal-summary-input"
          data-testid="goal-summary-input"
          placeholder="e.g. Move D1 to the left edge so it is visible from the side, keep every net routed and DRC-clean."
          rows={2}
          value={summary}
          onChange={(e) => {
            setSummary(e.target.value);
            touch();
          }}
        />
        <div className={`goal-met ${h.goalStatus?.met ? "badge-ok" : "badge-warn"}`} data-testid="goal-met">
          {h.goalStatus ? (h.goalStatus.met ? "goal met ✓" : "goal not met") : "not evaluated yet"}
        </div>
      </div>

      <div className="goal-primary-actions">
        <button className="run-goal-btn" data-testid="goal-derive" disabled={deriving || !summary.trim()} onClick={() => void derive()}>
          {deriving ? "asking the agent…" : "Let the agent define the criteria"}
        </button>
        <button className="secondary" data-testid="goal-save-summary" disabled={saving || !dirty} onClick={() => void save()}>
          {saving ? "saving…" : "Save goal"}
        </button>
        <button className="link" data-testid="goal-manual-toggle" onClick={() => setManual((m) => !m)}>
          {manual ? "hide manual criteria" : "edit criteria manually"}
        </button>
      </div>

      <div className="section-title">Criteria</div>
      {!manual && (
        <div className="criterion-chips" data-testid="criterion-summary">
          {!h.goal && <span className="muted">loading the goal…</span>}
          {h.goal && saved.length === 0 && (
            <span className="muted">No criteria yet — describe the goal and let the agent define them.</span>
          )}
          {saved.map((c) => (
            <span key={c.id} className="ref-chip" data-testid={`saved-criterion-${c.id}`}>
              {CRITERION_SPECS[c.type]?.label ?? c.type}
              {": "}
              {Object.entries(c)
                .filter(([k]) => !["id", "type"].includes(k))
                .map(([k, v]) => `${k}=${Array.isArray(v) ? v.join(",") : v}`)
                .join(" ")}
            </span>
          ))}
        </div>
      )}
      {manual && (
      <>
      <div className="criterion-list" data-testid="criterion-editor">
        {criteria.map((c, i) => {
          const spec = CRITERION_SPECS[c.type] ?? null;
          return (
            <div className="criterion-row" key={`${c.id}-${i}`} data-testid={`criterion-${i}`}>
              <div className="criterion-head">
                <select
                  data-testid={`criterion-type-${i}`}
                  value={c.type}
                  onChange={(e) => changeType(i, e.target.value)}
                >
                  {Object.entries(CRITERION_SPECS).map(([type, s]) => (
                    <option key={type} value={type}>
                      {s.label}
                    </option>
                  ))}
                </select>
                <span className="muted criterion-docs">{spec?.docs}</span>
                <button
                  className="link"
                  data-testid={`criterion-remove-${i}`}
                  onClick={() => {
                    setCriteria((prev) => prev.filter((_, j) => j !== i));
                    touch();
                  }}
                >
                  remove
                </button>
              </div>
              <div className="criterion-fields">
                {(spec?.fields ?? []).map((field) => (
                  <label key={field.key} className="criterion-field">
                    <span className="muted">{field.label}</span>
                    {field.type === "region" ? (
                      <span className="region-inputs">
                        {[0, 1, 2, 3].map((k) => (
                          <input
                            key={k}
                            type="number"
                            step={0.5}
                            data-testid={`criterion-${i}-region-${k}`}
                            value={(Array.isArray(c.region) ? c.region[k] : 0) ?? 0}
                            onChange={(e) => {
                              const region = [...(Array.isArray(c.region) ? c.region : [0, 0, 0, 0])];
                              region[k] = Number(e.target.value);
                              update(i, { region });
                            }}
                          />
                        ))}
                      </span>
                    ) : field.type === "severities" ? (
                      <input
                        type="text"
                        placeholder="must_fix"
                        data-testid={`criterion-${i}-${field.key}`}
                        value={Array.isArray(c.severities) ? c.severities.join(",") : ""}
                        onChange={(e) =>
                          update(i, {
                            severities: e.target.value
                              ? e.target.value.split(",").map((x) => x.trim()).filter(Boolean)
                              : undefined,
                          })
                        }
                      />
                    ) : (
                      <input
                        type={field.type === "number" ? "number" : "text"}
                        step={field.step}
                        data-testid={`criterion-${i}-${field.key}`}
                        value={String((c as unknown as Record<string, unknown>)[field.key] ?? "")}
                        onChange={(e) =>
                          update(i, {
                            [field.key]: field.type === "number" ? Number(e.target.value) : e.target.value,
                          })
                        }
                      />
                    )}
                  </label>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      <div className="criterion-add">
        <select data-testid="criterion-new-type" value={adding} onChange={(e) => setAdding(e.target.value)}>
          {Object.entries(CRITERION_SPECS).map(([type, s]) => (
            <option key={type} value={type}>
              {s.label}
            </option>
          ))}
        </select>
        <button
          className="secondary"
          data-testid="criterion-add"
          onClick={() => {
            setCriteria((prev) => [...prev, draft(adding, prev)]);
            touch();
          }}
        >
          + Add criterion
        </button>
        {PRESETS.map((preset) => (
          <button
            key={preset.label}
            className="link"
            data-testid={`preset-${preset.label.split(" ")[0].toLowerCase()}`}
            onClick={() => {
              setCriteria((prev) => [...prev, ...preset.criteria.map((c) => ({ ...c, id: criterionId(c.type, prev) }))]);
              touch();
            }}
          >
            {preset.label}
          </button>
        ))}
      </div>
      </>
      )}

      {error && (
        <div className="error-text" data-testid="goal-error">
          {error}
        </div>
      )}
      <div className="goal-actions">
        <button className="run-goal-btn" data-testid="goal-save" disabled={saving || !dirty} onClick={() => void save()}>
          {saving ? "saving…" : dirty ? "Save goal" : "Saved"}
        </button>
        <button
          className="secondary"
          data-testid="goal-reset"
          disabled={!dirty}
          onClick={() => {
            setDirty(false);
            setError(null);
          }}
        >
          Reset
        </button>
        <button
          className="run-goal-btn"
          data-testid="run-goal-loop"
          onClick={() => void sendAgentMessage("Work toward the goal; stop when every criterion passes.").catch(() => undefined)}
        >
          ▶ Run goal loop
        </button>
      </div>

      <div className="section-title">Criteria (live)</div>
      <table className="criteria-table" data-testid="goal-criteria">
        <tbody>
          {live.map((c) => (
            <tr key={c.id} className={c.passed === false ? "crit-fail" : "crit-pass"}>
              <td>{c.passed === false ? "✗" : c.passed ? "✓" : "–"}</td>
              <td>{c.id}</td>
              <td>{c.detail}</td>
            </tr>
          ))}
          {live.length === 0 && (
            <tr>
              <td className="muted">No evaluation yet — run `check` in the chat or start the goal loop.</td>
            </tr>
          )}
        </tbody>
      </table>

      <details className="goal-advanced" onToggle={(e) => setShowJson((e.target as HTMLDetailsElement).open)}>
        <summary>Advanced: goal JSON</summary>
        {showJson && (
          <textarea
            className="goal-editor"
            data-testid="goal-editor"
            value={JSON.stringify({ ...(h.goal ?? {}), summary, criteria }, null, 2)}
            rows={14}
            onChange={(e) => {
              try {
                const parsed = JSON.parse(e.target.value) as Goal;
                setSummary(parsed.summary ?? "");
                setCriteria((parsed.criteria ?? []) as GoalCriterion[]);
                setDirty(true);
                setError(null);
              } catch {
                setError("JSON is not valid yet");
              }
            }}
          />
        )}
      </details>
    </div>
  );
}

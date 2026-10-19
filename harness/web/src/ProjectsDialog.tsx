/** Project selector: every design with a thumbnail, plus creation from an upload or the demo fixture. */

import { useEffect, useRef, useState } from "react";

import { api } from "./api.ts";
import { refreshDesigns, selectDesign, useHarness } from "./store.ts";
import type { DesignInfo, Goal } from "./types.ts";

function ago(seconds?: number | null): string {
  if (!seconds) return "";
  const delta = Math.max(0, Date.now() / 1000 - seconds);
  if (delta < 90) return "just now";
  if (delta < 3600) return `${Math.round(delta / 60)} min ago`;
  if (delta < 86400) return `${Math.round(delta / 3600)} h ago`;
  return `${Math.round(delta / 86400)} d ago`;
}

export function ProjectsDialog({ onClose }: { onClose: () => void }) {
  const h = useHarness();
  const [items, setItems] = useState<DesignInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [summary, setSummary] = useState("");
  const [text, setText] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [useFixture, setUseFixture] = useState(true);
  const [creating, setCreating] = useState(false);
  const fileRef = useRef<HTMLInputElement | null>(null);

  const load = () => api.designs().then(setItems).catch((e) => setError(String(e)));
  useEffect(() => {
    void load();
    void refreshDesigns();
  }, []);

  const pickFile = async (file: File | null) => {
    if (!file) {
      setText(null);
      setFileName(null);
      return;
    }
    setText(await file.text());
    setFileName(file.name);
    setUseFixture(false);
    if (!name) setName(file.name.replace(/\.kicad_pcb$/i, "").replace(/[^A-Za-z0-9_.-]+/g, "-").slice(0, 40));
  };

  const create = async () => {
    if (!name.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const goal: Goal | undefined = summary.trim()
        ? {
            summary: summary.trim(),
            criteria: [
              { id: "drc", type: "drc_errors", max: 0 },
              { id: "routed", type: "unconnected", max: 0 },
            ],
          }
        : undefined;
      await api.createDesign({
        name: name.trim(),
        board_text: text ?? undefined,
        from_fixture: text ? undefined : useFixture,
        goal,
      });
      await refreshDesigns();
      await selectDesign(name.trim());
      onClose();
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose} data-testid="projects-dialog">
      <div className="modal projects-modal" onClick={(e) => e.stopPropagation()}>
        <div className="projects-head">
          <b>Projects</b>
          <button className="link" onClick={onClose}>
            close
          </button>
        </div>

        <div className="projects-list" data-testid="projects-list">
          {(items.length ? items : h.designs ?? []).map((d) => (
            <button
              key={d.name}
              className={`project-card ${d.name === h.designName ? "current" : ""}`}
              data-testid={`project-${d.name}`}
              onClick={() => {
                void selectDesign(d.name);
                onClose();
              }}
            >
              {d.thumbnail ? (
                <img className="project-thumb" src={d.thumbnail} alt={`${d.name} board`} loading="lazy" />
              ) : (
                <span className="project-thumb empty" />
              )}
              <span className="project-meta">
                <b>{d.name}</b>
                <span className="muted">
                  {d.branch} @ {(d.head ?? "").slice(0, 8) || "—"} · {ago(d.updated_at)}
                </span>
                <span className="project-subject">{d.latest?.subject ?? "no versions yet"}</span>
                {d.goal_summary && <span className="project-goal">{d.goal_summary}</span>}
              </span>
              {d.name === h.designName && <span className="badge badge-ok">current</span>}
            </button>
          ))}
        </div>

        <div className="project-new">
          <div className="section-title">New project</div>
          <div className="project-form">
            <input
              data-testid="new-project-name"
              placeholder="project name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <input
              data-testid="new-project-goal"
              placeholder="goal summary (optional)"
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
            />
            <label className="toggle">
              <input type="checkbox" checked={useFixture} onChange={(e) => setUseFixture(e.target.checked)} />
              start from the demo board
            </label>
            <button className="secondary" onClick={() => fileRef.current?.click()} data-testid="new-project-file">
              {fileName ? `board: ${fileName}` : "upload .kicad_pcb…"}
            </button>
            <input
              ref={fileRef}
              type="file"
              accept=".kicad_pcb"
              style={{ display: "none" }}
              onChange={(e) => void pickFile(e.target.files?.[0] ?? null)}
            />
            <button
              className="run-goal-btn"
              data-testid="new-project-create"
              disabled={!name.trim() || creating}
              onClick={() => void create()}
            >
              {creating ? "creating…" : "Create project"}
            </button>
          </div>
          {error && (
            <div className="error-text" data-testid="new-project-error">
              {error.slice(0, 200)}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function ProjectsButton() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button className="projects-btn" data-testid="projects-open" onClick={() => setOpen(true)} title="All projects">
        Projects
      </button>
      {open && <ProjectsDialog onClose={() => setOpen(false)} />}
    </>
  );
}
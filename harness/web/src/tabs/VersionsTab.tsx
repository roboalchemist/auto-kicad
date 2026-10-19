/** Versions tab: branch timeline with view / compare / restore / branch-from-here. */

import { useEffect, useMemo, useState } from "react";

import { api } from "../api.ts";
import { refreshVersions, setRev, setStore, useHarness } from "../store.ts";
import type { VersionInfo, VersionSummary } from "../types.ts";

function timeAgo(unix: number): string {
  const s = Date.now() / 1000 - unix;
  if (s < 90) return `${Math.max(1, Math.round(s))}s ago`;
  if (s < 5400) return `${Math.round(s / 60)}m ago`;
  if (s < 172800) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
}

export function VersionsTab() {
  const h = useHarness();
  const [branch, setBranch] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [branchName, setBranchName] = useState<string | null>(null);

  const currentBranch = branch || h.design?.branch || "main";
  const versions = useMemo(() => (h.versions ?? []).filter((v) => v.branch === currentBranch), [h.versions, currentBranch]);
  const threadsBySha = useMemo(() => {
    const map = new Map<string, number[]>();
    for (const t of h.threads ?? []) {
      const sha = t.created_sha;
      map.set(sha, [...(map.get(sha) ?? []), t.number]);
    }
    return map;
  }, [h.threads]);

  const act = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="versions-tab">
      <div className="branch-row">
        <label>
          Branch{" "}
          <select
            value={currentBranch}
            data-testid="branch-select"
            onChange={(e) => {
              const name = e.target.value;
              setBranch(name);
              if (name !== h.design?.branch) void act(() => api.switchBranch(h.designName!, name).then(() => setRev("working")));
            }}
          >
            {(h.branches ?? []).map((b) => (
              <option key={b.name} value={b.name}>
                {b.name}
                {b.current ? " (current)" : ""}
              </option>
            ))}
          </select>
        </label>
        {h.design?.dirty && <span className="chip chip-sm">dirty working copy</span>}
      </div>
      {error && <div className="error-text">{error}</div>}
      <div className="version-list" data-testid="version-list">
        {versions.map((v, i) => (
          <VersionRow
            key={v.sha}
            v={v}
            design={h.designName!}
            isHead={i === 0}
            viewing={h.rev === v.sha}
            threadNums={threadsBySha.get(v.sha) ?? []}
            busy={busy}
            onView={() => void act(() => setRev(v.sha))}
            onCompare={() =>
              void act(async () => {
                const parent = versions[i + 1]?.sha ?? "working";
                const diff = await api.diff(h.designName!, v.sha === "working" ? "working" : v.sha, parent === v.sha ? "working" : parent);
                // setRev clears overlay state, so navigate first and set the diff after
                await setRev(v.sha);
                setStore({ diff, diffVs: `vs ${parent.slice(0, 8)}` });
              })
            }
            onRestore={() =>
              void act(async () => {
                await api.restore(h.designName!, v.sha);
                await refreshVersions();
                await setRev("working");
              })
            }
            onBranch={() => setBranchName(v.sha)}
          />
        ))}
        {versions.length === 0 && <div className="muted">No versions on this branch.</div>}
      </div>
      {branchName && (
        <div className="modal-backdrop" onClick={() => setBranchName(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div>Branch from {branchName.slice(0, 8)}</div>
            <input
              placeholder="branch name"
              data-testid="branch-name-input"
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.target as HTMLInputElement).value.trim()) {
                  const name = (e.target as HTMLInputElement).value.trim();
                  setBranchName(null);
                  void act(() => api.createBranch(h.designName!, name, branchName).then(() => setRev("working")));
                }
              }}
            />
            <button
              className="secondary"
              onClick={() => {
                const input = document.querySelector<HTMLInputElement>("[data-testid=branch-name-input]");
                if (input?.value.trim()) {
                  const name = input.value.trim();
                  setBranchName(null);
                  void act(() => api.createBranch(h.designName!, name, branchName).then(() => setRev("working")));
                }
              }}
            >
              Create
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/** Lazily fetch the diff + few-word LLM note for one version (server caches it). */
function VersionChanges({ design, sha, onShowDiff }: { design: string; sha: string; onShowDiff: () => void }) {
  const [data, setData] = useState<VersionSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    api
      .versionSummary(design, sha)
      .then((d) => alive && setData(d))
      .catch((e) => alive && setError(String(e instanceof Error ? e.message : e)));
    return () => {
      alive = false;
    };
  }, [design, sha]);

  if (error) {
    return (
      <div className="version-changes error-text" data-testid="version-changes">
        {error.slice(0, 160)}
      </div>
    );
  }
  if (!data) {
    return (
      <div className="version-changes muted" data-testid="version-changes">
        summarising changes…
      </div>
    );
  }
  const { counts, diff } = data;
  const changed = [...(diff.moved ?? []), ...(diff.added ?? []), ...(diff.removed ?? [])].slice(0, 6);
  return (
    <div className="version-changes" data-testid="version-changes">
      <div className="version-summary" data-testid="version-summary">
        {data.summary ? `“${data.summary}”` : data.error ? `summary unavailable: ${data.error}` : "no summary"}
      </div>
      <div className="version-counts">
        <span className="delta added">+{counts.added}</span>
        <span className="delta removed">−{counts.removed}</span>
        <span className="delta moved">↔{counts.moved}</span>
        {counts.silkscreen > 0 && <span className="delta silk">silk {counts.silkscreen}</span>}
        {counts.outline > 0 && <span className="delta outline">outline</span>}
        {counts.net_changed > 0 && <span className="delta net">net↺{counts.net_changed}</span>}
        {!data.parent && <span className="muted">initial import</span>}
      </div>
      <div className="version-changed-refs">
        {diff.outline && (
          <span className="ref-chip ref-outline">
            outline {diff.outline.from[0]}×{diff.outline.from[1]} → {diff.outline.to[0]}×{diff.outline.to[1]}
          </span>
        )}
        {changed.map((e, i) => (
          <span key={`${e.uuid ?? i}`} className={`ref-chip ref-${e.kind}`}>
            {e.ref ?? e.net ?? e.kind}
            {e.pad ? `.${e.pad}` : ""}
          </span>
        ))}
      </div>
      <button className="link" onClick={onShowDiff} disabled={!data.parent} title="Show this change as an overlay on the board">
        show diff on board
      </button>
    </div>
  );
}

function VersionRow({
  v,
  design,
  isHead,
  viewing,
  threadNums,
  busy,
  onView,
  onCompare,
  onRestore,
  onBranch,
}: {
  v: VersionInfo;
  design: string;
  isHead: boolean;
  viewing: boolean;
  threadNums: number[];
  busy: boolean;
  onView: () => void;
  onCompare: () => void;
  onRestore: () => void;
  onBranch: () => void;
}) {
  const m = v.metrics;
  const [openChanges, setOpenChanges] = useState(false);
  return (
    <div className={`version-row ${viewing ? "viewing" : ""}`} data-testid={`version-${v.short}`} data-head={isHead}>
      <div className="version-main">
        {v.thumbnail ? (
          <img className="version-thumb" src={v.thumbnail} alt="" loading="lazy" data-testid={`version-thumb-${v.short}`} />
        ) : (
          <span className="version-thumb empty" />
        )}
        <span className={`author-dot author-${v.author}`} title={v.author} />
        <div className="version-text">
          <div className="version-subject">
            {v.subject} {isHead && <span className="chip chip-sm">HEAD</span>}
          </div>
          <div className="muted version-meta">
            {v.short} · {v.author} · {timeAgo(v.time)}
            {m && (
              <span className="metrics-badges">
                {" "}
                · <span className={m.errors ? "badge-warn" : "badge-ok"}>{m.errors}e</span> <span className={m.warnings ? "badge-warn" : "badge-ok"}>{m.warnings}w</span>{" "}
                <span className={m.unconnected ? "badge-warn" : "badge-ok"}>{m.unconnected}u</span>
              </span>
            )}
            {threadNums.length > 0 && <span> · threads {threadNums.map((n) => `#${n}`).join(" ")}</span>}
          </div>
          {!openChanges && v.summary && <div className="version-summary cached">“{v.summary}”</div>}
          {openChanges && <VersionChanges design={design} sha={v.sha} onShowDiff={onCompare} />}
        </div>
      </div>
      <div className="version-actions">
        <button className="link" onClick={() => setOpenChanges((o) => !o)} data-testid={`changes-${v.short}`}>
          {openChanges ? "hide changes" : "changes"}
        </button>
        <button className="link" disabled={busy || viewing} onClick={onView}>
          view
        </button>
        <button className="link" disabled={busy} onClick={onCompare}>
          compare
        </button>
        <button className="link" disabled={busy || isHead} onClick={onRestore} data-testid={`restore-${v.short}`}>
          restore
        </button>
        <button className="link" disabled={busy} onClick={onBranch}>
          branch…
        </button>
      </div>
    </div>
  );
}

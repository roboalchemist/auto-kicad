/** Schematic viewer: the plotted sheet from KiCad plus the netlist and ERC the agent is working to.
 *
 * Shown instead of the board while a design is in the schematic phase. The plot comes from
 * `kicad-cli sch export svg`, so it is exactly what KiCad draws — no second renderer to drift.
 */

import { useEffect, useState } from "react";

import { api } from "./api.ts";
import type { SchematicInfo } from "./types.ts";

export function SchematicViewer({ design, rev, version }: { design: string; rev: string; version?: string | null }) {
  const [info, setInfo] = useState<SchematicInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [svgKey, setSvgKey] = useState(0);

  // `version` is the design's schematic content hash. It changes on every accepted edit, so the
  // sheet, netlist and ERC refresh live while the agent draws — not only when the tab is opened.
  useEffect(() => {
    let live = true;
    setError(null);
    api
      .schematic(design)
      .then((data) => live && setInfo(data))
      .catch((e) => live && setError(String(e instanceof Error ? e.message : e)));
    return () => {
      live = false;
    };
  }, [design, rev, version, svgKey]);

  const errors = info?.erc?.counts?.errors;
  const warnings = info?.erc?.counts?.warnings;
  const nets = Object.entries(info?.nets ?? {});
  const floating = info?.unconnected_pins ?? [];

  return (
    <div className="schematic-view" data-testid="schematic-view">
      <div className="schematic-bar">
        <span className="badge badge-phase" data-testid="schematic-phase-badge">
          schematic
        </span>
        {info?.brief && <span className="schematic-brief">{info.brief}</span>}
        <span className="schematic-stats muted" data-testid="schematic-stats">
          {info ? `${info.symbols.length} symbols · ${nets.length} nets · ${info.wires} wires` : "loading…"}
        </span>
        {info?.erc?.error ? (
          <span className="badge badge-warn" title={info.erc.error}>
            ERC unavailable
          </span>
        ) : (
          <span
            className={`badge ${errors ? "badge-error" : "badge-ok"}`}
            data-testid="schematic-erc"
            title={`${floating.length} floating pins`}
          >
            ERC {errors ?? 0} err / {warnings ?? 0} warn
          </span>
        )}
        <button className="link" onClick={() => setSvgKey((k) => k + 1)} title="Re-plot the sheet">
          refresh
        </button>
      </div>

      {error && <div className="error-text">{error.slice(0, 300)}</div>}

      <div className="schematic-sheet">
        <img
          /* Keyed by content hash so each edit re-fetches the plot; `?v=` busts the browser
             cache for a URL that would otherwise be identical. */
          key={`${svgKey}-${version ?? ""}`}
          src={api.schematicSvgUrl(design, rev, 0, version)}
          alt="schematic"
          data-testid="schematic-svg"
          onError={() => setError("the schematic could not be plotted")}
        />
      </div>

      <div className="schematic-side">
        <div className="section-title">Nets</div>
        {nets.length === 0 && <div className="muted">no connections yet</div>}
        <ul className="schematic-nets" data-testid="schematic-nets">
          {nets.map(([name, members]) => (
            <li key={name}>
              <b>{name}</b>
              <span className="muted">
                {members.map((m) => `${m.ref}.${m.pin}`).join(", ")}
              </span>
            </li>
          ))}
        </ul>
        {floating.length > 0 && (
          <>
            <div className="section-title">Floating pins</div>
            <div className="muted schematic-floating" data-testid="schematic-floating">
              {floating.map((f) => `${f.ref}.${f.pin}`).join(", ")}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

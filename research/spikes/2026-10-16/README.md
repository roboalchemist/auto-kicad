# Spikes: AG-UI backends and KiCad views (2026-10-16)

Throwaway code that answered the framework question in `research/agent-harness-2026.md`. Kept because it records exactly which APIs worked on that date. Results and conclusions are in that doc; this file covers how to re-run things.

## `agui/`: Pydantic AI vs LangGraph over AG-UI

`pai_app.py` is a Pydantic AI 2.57 agent behind `AGUIAdapter`:
- `render_board` returns a PNG the model sees, plus a `STATE_SNAPSHOT` event.
- `commit_design` needs approval, so the run ends in an AG-UI interrupt.

`lg_app.py` is the LangGraph 1.2 equivalent: `interrupt()` handles the approval, and frontend tools are bound by hand.

`agui_client.py` and `run_scenarios.py` post `RunAgentInput` to either server, record the SSE stream, and resume interrupts. `board_png.py` draws test images with a random code and shape, so you can check that the model really read them.

`streams/pai_*.sse` are recorded Pydantic AI streams from `claude-haiku-5-5`:
- render, then commit (ends in an interrupt);
- resume after approval;
- resume without the reasoning messages;
- a frontend-tool call, then its result.

They also work as fixtures for building UI against a stream before the backend exists.

```bash
python3 -m venv .venv
.venv/bin/pip install 'pydantic-ai-slim[ag-ui,anthropic]==2.57.0' uvicorn httpx pillow
export ANTHROPIC_API_KEY=sk-ant-...
.venv/bin/uvicorn pai_app:app --port 8811 &
.venv/bin/python run_scenarios.py pai http://127.0.0.1:8811/ all   # writes streams/ and results/
```

LangGraph needs its own venv: `ag-ui-langgraph` wants `ag-ui-protocol` 1.x, but Pydantic AI 2.57 pins it below 1. Install `langgraph langchain-anthropic 'ag-ui-langgraph[fastapi]'` and serve `lg_app:app`.

## `viewer/`: agent renders and browser picking

- `blinker_k10.kicad_pcb` is the demo blinker after `kicad-cli pcb upgrade` (KiCad 10 format, name-only `(net "X")`). It still has the duplicate pad UUIDs that `demo/layout.py` copies from library footprints; `dedupe_uuids.py` fixes a copy.
- `dump_items.py` (run with KiCad's Python) dumps footprints, pads, tracks and vias with UUIDs, nets and geometry. That dump is the pick index: `items_k10.json` comes from this board, `items_uniq.json` from the deduplicated copy.
- `frame_render.py` frames `kicad-cli pcb render` on a point in mm and a view height. The camera mapping is in its docstring.
- `svg_pick.html` overlays invisible hit shapes from `items_uniq.json` on `svg/front.svg` (`kicad-cli pcb export svg --layers F.Cu,F.SilkS,Edge.Cuts --page-size-mode 2 --exclude-drawing-sheet --mode-single`). Serve the folder with `python3 -m http.server` and click; `svg_pick_test.py` drives it with Playwright.
- `glb_inspect.py` lists the nodes and meshes in a `kicad-cli pcb export glb` file using only the standard library.
- `k10_to_numbered_nets.py` rewrites KiCad 10 nets into the numbered form KiCanvas understands. Use its output for display only.
- `images/` holds evidence screenshots:
  - an overlay pick of U1 pad 1;
  - a framed 10 mm render around U1;
  - KiCanvas showing a KiCad 10 board.

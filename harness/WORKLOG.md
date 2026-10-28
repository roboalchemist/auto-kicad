# WORKLOG

Challenges encountered while building the schematic phase, kept so they are not rediscovered.
Everything here was found empirically against KiCad 10.0.7 via `kicad-cli sch export svg` /
`kicad-cli sch erc`, which are the only fast authorities for "will KiCad load this file?".

## KiCad-10 `.kicad_sch` format rules that bite

`kicad-cli` reports a rejected file only as `Failed to load schematic` (exit 3) with no line
number and nothing useful on stderr, even under `strace`. Bisect instead: start from a minimal
file KiCad accepts, add one node at a time, and run `kicad-cli sch export svg`. That is much
faster than reading the parser source.

Rules, each verified by bisection:

1. **Quoted strings.** `generator`, `generator_version`, `uuid`, `paper`, `lib_id`, property
   keys *and* values, and `page` are written quoted by KiCad and must round-trip quoted. The
   writer carries an always-quote marker (`schematic.Q`) for these.
2. **Unit sub-symbol names stay short.** A library symbol is `(symbol "lib:Name" ...)` but its
   unit is `(symbol "Name_0_1" ...)` — *not* `lib:Name_0_1`. KiCad strips the `lib:` prefix
   from the parent and looks up `Name_<unit>_<style>`; a prefixed unit name fails to load.
3. **One wire per straight segment.** A `wire` node holds exactly two `xy` points. A bent path
   is several wires sharing endpoints (plus a junction where three or more meet).
4. **No per-pin instance entries.** `(pin N (uuid ...))` inside a placed symbol made
   `kicad-cli` reject the file in every form tried (`alternate` included). They are optional,
   so the writer omits them.
5. **Legacy library syntax.** JLC2KiCadLib-style libraries carry `(id N)` properties and bare
   `hide` inside `(effects ...)`. The `id` must be dropped; bare `hide` is still accepted.
6. **`-0.0` is not a number KiCad accepts.** Generated libraries contain it; the writer
   normalises it to `0`.
7. **`find_all(node, head)` needs the whole root node.** `parse()` returns the root list, not a
   list of trees; `parse(text)[0]` is the head string and silently finds nothing.

A working end-to-end check (symbols → `connect_pins` → save → reload) that passes ERC with 0
violations is in `tests/test_schematic.py`.

## Connectivity: ask KiCad, don't re-derive it

The first version of the schematic→board handoff read nets geometrically (union-find over pin
points, wire ends and labels). It mostly worked and then disagreed with KiCad on one pin: a
power symbol and a global label can name the same point, and dict insertion order decided which
won. Two lessons:

- **Use `kicad-cli sch export netlist`** as the authority for connectivity
  (`kicad_cli.export_netlist` + `parse_netlist`). It applies eeschema's own rules, including
  power symbols and global labels. The geometric extractor stays for quick agent queries, but
  the one-way transition to a board seeds pads from KiCad's netlist.
- Power symbols (`#PWR..`, `(power)` in the library) are not parts: they connect at their one
  pin and name a global net through their **value**. Skipping every `#` reference loses GND/VCC.

`engine/seed.py` places footprints on a grid and assigns pad nets from that netlist. A missing
footprint is reported per part instead of aborting the whole board.

## Why the goal loop died (and how each is fixed)

Every one of these ended a live run. Each is now covered by a test in `tests/test_loop.py`.

| Symptom | Cause | Fix |
|---|---|---|
| "Model token limit (16000) exceeded before any response" | A reasoning model spent the whole completion budget on thinking and returned `finish_reason=length` with no output | `max_tokens` default 20000 (configurable), thinking `low`, and `next_budget()` adapts up to 64000 |
| 402 "can only afford 25411 tokens" | Raising the budget past the provider's key limit | `next_budget()` also *shrinks* the budget when the provider rejects it |
| "Tool 'schematic_summary' exceeded max retries count of 5" | Models send `{"_": null}` to no-argument tools; extra args were a validation error, retried 5x | No-arg tools accept `**kwargs`; refusals return `ok:false` data instead of `ModelRetry` |
| A tool appeared hung for minutes | (a) SSE polling twice a second per tab shared the thread pool tools run on; (b) every schematic tool parsed ~200 symbol libraries on first use | `SseFanout` shares one probe per design; libraries load on demand (137s -> 0.74s) |
| "Goal NOT MET" after doing all the work | `board_laid_out` was supplied only in the schematic phase, so it never passed once a board existed — in four call sites | `goals.with_board_state()` is the single source |
| Schematic had 0 wires | A netless `generate_schematic_skidl` overwrote the sheet, discarding wiring | Refuses netless generation and restores the previous file |
| Wrong pins joined / shorts | Library symbol y is +up, sheet y is +down; pin positions skipped the sign flip | Negate the local pin y; verified against `kicad-cli` |
| Wires read as unconnected | `pin_net` stopped at the first touching wire, and missed pins meeting a power symbol | Follows the whole chain; `unconnected_pins` uses the connectivity graph |

## Cold-start evidence

`coldstart-rc5`, service freshly restarted, headless `kicad-harness run --loop` on `bifrost:deepseek-flash-latest`:

- 140 tool calls, 32 versions, **no failed/retried model calls**
- schematic: 18 wires, 0 floating pins, 0 ERC errors
- board: 16 x 10 mm, 0 DRC errors, 0 unconnected
- `Goal MET`

Then `midstream`: killed ~55s in (12 versions committed), resumed with `--thread` and finished
`Goal MET` (0 ERC, 0 DRC, 0 unconnected). Interruption loses no work because every edit is a commit.

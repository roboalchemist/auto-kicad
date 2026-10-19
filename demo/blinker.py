#!/usr/bin/env python3
"""
555 LED Blinker — JLCPCB → KiCad Pipeline Demo

Pipeline:
  CDFER SQLite DB → JLC2KiCad_lib → skidl → .kicad_pcb

Searches a local JLCPCB parts database for real components, fetches their
KiCad symbols/footprints, wires them into a 555 astable circuit, and
generates a KiCad netlist + PCB file.
"""

import logging
import os
import sqlite3
import sys
from argparse import Namespace
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

DEMO_DIR = Path(__file__).parent.resolve()
LIBS_DIR = DEMO_DIR / "libs"
DB_PATH = DEMO_DIR.parent / "data" / "jlcpcb-components.sqlite3"

# ── Part search queries ──────────────────────────────────────────────────────
# Each entry: (label, WHERE clause, ORDER BY clause)
PART_QUERIES = [
    ("NE555 (SOIC-8)", "mfr LIKE '%NE555%' AND (package='SOIC-8' OR package='SOP-8')", "stock DESC"),
    ("10K Resistor (0805)", "mfr LIKE '%F1002%' AND package='0805' AND basic=1", "stock DESC"),
    ("470R Resistor (0805)", "mfr LIKE '%F4701%' AND package='0805' AND basic=1", "stock DESC"),
    ("100nF Cap (0805)", "mfr LIKE '%104%' AND package='0805' AND basic=1", "stock DESC"),
    ("10uF Cap (0805)", "mfr LIKE '%106%' AND package='0805' AND basic=1", "stock DESC"),
    ("Red LED (0805)", """
        c.category_id IN (SELECT id FROM categories WHERE subcategory LIKE '%LED%')
        AND c.package='0805' AND c.basic=1
    """, "c.stock DESC"),
]

# Fallback: known-good LCSC IDs if DB search fails
FALLBACK_PARTS = {
    "NE555 (SOIC-8)": ("C7593", "NE555DR", "SOIC-8"),
    "10K Resistor (0805)": ("C17414", "0805W8F1002T5E", "0805"),
    "470R Resistor (0805)": ("C17673", "0805W8F4701T5E", "0805"),
    "100nF Cap (0805)": ("C49678", "CC0805KRX7R9BB104", "0805"),
    "10uF Cap (0805)": ("C15850", "CL21A106KAYNNNE", "0805"),
    "Red LED (0805)": ("C84256", "NCD0805R1", "0805"),
}


# ── Step A: Search the SQLite DB ─────────────────────────────────────────────

def search_parts(db_path: Path) -> dict[str, tuple[str, str, str]]:
    """Search JLCPCB SQLite DB for required parts.

    Returns dict of {label: (lcsc_id, mfr, package)}.
    """
    if not db_path.exists():
        log.warning("Database not found at %s, using fallback parts", db_path)
        return dict(FALLBACK_PARTS)

    db = sqlite3.connect(str(db_path))
    cur = db.cursor()
    found = {}

    for label, where, order in PART_QUERIES:
        # Use 'c' alias since some queries reference it
        sql = f"SELECT c.lcsc, c.mfr, c.package, c.stock FROM components c WHERE {where} ORDER BY {order} LIMIT 1"
        try:
            cur.execute(sql)
            row = cur.fetchone()
        except sqlite3.OperationalError as e:
            log.warning("Query failed for %s: %s", label, e)
            row = None

        if row:
            lcsc_id = f"C{row[0]}"
            found[label] = (lcsc_id, row[1], row[2])
            log.info("Found %-25s → %s  %s  (%s, stock: %d)", label, lcsc_id, row[1], row[2], row[3])
        else:
            log.warning("No DB result for %s, using fallback", label)
            found[label] = FALLBACK_PARTS[label]

    db.close()
    return found


# ── Step B: Fetch KiCad libraries via JLC2KiCad_lib ─────────────────────────

def fetch_libraries(parts: dict[str, tuple[str, str, str]]) -> None:
    """Download KiCad symbols + footprints for each part."""
    from JLC2KiCadLib.JLC2KiCadLib import add_component

    output_dir = str(LIBS_DIR)
    os.makedirs(output_dir, exist_ok=True)

    args = Namespace(
        output_dir=output_dir,
        footprint_creation=True,
        symbol_creation=True,
        symbol_lib="jlcpcb",
        symbol_lib_dir="symbols",
        footprint_lib="footprints",
        model_dir="packages3d",
        model_base_variable="",
        skip_existing=True,
        models="STEP",
    )

    for label, (lcsc_id, mfr, pkg) in parts.items():
        log.info("Fetching library for %s (%s)...", label, lcsc_id)
        try:
            add_component(lcsc_id, args)
        except Exception as e:
            log.error("Failed to fetch %s (%s): %s", label, lcsc_id, e)
            raise


# ── Step B½: Discover symbol names from generated library ────────────────────

def discover_symbol_names(parts: dict[str, tuple[str, str, str]]) -> dict[str, str]:
    """Read the generated .kicad_sym and map LCSC IDs to actual symbol names.

    JLC2KiCad_lib names symbols by the EasyEDA model name, which may differ
    from the MFR part number in the JLCPCB database. The LCSC ID is stored
    in a 'ki_keywords' or 'LCSC' property inside each symbol.

    Returns dict of {lcsc_id: symbol_name}.
    """
    import re

    sym_file = LIBS_DIR / "symbols" / "jlcpcb.kicad_sym"
    content = sym_file.read_text()

    lcsc_to_symbol = {}
    # Find top-level symbol definitions (not sub-symbols like NE555DR_0_1)
    for match in re.finditer(
        r'^\s+\(symbol\s+"([^"]+)"\s+.*?(?=^\s+\(symbol\s+"[^"]+"\s+\(|\Z)',
        content,
        re.MULTILINE | re.DOTALL,
    ):
        sym_name = match.group(1)
        # Skip sub-symbols (contain _0_1 suffix)
        if re.search(r"_\d+_\d+$", sym_name):
            continue
        block = match.group(0)
        # Extract LCSC property
        lcsc_match = re.search(r'\(property\s+"(?:LCSC|ki_keywords)"\s+"(C\d+)"', block)
        if lcsc_match:
            lcsc_id = lcsc_match.group(1)
            lcsc_to_symbol[lcsc_id] = sym_name
            log.info("Symbol mapping: %s → %s", lcsc_id, sym_name)

    return lcsc_to_symbol


# ── Step C: Wire the 555 astable circuit with skidl ─────────────────────────

def wire_circuit(parts: dict[str, tuple[str, str, str]]) -> None:
    """Create 555 astable blinker circuit using skidl.

    Classic 555 astable:
        VCC → R1 → junction → R2 → C1(timing) → GND
        junction connects to pin 7 (DISCHARGE)
        R2/C1 junction connects to pins 2 (TRIGGER) and 6 (THRESHOLD)
        pin 5 (CONTROL) bypassed to GND via C2
        pin 3 (OUTPUT) → R_LED → LED → GND
        pin 4 (RESET) tied to VCC
        pin 8 (VCC), pin 1 (GND)
    """
    import skidl

    # Reset any previous circuit state
    skidl.reset()

    # Point skidl at our downloaded libraries
    sym_dir = str(LIBS_DIR / "symbols")
    fp_dir = str(LIBS_DIR / "footprints")
    skidl.lib_search_paths[skidl.KICAD] = [sym_dir]
    skidl.footprint_search_paths[skidl.KICAD] = [fp_dir]

    # Discover actual symbol names from the generated library
    lcsc_to_sym = discover_symbol_names(parts)

    # Build lookup: label → symbol_name
    def sym(label: str) -> str:
        lcsc_id = parts[label][0]
        if lcsc_id not in lcsc_to_sym:
            raise ValueError(f"No symbol found for {label} ({lcsc_id}). Available: {lcsc_to_sym}")
        return lcsc_to_sym[lcsc_id]

    # Create nets
    vcc = skidl.Net("VCC")
    gnd = skidl.Net("GND")
    discharge_net = skidl.Net("DISCHARGE")
    threshold_net = skidl.Net("THRESHOLD")
    output_net = skidl.Net("OUTPUT")
    control_net = skidl.Net("CONTROL")
    led_anode = skidl.Net("LED_ANODE")

    # ── Instantiate parts ──
    # Symbol names come from JLC2KiCad_lib (EasyEDA model names)
    # Footprints are already embedded in the symbol definitions
    ne555 = skidl.Part("jlcpcb", sym("NE555 (SOIC-8)"))
    r1 = skidl.Part("jlcpcb", sym("10K Resistor (0805)"), ref_prefix="R")
    r2 = skidl.Part("jlcpcb", sym("10K Resistor (0805)"), ref_prefix="R")
    r_led = skidl.Part("jlcpcb", sym("470R Resistor (0805)"), ref_prefix="R")
    c1 = skidl.Part("jlcpcb", sym("10uF Cap (0805)"), ref_prefix="C")
    c2 = skidl.Part("jlcpcb", sym("100nF Cap (0805)"), ref_prefix="C")
    led = skidl.Part("jlcpcb", sym("Red LED (0805)"), ref_prefix="D")

    # ── Log pin names to help with wiring ──
    log.info("NE555 pins: %s", [(p.num, p.name) for p in ne555.pins])
    log.info("R1 pins: %s", [(p.num, p.name) for p in r1.pins])
    log.info("C1 pins: %s", [(p.num, p.name) for p in c1.pins])
    log.info("LED pins: %s", [(p.num, p.name) for p in led.pins])

    # ── Wire the 555 ──
    # NE555 standard pinout (SOIC-8):
    #   1=GND, 2=TRIGGER, 3=OUTPUT, 4=RESET, 5=CONTROL, 6=THRESHOLD, 7=DISCHARGE, 8=VCC
    # We connect by pin number for reliability since symbol pin names vary

    # Power
    ne555[8] += vcc          # VCC
    ne555[1] += gnd          # GND
    ne555[4] += vcc          # RESET tied high

    # Timing network: VCC → R1 → DISCHARGE → R2 → THRESHOLD/TRIGGER → C1 → GND
    ne555[7] += discharge_net   # DISCHARGE
    ne555[6] += threshold_net   # THRESHOLD
    ne555[2] += threshold_net   # TRIGGER (same net as THRESHOLD for astable)

    # R1: VCC to DISCHARGE
    r1[1] += vcc
    r1[2] += discharge_net

    # R2: DISCHARGE to THRESHOLD
    r2[1] += discharge_net
    r2[2] += threshold_net

    # C1 (timing cap): THRESHOLD to GND
    c1[1] += threshold_net
    c1[2] += gnd

    # Control voltage bypass: pin 5 → C2 → GND
    ne555[5] += control_net
    c2[1] += control_net
    c2[2] += gnd

    # Output: pin 3 → R_LED → LED → GND
    # LED pinout from JLC2KiCad_lib: pin 1 = cathode (-), pin 2 = anode (+)
    ne555[3] += output_net
    r_led[1] += output_net
    r_led[2] += led_anode
    led[2] += led_anode     # Anode (+)
    led[1] += gnd           # Cathode (-)

    # ── Run ERC ──
    log.info("Running Electrical Rules Check...")
    skidl.ERC()

    # ── Generate netlist ──
    netlist_path = str(DEMO_DIR / "blinker.net")
    log.info("Generating netlist: %s", netlist_path)
    skidl.generate_netlist(file_=netlist_path)
    log.info("Netlist generated successfully")

    return netlist_path


# ── Step D: Generate KiCad PCB ───────────────────────────────────────────────

def generate_pcb(netlist_path: str) -> str:
    """Convert netlist to .kicad_pcb file.

    Tries kinet2pcb first (requires pcbnew), falls back to creating a
    minimal .kicad_pcb from the netlist using S-expression generation.
    """
    pcb_path = str(DEMO_DIR / "blinker.kicad_pcb")

    try:
        from kinet2pcb import kinet2pcb
        log.info("Using kinet2pcb for PCB generation...")
        kinet2pcb.kinet2pcb(netlist_path, pcb_path)
        log.info("PCB generated: %s", pcb_path)
        return pcb_path
    except (ImportError, Exception) as e:
        log.warning("kinet2pcb unavailable (%s), generating minimal PCB from netlist", e)

    # Fallback: parse netlist and create minimal .kicad_pcb with components
    pcb_path = _generate_minimal_pcb(netlist_path, pcb_path)
    return pcb_path


def _generate_minimal_pcb(netlist_path: str, pcb_path: str) -> str:
    """Generate a minimal .kicad_pcb by parsing the netlist and placing footprints."""
    from layout import BoardLayout

    # Parse the netlist to extract component info
    components = _parse_netlist_components(netlist_path)

    # Create a new board
    board = BoardLayout.new_board(pcb_path, components, str(LIBS_DIR / "footprints"))
    board.set_board_outline(50, 40)
    board.auto_place_grid(spacing_mm=12.0)
    board.save()

    log.info("Minimal PCB generated: %s", pcb_path)
    return pcb_path


def _parse_netlist_components(netlist_path: str) -> list[dict]:
    """Extract component references and footprints from a KiCad netlist."""
    import re

    with open(netlist_path, "r") as f:
        content = f.read()

    components = []
    # KiCad netlist format has (comp (ref X) (value Y) (footprint Z) ...)
    # We parse with regex since it's a simple S-expression
    comp_pattern = re.compile(
        r'\(comp\s+\(ref\s+"?(\w+)"?\).*?\(value\s+"?([^")\s]+)"?\).*?\(footprint\s+"?([^")\s]+)"?\)',
        re.DOTALL,
    )
    for match in comp_pattern.finditer(content):
        components.append({
            "ref": match.group(1),
            "value": match.group(2),
            "footprint": match.group(3),
        })

    log.info("Parsed %d components from netlist", len(components))
    return components


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("555 LED Blinker — JLCPCB → KiCad Pipeline Demo")
    log.info("=" * 60)

    # Step A: Search for parts
    log.info("\n── Step A: Searching JLCPCB database ──")
    parts = search_parts(DB_PATH)
    log.info("Found %d parts\n", len(parts))

    # Step B: Fetch KiCad libraries
    log.info("── Step B: Fetching KiCad libraries ──")
    fetch_libraries(parts)
    log.info("Libraries downloaded to %s\n", LIBS_DIR)

    # Step C: Wire the circuit
    log.info("── Step C: Wiring 555 astable circuit ──")
    netlist_path = wire_circuit(parts)

    # Step D: Generate PCB
    log.info("\n── Step D: Generating KiCad PCB ──")
    pcb_path = generate_pcb(netlist_path)

    log.info("\n" + "=" * 60)
    log.info("Pipeline complete!")
    log.info("  Netlist: %s", netlist_path)
    log.info("  PCB:     %s", pcb_path)
    log.info("  Open in KiCad to view the board")
    log.info("=" * 60)


if __name__ == "__main__":
    main()

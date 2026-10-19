# KiPart Analysis Report

## Overview

**KiPart** is a CLI tool for generating KiCad schematic symbol libraries (.kicad_sym) from CSV or Excel files, and converting existing libraries back to CSV. It focuses on creating "boring, box-like" symbols with pins arranged on four sides, targeting users who want spreadsheet-driven symbol management.

- **Version**: 2.3.0 (Jan 2026)
- **Author**: Dave Vandenbout (devbisme)
- **License**: MIT
- **Repository**: github.com/devbisme/kipart
- **Python**: 3.8+

## Architecture

### Single-Module Design

The entire codebase lives in one main file (`kipart/kipart.py`, ~2027 lines) plus three small auxiliary modules:

```
kipart/
  __init__.py          # Re-exports everything from kipart.py and version.py
  kipart.py            # All core logic (~2027 lines)
  compare_symbols.py   # Deep equality comparison for symbols/libraries
  random_symbol.py     # Random symbol generator for testing
  version.py           # Version string
```

### Data Flow Pipeline

```
CSV/Excel file
  -> read_row_file()           # Parse CSV (stdlib csv) or Excel (pandas)
  -> read_symbol_rows()        # Split rows by blank lines into per-symbol groups
  -> rows_to_symbol()          # Convert each group into a KiCad symbol Sexp
  -> rows_to_symbol_lib()      # Wrap symbols in a library Sexp
  -> row_file_to_symbol_lib_file()  # Write .kicad_sym with quoting
```

Reverse path:
```
.kicad_sym file
  -> extract_symbols_from_lib()  # Parse S-expression, extract symbol nodes
  -> symbol_to_csv_rows()        # Convert each symbol back to CSV rows
  -> symbol_lib_file_to_csv_file()  # Write CSV
```

### Dependencies

| Dependency | Purpose |
|-----------|---------|
| `simp_sexp` | S-expression parsing/manipulation (KiCad file format) |
| `pandas` | Reading Excel files (.xlsx, .xls) |
| `openpyxl` | Excel engine for pandas |

Standard library: `csv`, `math`, `os`, `sys`, `argparse`, `functools`

## Input Format Parsing

### CSV Format Structure

Each symbol in a CSV file follows this structure:
1. **Part name** in first column of first row
2. **Properties** on subsequent rows (key with trailing colon, then value)
3. **Column headers** row: required `Pin`, `Name`; optional `Unit`, `Side`, `Type`, `Style`, `Hidden`
4. **Pin data** rows with values matching headers
5. **Blank line** separates multiple symbols

Properties map to KiCad properties via a lookup table (e.g., `Reference:`, `Footprint:`, `Datasheet:`). Custom properties (not in the lookup) are placed below the symbol; prefixing the property name with `*` makes it hidden.

### Pin Type/Style Mapping

Extensive alias mapping via `str_to_type()` and `str_to_style()`:
- Types: `input/inp/in/clk`, `output/out/outp`, `bidirectional/bidir/bi/inout/io`, `power_in/pwr/ground/gnd`, etc.
- Styles: `line`, `inverted/inv/~/# `, `clock/clk`, `inverted_clock`, `input_low`, `output_low`, `edge_clock_high`, `non_logic/nl/analog`
- Sides: `left/l`, `right/r`, `top/t`, `bottom/b`

### Excel Support

Uses `pandas.read_excel()` with `dtype=str` and `header=None` to treat all data as strings, same as CSV parsing.

## Symbol Generation Algorithm

### Core Function: `rows_to_symbol()`

This is the heart of KiPart (~450 lines). The algorithm:

1. **Parse part name and properties** from the first rows
2. **Map column headers** to indices (flexible column ordering)
3. **Collect pin data** with defaults for optional fields
4. **Calculate pin length** based on longest pin number text width
5. **Group pins by unit and side** into a nested dict: `{unit_id: {side: [pins]}}`
6. **For each unit**:
   a. Expand spacer pins (`insert_spacers()`)
   b. Bundle identical power/ground pins if requested
   c. Calculate bounding box per side based on pin name widths and pin counts
   d. Compute unit dimensions (width/height) considering scrunch mode
   e. Create rectangle outline centered on origin
   f. Sort pins per side (by row order, pin number, or pin name)
   g. Place pins with correct coordinates, orientation, and spacing
7. **Place properties** at the top-left corner across all units
8. **Assemble final Sexp** with units appended after properties

### Pin Placement Logic

Pins are placed on a grid (`GRID_SPACING = 1.27mm`). Key parameters:

- `PIN_HEIGHT = 2 * GRID_SPACING` (2.54mm) - standard KiCad pin spacing
- `PIN_SPACING = 2 * GRID_SPACING` - distance between adjacent pins
- `FONT_SIZE = 1.27mm` - text sizing for width calculations
- `push` parameter (0.0-1.0) controls pin group positioning on each side

Pin orientation is set by side: left=0deg, right=180deg, top=270deg, bottom=90deg.

The `--ccw` flag reverses pin direction on right and top sides for counter-clockwise arrangement.

The `--scrunch` flag compresses the symbol width to only accommodate top/bottom pins, pushing left/right pin labels under the top/bottom pin rows.

## Multi-Unit Support

Units are identified by the `Unit` column value. Each distinct unit ID creates a separate sub-symbol. Unit numbering is assigned sequentially based on order of appearance.

If the unit ID differs from the default ("1") and there are multiple units, a `unit_name` attribute is added to the KiCad symbol so it appears in the unit dropdown.

Each unit gets its own rectangle outline and pin placement, sized independently.

## Pin Sorting, Bundling, and Arrangement

### Sorting (`-s` flag)
- `row`: Preserve CSV row order (default)
- `num`: Natural sort by pin number via `parse_mixed_string()` (handles mixed alpha/numeric like "A10", "B2")
- `name`: Natural sort by pin name

### Bundling (`-b` flag)
`bundle_pins()` merges identically-named power_in and power_out pins into a single visible pin:
- All pin numbers are collected into a list on the first pin
- Hidden bundled pins become `passive` type to avoid ERC issues (hidden power_in pins become global nets)
- Bundle suffix can be `count` (e.g., `VCC[3]`), `range` (e.g., `VCC[2:0]`), or `none`
- Using `-b` twice also bundles `no_connect` pins

### Spacer Pins
Pin numbers with leading `*` characters insert blank gaps:
- `*1` = one gap then pin 1
- `**1` = two gaps then pin 1
- `***` = three gaps, no real pin
- Only effective with `-s row` sorting

### Pin Creation
`create_pin()` handles:
- Bundled pins: creates multiple pin Sexp objects at the same coordinates, with only the first visible
- Hidden power_in pins converted to passive to avoid global net issues
- Hidden NC pins shifted off-grid to prevent accidental connections
- Alternate pin names split by delimiter

## Output Format (.kicad_sym)

Output is KiCad 8.0-compatible S-expression format:
- Version: `20241209`
- Generator: `kicad_symbol_editor`
- String quoting handled via `add_quotes()` using `simp_sexp`'s quoting API

The `simp_sexp` library handles all S-expression serialization. Specific elements requiring quoted values are defined in `add_rmv_quotes()`.

## Reverse Conversion (kilib2csv)

`symbol_to_csv_rows()` parses a KiCad symbol Sexp back into CSV rows:
- Extracts symbol name, properties, and per-unit pin data
- Determines pin side from orientation angle: `{0: left, 90: bottom, 180: right, 270: top}`
- Detects hidden pins from both pin-level `hide` and name/number effects `hidden`
- Extracts unit names from `unit_name` attributes, falling back to sequential numbers

## CLI Interface

Two entry points registered via `pyproject.toml`:

### `kipart`
Full-featured CLI with argparse:
- Input: one or more CSV/Excel files
- Output: `.kicad_sym` file (auto-named or specified with `-o`)
- Sort: `-s row|num|name`, `--reverse`
- Layout: `--ccw`, `--scrunch`, `--push 0.0-1.0`, `--side`, `--hide-pin-num`
- Bundling: `-b` (repeat for NC pins), `--bundle-style none|count|range`
- Defaults: `--type`, `--style`
- Library management: `-w` (overwrite), `-m` (merge), `-1` (one-symbol mode)
- Text: `-j left|center|right`, `-a` (alt pin name delimiter)

### `kilib2csv`
Simpler CLI for reverse conversion:
- Input: one or more `.kicad_sym` files
- Output: CSV file
- Options: `-o` output path, `-w` overwrite

## Testing

Tests use pytest with comprehensive coverage:

| Test | What it covers |
|------|---------------|
| `test_get_text_bounding_box` | Text width calculation |
| `test_parse_mixed_string` | Alphanumeric sorting key |
| `test_extract_symbols_from_lib` | S-expression symbol extraction |
| `test_symbol_to_csv_rows` | Symbol-to-CSV conversion |
| `test_open_row_file` | CSV and Excel file reading |
| `test_read_symbol_rows` | Row grouping by blank lines |
| `test_rows_to_symbol` | Core symbol generation |
| `test_row_file_to_symbol_lib_file` | End-to-end file conversion |
| `test_kipart_cli` / `test_kilib2csv_cli` | CLI subprocess tests |
| `test_create_empty_symbol_lib` | Library scaffold |
| `test_merge_symbol_libs` | Library merging with duplicate handling |
| `test_scrunch_option` | Scrunch layout verification |
| `test_bundle_option` | Power pin bundling |
| `test_symbols_are_equal` | Deep symbol comparison |
| `test_symbol_libs_are_equal` | Deep library comparison |
| `test_end_to_end_conversion` | Round-trip: random symbols -> kicad_sym -> CSV -> kicad_sym |
| `test_insert_spacers` | Spacer pin expansion |
| `test_bundle_pins` | Pin bundling unit tests |

The `random_symbol.py` module generates random symbols for fuzz-like round-trip testing.

14 example CSV files are included for testing various scenarios.

## Code Quality

### Strengths
- Clean, well-documented code with extensive docstrings
- Comprehensive test suite including round-trip verification with random symbols
- Good separation between data parsing, symbol generation, and file I/O
- Flexible alias system for pin types/styles (user-friendly)
- Proper grid alignment throughout
- Handles edge cases: hidden pins, bundled power pins, spacer gaps, multi-unit symbols
- Bidirectional conversion (CSV <-> .kicad_sym) enables spreadsheet-based workflow
- Active development (v2.0 rewrite in May 2025, regular updates through Jan 2026)

### Weaknesses
- **Monolithic module**: All logic in one 2027-line file; could benefit from splitting into parsing, generation, and layout modules
- **Box-only symbols**: Cannot create stylized symbols (circles, custom graphics, arcs) -- only rectangles
- **No schematic-level features**: No support for power flags, graphical symbols, or component variants
- **Text width approximation**: Uses `font_size * 0.9 * char_count` which is imprecise for proportional fonts
- **Bug**: `open_emitter` maps to `open_collector` in `str_to_type()` (line 273)
- **No validation of pin number uniqueness**: Duplicate pin numbers within a unit are not caught
- **Limited error context**: Errors during symbol generation are caught and printed, but the user gets minimal diagnostic info
- **simp_sexp dependency**: A custom/niche library for S-expression handling; coupling to its API makes the code harder to understand without that library's docs

## Key Takeaways for auto-kicad

1. **CSV-to-symbol pipeline** is a well-validated pattern -- the input format is simple, human-editable, and spreadsheet-compatible
2. **Pin placement algorithm** handles all four sides with proper grid alignment, centering, and directional options
3. **Bundle/spacer system** elegantly handles high-pin-count ICs with many power/ground pins
4. **S-expression output** via `simp_sexp` is clean but creates a dependency; direct string generation or a lighter approach might be preferable
5. **Round-trip testing** with random symbols is an excellent validation strategy worth adopting
6. **The text width calculation** is approximate and could be improved with actual font metrics
7. **Unit naming** support allows descriptive unit labels (e.g., "IO", "PWR") in multi-unit symbols

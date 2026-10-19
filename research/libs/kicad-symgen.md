# kicad-symgen Analysis

## Overview

**Repository**: kicad-symgen
**Author**: Bob Cousins (2017)
**License**: GPLv3
**Language**: Python 2/3 (mixed compatibility)
**Purpose**: Generate KiCad schematic symbol libraries from a custom text-based description language

## Architecture

```
symgen/
  sym_gen.py           # CLI entry point (argparse)
  lib_symgen.py        # Core: SymGen class - parser + symbol generation engine (~1350 lines)
  convert_library.py   # Reverse: convert .lib/.kicad_sym -> symgen .txt format
  gen_legacy.py        # Output generator for KiCad v5 legacy format (.lib/.dcm)
  gen_sweet.py         # Output generator for KiCad v6 S-expression format (.kicad_sym)
  sym_comp.py          # Data model classes (SgComponent, SgSettings, Pin, drawing primitives)
  sym_drawing.py       # Drawing primitives (Point, Rectangle, BoundingBox, Arc, Circle, PolyLine, Rect, Text, Pin)
  sym_gates.py         # Logic gate shape generators (AND, OR, XOR, NOT, IEC box style)
  sym_iec.py           # IEC symbol structure classes (IecSymbol, IecElement, Group)
  sym_utils.py         # Utility functions (bounds, checksums, icon copying, pin analysis)
  sym_utils_v6.py      # V6-specific utilities
  sweet.py             # S-expression helpers and v5<->v6 conversion functions
  str_utils.py         # String manipulation utilities
  file_util.py         # File path utilities
  common/
    kicad_sym.py       # KiCad v6 .kicad_sym parser (from kicad-library-utils)
    sexpr.py           # S-expression parser
    boundingbox.py     # Bounding box utilities
    rulebase.py        # Rule-based checking
    print_color.py     # Colored terminal output
  v5_schlib/
    schlib.py          # KiCad v5 .lib parser (from kicad-library-utils)
```

The tool has two main flows:
1. **Generate**: Parse `.txt` description file -> build internal representation -> emit KiCad library
2. **Dump/Convert**: Parse existing KiCad `.lib` or `.kicad_sym` -> emit `.txt` description file

## Input Text Format Specification

The format is fully documented in `symgen/doc/symgen.bnf` and `symgen/doc/symgen_syntax.txt`.

### Global Directives
```
%lib Logic_74xx          # Output library name
%pinlen 200              # Pin length in mils
%width 600               # Box width in mils (or AUTO)
%fill back               # Body fill: fore, back, none
%line 10                 # Default pen size in mils
%iconlib template.lib    # Icon template library file
%style IEC|ANSI|DIN      # Symbol drawing style
%label_style center|floating
%pin_stack OFF|pattern+  # Pin stacking configuration
```

### Component Definition
```
COMP <name> <reference> [FROM <parent> | TEMPLATE]
  [FIELD $FOOTPRINT|name value]*
  [FPLIST <footprint_pattern>*]
  [DESC <description>]
  [KEYW <keywords>]
  [DOC <url>]
  [ALIAS <name> [DESC ...] [KEYW ...] [DOC ...]]
  <unit>*
END
```

### Unit Definition
```
UNIT [type] [WIDTH n] [LABEL "str"] [TEMPLATE name] [ICON name+]
  <element>*
```

Unit types: `PWR [SEP|COMB]`, `NONE`, logic gates (`AND`, `OR`, `NAND`, `NOR`, `XOR`, `XNOR`, `NOT`, `BUF`), `EXTENDS n`

### Pin Definition
```
<pin_number> <pin_name> [flags][type] [position] [qualifiers]
SPC [position]                    # Spacer (gap in pin column)
DEL <pin_number>+                 # Delete pins (for derived components)
%SELECT col+ FROM "filename"      # Import pins from TSV file
```

**Pin flags** (graphic modifiers, combinable):
- `N` = not visible, `P` = power, `~` = inverted, `C` = clock
- `F` = falling edge clock, `L` = active low input, `V` = active low output, `X` = non-logic

**Pin electrical types** (single char):
- `I` = input, `O` = output, `B` = bidirectional, `T` = tristate
- `P` = passive, `C` = open collector, `E` = open emitter
- `U` = unspecified, `N` = no connect

**Pin positions**: `L` (left), `R` (right), `T` (top), `B` (bottom); append `C` for center alignment

### Pin Grouping (IEC style)
```
GROUP "qualifiers" <type> "label"
  <pin_def>*
END-GROUP
```
Group types: `-` (no label), `C` (clock), `~` (inverted)

### Example
```
%lib Logic_74xx
%pinlen 200
%width 600
%fill back

COMP 74469 U
FIELD $FOOTPRINT "Package_DIP:DIP-24_W7.62mm"
DESC 8-bit Synchronous Up/Down Counter
KEYW counter
DOC https://example.com/74LS469.pdf
UNIT
3 D0 I L
4 D1 I L
22 Q0 T R
23 CBI I L
UNIT PWR
12 GND PI B
24 VCC PI T
END
```

## Symbol Generation Logic

### Core Pipeline (lib_symgen.py: SymGen class)

1. **Parsing** (`parse_input_file`): Line-by-line tokenizer reads `.txt` file. Skips comments (`#`) and blanks. Uses custom `tokenise()` that handles quoted strings. Builds list of `SgComponent` objects with `IecSymbol` (unit) and `IecElement` children.

2. **Pin Layout**: Pins are placed automatically based on position (L/R/T/B). The engine tracks four position cursors (`pin_pos_left`, `pin_pos_right`, `pin_pos_top`, `pin_pos_bottom`) that advance by 100 mils per pin. `SPC` inserts gaps. Pin stacking allows power pins with matching patterns to share positions.

3. **Box Sizing**: Width is configurable (`%width` or per-unit `WIDTH`). Height is computed from pin count. The bounding box is calculated to center the symbol.

4. **Logic Gate Graphics** (sym_gates.py): For gate-type units (`AND`, `OR`, `XOR`, `NOT`), parametric shape generators create the gate body using arcs, polylines, and circles. Supports:
   - **ANSI/MIL style**: Distinctive shapes (curved OR gates, flat AND gates, triangle NOT)
   - **IEC style**: Rectangular boxes with function labels (`>=1`, `&`, `=1`, `1`)
   - Gates scale for 2-8+ inputs with automatic positioning

5. **Icon Overlay**: `ICON` keyword copies graphic elements from a template library (specified by `%iconlib`) into the symbol unit, allowing reuse of shared graphics.

6. **Inheritance**: `FROM <parent>` derives a component from another, inheriting pins and structure. `EXTENDS n` extends a unit from another. `DEL` removes inherited pins.

7. **Output Generation**: Dispatches to either `GenerateKicad` (v5 legacy) or `GenerateSweetLib` (v6 s-expression) generator class.

### Output Formats

- **v5 legacy** (`gen_legacy.py` -> `GenerateKicad`): Produces `.lib` + `.dcm` files in KiCad v5 format
- **v6 s-expression** (`gen_sweet.py` -> `GenerateSweetLib`): Produces `.kicad_sym` files. Handles per-unit sub-symbols, De Morgan variants, properties with effects, `ki_keywords`/`ki_description`/`ki_fp_filters` metadata

### Reverse Conversion

`convert_library.py`: Parses existing KiCad libraries (both v5 `.lib` and v6 `.kicad_sym`) and dumps them as symgen `.txt` format. Not round-trip exact but useful for bootstrapping.

## Supported Component Types

- **Generic IC symbols**: Rectangular boxes with pins on all four sides (the primary use case)
- **Logic gates**: AND, OR, NAND, NOR, XOR, XNOR, NOT, BUF with both ANSI and IEC drawing styles
- **Power units**: Dedicated power pin units (`UNIT PWR`) with optional separate/combined modes
- **Multi-unit components**: Multiple units per component (e.g., quad gates), with De Morgan variant support
- **Derived/aliased components**: Component inheritance and aliases with per-alias documentation
- **Template components**: Reusable component templates

## Pin Handling

- Automatic sequential placement on each side (L/R/T/B) with 100-mil spacing
- Pin number and name are mandatory; type/flags/position are sticky (inherit from previous pin)
- Special handling for power pins (`P` flag converts I->power_in, O->power_out)
- Inverted pins via `~` prefix on name or `~` flag
- Pin stacking: stackable power pins share positions based on name patterns
- Alternate pin names: slash-separated names create alternate pin functions
- Spacers (`SPC`) for visual grouping
- Pin import from TSV files (`%SELECT ... FROM`)
- Pin deletion for derived components (`DEL`)
- Pin qualifiers for IEC-style annotations

## CLI Interface

```
python sym_gen.py [options]

Options:
  --inp FILE       Symgen script file (.txt)
  --lib FILE       KiCad library file (.lib or .kicad_sym)
  --fp_dir DIR     Folder containing valid footprints
  --ref FILE       7400 logic reference list
  -d, --dump       Dump existing library to symgen format
  -v, --verbose    Enable verbose output
  --regen          Dump and regenerate from script
  --output FORMAT  Output format: v5, v6 (default: v6)
```

Primary workflows:
1. `--inp 74xx.txt` -- generate library from symgen script
2. `--inp 74xx.txt --output v6` -- generate v6 format
3. `-d --lib 74xx.lib` -- convert existing library to symgen text
4. `--regen --lib 74xx.lib` -- dump then regenerate (for format migration)

## Dependencies

- **Python standard library only** (os, sys, argparse, re, math, hashlib, copy, shlex, time, fnmatch, enum)
- **Bundled**: `v5_schlib/schlib.py` and `common/kicad_sym.py` from kicad-library-utils (vendored, not pip-installed)
- **No external pip packages required**

## Included Data/Examples

The `symgen/data/` directory contains working examples:
- `Logic_74xx/` - 74xx series logic ICs with template library
- `DSP_Microchip_DSPIC33/` - Microchip dsPIC33 DSPs
- `Memory_xxx/` - EEPROM, EPROM, Flash, NVRAM, RAM
- `Xilinx/` - Xilinx CPLDs
- `cmos4000/` - CMOS 4000 series logic
- `cmos_ieee/` - CMOS IEC-style symbols

Each directory typically contains: `.txt` (source), `.lib`/`.dcm` (v5 output), and `.bat` (generation scripts).

## Code Quality Assessment

### Strengths
- **Well-documented input format**: BNF grammar and syntax reference included
- **Comprehensive domain coverage**: Handles the full complexity of KiCad symbols (multi-unit, De Morgan, aliases, power pins, IEC/ANSI styles)
- **Zero external dependencies**: Pure Python with vendored KiCad library parsers
- **Bidirectional**: Can both generate from text and reverse-engineer from existing libraries
- **Practical examples**: Multiple real-world library data sets included
- **Parametric gate drawing**: Logic gate shapes are mathematically generated, scaling to different input counts
- **Pin stacking and grouping**: Advanced features for complex ICs

### Weaknesses
- **Python 2/3 compatibility issues**: Uses `.decode('utf-8')` on strings (Python 2), mixed print statements. Will fail on modern Python 3 without fixes.
- **No packaging/setup.py**: No pip installability, no pyproject.toml
- **Class-level mutable defaults**: Extensively uses class-level attributes that are mutable (lists, dicts). This is a well-known Python antipattern that can cause shared state bugs between instances.
- **Heavy use of `from X import *`**: Every module uses wildcard imports, making it hard to trace where names come from and creating namespace pollution
- **Manual tokenizer/parser**: Hand-rolled line-by-line parser instead of using a proper parsing library. Fragile error handling (many bare `print` error messages, no exceptions).
- **No tests**: No test suite of any kind
- **Tight coupling**: The SymGen class is 1350 lines with mixed parsing, layout, and generation logic
- **Windows-centric examples**: Batch files, Windows paths in comments
- **Stale code**: Many TODO/todo comments, commented-out code blocks, dead code paths
- **No type hints**: No typing annotations anywhere
- **Global state**: Uses module-level constants and class-level state extensively
- **Limited error reporting**: No line numbers in error messages, no structured error collection

### Architecture Issues
- The v5 legacy format code is deeply intertwined with the v6 code rather than cleanly separated
- The `Component` class from `schlib.py` is used as an intermediate representation for both input parsing and output, creating unnecessary coupling between the KiCad library format and the internal model
- The generator classes (`GenerateKicad`, `GenerateSweetLib`) inherit from each other but share layout logic that belongs in the parser

## Key Insights for auto-kicad

1. **Text format is the key innovation**: The symgen text format is a well-designed DSL for describing IC symbols compactly. A pin that takes 5+ lines in KiCad's native format is 1 line in symgen. This is worth studying as a reference for any text-based symbol input format.

2. **Pin layout algorithm**: The automatic placement of pins on four sides with spacers, stacking, and grouping is a solved problem here. The approach of maintaining four position cursors and advancing them independently is simple and effective.

3. **Gate drawing math**: The parametric gate shape generators (especially OR gate with arc calculations) represent significant domain knowledge about KiCad symbol graphics.

4. **Reverse engineering capability**: The dump/convert feature shows how to parse existing KiCad libraries and extract structured data, useful for library analysis and migration.

5. **The code needs modernization**: While the domain logic is sound, the implementation would need significant refactoring for Python 3 compatibility, proper packaging, and modern practices before integration into any new project.

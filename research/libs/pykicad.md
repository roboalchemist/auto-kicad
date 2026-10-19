# pykicad (cjlano)

**Source**: `research/libs/pykicad/`
**Author**: CJlano
**License**: GPLv2+
**Language**: Python (no version specified, Python 2/3 compatible)
**Dependencies**: None (stdlib only -- uses `time`)
**Lines of code**: ~183 (single file: `kicad.py`)

## Overview

pykicad is a minimal Python library for **generating** KiCad module library files (legacy `.mod` format). It is explicitly described as "early stage" and was designed as a companion to the SVG2KiCad toolchain (`kicad-utils`). It is write-only -- there is no parser.

## Architecture

Single-module architecture with 5 classes, no inheritance, no external dependencies:

```
kicad.py
  LibModule     -- file-level container, writes .mod files
  Module        -- footprint/module with position, fields, drawings
  Segment       -- line drawing primitive (DS)
  Polygon       -- polygon drawing primitive (DP/Dl)
  Circle        -- circle drawing primitive (DC)
```

All classes use `__str__` for serialization. `LibModule.write()` opens a file and writes the header + index + module string representations.

## S-Expression Parser

**None.** This library does not parse S-expressions at all. It generates the **legacy KiCad format** (pre-S-expression), which uses a line-oriented text format with keywords like `$MODULE`, `$EndMODULE`, `Po`, `Li`, `DS`, `DP`, `DC`, etc.

## Supported File Formats

| Format | Read | Write | Notes |
|--------|------|-------|-------|
| `.mod` (legacy module library) | No | Yes | PCBNEW-LibModule-V1 format only |
| `.kicad_pcb` | No | No | |
| `.kicad_sch` | No | No | |
| `.kicad_mod` (S-expr footprint) | No | No | |
| `.kicad_sym` | No | No | |

Only the legacy module library format is supported, and only for writing.

## Data Model Classes

### LibModule
- Container for a `.mod` file
- Holds a list of `Module` objects
- `write()` method outputs the full file with header, index, and module sections
- Header is generated at import time using `time.strftime`

### Module
- Represents a single footprint/module
- Properties: `name`, `position` (dict with Xpos, Ypos, orientation, layer, timestamp), `cd` (comment), `kw` (keywords), `fields` (list of dicts), `drawings` (list of drawing primitives), `pads` (declared but not implemented)
- Methods: `position()`, `comment()`, `keywords()`, `field()`, `reference()`, `value()`, `draw()`
- Bug: `position` is both an attribute (dict) and a method, causing a name collision

### Segment
- Line segment between two points with width and layer
- Serializes to `DS x1 y1 x2 y2 width layer`

### Polygon
- Filled polygon from a list of points
- Serializes to `DP 0 0 0 0 count width layer` followed by `Dl x y` per point

### Circle
- Circle defined by center and radius
- Serializes to `DC cx cy px py width layer` (px,py = point on circumference)

## Read/Write Capabilities

- **Read**: None. No parsing capability whatsoever.
- **Write**: Legacy `.mod` format only. Write-only via string concatenation in `__str__` methods.

## API Design Patterns

- Plain Python classes with dict-based attribute storage (no dataclasses, no type hints)
- Serialization via `__str__` overrides
- No validation, no error handling
- No context managers for file I/O
- Mutable state with no immutability guarantees

## Code Quality Assessment

- **Very small scope**: 183 lines total, does one thing
- **No tests**: The `kicad.test.py` file is actually an integration script that requires an external `svg` module, not a test suite
- **No packaging**: No `setup.py`, `pyproject.toml`, or `requirements.txt`
- **Bug**: `Module.position` name collision between the dict attribute and the method (method will shadow the dict after first call)
- **Legacy format**: Generates PCBNEW-LibModule-V1, which is obsolete since KiCad 4+ moved to S-expression formats
- **No documentation**: Beyond the brief README

## Strengths

1. Zero dependencies -- pure stdlib Python
2. Extremely simple API for generating footprint silkscreen art
3. Useful as a reference for understanding the legacy `.mod` text format structure

## Weaknesses

1. **Write-only**: No parsing capability at all
2. **Legacy format only**: Does not support modern S-expression `.kicad_mod` format
3. **No S-expression support**: Neither parsing nor generation
4. **Incomplete**: Pads declared but not implemented, only silkscreen drawing supported
5. **No tests, no packaging, no CI**
6. **Name collision bug**: `Module.position` attribute vs method
7. **Abandoned**: Last meaningful development appears very old, no recent updates
8. **Not pip-installable**: No packaging metadata

## Relevance to kicad-agent

**Very low.** This library:
- Does not handle any modern KiCad file format
- Has no S-expression parser (the core need for kicad-agent)
- Is write-only with no round-trip capability
- Covers only legacy footprint library generation for silkscreen art

The only takeaway is a reference for the legacy `.mod` format structure, which is not a priority for kicad-agent. No code or patterns from this library are reusable for our purposes.

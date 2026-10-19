# easyeda2kicad Analysis Report

## Overview

**Repository**: [uPesy/easyeda2kicad.py](https://github.com/uPesy/easyeda2kicad.py)
**Version**: 0.8.0
**License**: AGPL-3.0
**Author**: uPesy (contact@upesy.com)
**Python**: >=3.6
**Dependencies**: pydantic>=2.0.0, requests>2.0.0

A CLI tool that converts electronic components from EasyEDA/LCSC into KiCad libraries, including schematic symbols, PCB footprints, and colored 3D models (.WRL and .STEP). Supports both KiCad v5.x (legacy) and v6.x formats.

## Architecture

### Package Structure

```
easyeda2kicad/
  __main__.py              # CLI entry point (argparse)
  __init__.py              # Version info
  helpers.py               # Utility functions (logging, lib file management, arc math)
  easyeda/                 # EasyEDA data layer
    easyeda_api.py         # HTTP client for EasyEDA/LCSC APIs
    easyeda_importer.py    # Parsers: symbol, footprint, 3D model from API data
    parameters_easyeda.py  # Pydantic/dataclass models for EasyEDA primitives
    svg_path_parser.py     # SVG path command parser (M, L, A, Z)
  kicad/                   # KiCad output layer
    export_kicad_symbol.py       # EasyEDA symbol -> KiCad symbol conversion
    export_kicad_footprint.py    # EasyEDA footprint -> KiCad footprint conversion
    export_kicad_3d_model.py     # OBJ -> WRL conversion + STEP pass-through
    parameters_kicad_symbol.py   # KiCad symbol data models (v5+v6 export methods)
    parameters_kicad_footprint.py # KiCad footprint data models + format templates
```

### Data Flow / Conversion Pipeline

```
LCSC Part ID (e.g. C2040)
  |
  v
EasyedaApi.get_cad_data_of_component()   -- HTTP GET to easyeda.com API
  |
  v
Raw JSON dict (symbol + footprint + 3D metadata)
  |
  +---> EasyedaSymbolImporter     --> EeSymbol (dataclass)
  |      parse shape lines by designator (P=pin, R=rect, E=ellipse, etc.)
  |      |
  |      v
  |    ExporterSymbolKicad        --> convert_to_kicad() --> KiSymbol
  |      |                            coordinate transform (px->mil or px->mm)
  |      v
  |    KiSymbol.export()          --> .kicad_sym (v6) or .lib (v5) text
  |
  +---> EasyedaFootprintImporter  --> ee_footprint (dataclass)
  |      parse shape lines (PAD, TRACK, HOLE, VIA, CIRCLE, ARC, RECT, TEXT, SVGNODE)
  |      |
  |      v
  |    ExporterFootprintKicad     --> KiFootprint
  |      unit conversion (EasyEDA units -> mm), layer mapping
  |      |
  |      v
  |    export()                   --> .kicad_mod file (string template formatting)
  |
  +---> Easyeda3dModelImporter    --> Ee3dModel
         parse SVGNODE JSON for uuid, translation, rotation
         download raw OBJ + STEP from modules.easyeda.com
         |
         v
       Exporter3dModelKicad
         OBJ -> WRL (VRML V2.0) with materials/colors
         STEP: raw binary pass-through
         |
         v
       .wrl + .step files in .3dshapes/ folder
```

## LCSC API Integration

### Endpoints

| Endpoint | Purpose |
|----------|---------|
| `https://easyeda.com/api/products/{lcsc_id}/components?version=6.4.19.5` | Fetch component CAD data (symbol, footprint, 3D metadata) |
| `https://modules.easyeda.com/3dmodel/{uuid}` | Download raw 3D model (OBJ format) |
| `https://modules.easyeda.com/qAxj6KHrDKw4blvCG8QJPs7Y/{uuid}` | Download STEP 3D model |

### API Client (`EasyedaApi`)

- Simple `requests.get()` calls with custom User-Agent header
- No authentication required (public API)
- No rate limiting, retries, or caching
- Returns raw JSON dict; callers access `result` key for CAD data
- 3D model download is optional (only when `download_raw_3d_model=True`)

## Data Models

### EasyEDA Side (parameters_easyeda.py)

Mixed Pydantic v2 BaseModel + Python dataclasses:

**Symbol primitives** (Pydantic): `EeSymbolPinSettings`, `EeSymbolPinDot`, `EeSymbolPinPath`, `EeSymbolPinName`, `EeSymbolPinDotBis`, `EeSymbolPinClock`, `EeSymbolRectangle`, `EeSymbolCircle`, `EeSymbolArc`, `EeSymbolEllipse`, `EeSymbolPolyline`, `EeSymbolPolygon`, `EeSymbolPath`

**Symbol containers** (dataclass): `EeSymbolPin`, `EeSymbolInfo`, `EeSymbol`

**Footprint primitives** (Pydantic): `EeFootprintPad`, `EeFootprintTrack`, `EeFootprintHole`, `EeFootprintVia`, `EeFootprintCircle`, `EeFootprintRectangle`, `EeFootprintArc`, `EeFootprintText`

**Footprint container** (dataclass): `ee_footprint`, `EeFootprintInfo`, `EeFootprintBbox`

**3D Model** (Pydantic + dataclass): `Ee3dModelBase`, `Ee3dModel`

Each model has `convert_to_mm()` methods for unit conversion (EasyEDA uses mils internally: `float(dim) * 10 * 0.0254`).

Pydantic field validators handle EasyEDA's inconsistent data: empty strings to None/False/0, "show" to True, pin type enum conversion, SVG path parsing.

### KiCad Side

**Symbol** (parameters_kicad_symbol.py): `KiSymbolInfo`, `KiSymbolPin`, `KiSymbolRectangle`, `KiSymbolPolygon`, `KiSymbolCircle`, `KiSymbolArc`, `KiSymbolBezier`, `KiSymbol` -- all dataclasses with dual `export_v5()` / `export_v6()` methods.

**Footprint** (parameters_kicad_footprint.py): `KiFootprintPad`, `KiFootprintTrack`, `KiFootprintHole`, `KiFootprintCircle`, `KiFootprintArc`, `KiFootprintText`, `KiFootprintVia`, `KiFootprint` -- dataclasses + string template constants (`KI_PAD`, `KI_LINE`, `KI_CIRCLE`, etc.).

**3D Model**: `Ki3dModel`, `Ki3dModelBase` -- simple position/rotation + raw WRL content.

## CLI Interface

Entry point: `easyeda2kicad` (argparse-based)

### Arguments

| Flag | Description |
|------|-------------|
| `--lcsc_id` | LCSC part number (required, must start with "C") |
| `--symbol` | Export symbol |
| `--footprint` | Export footprint |
| `--3d` | Export 3D model |
| `--full` | Export all three (symbol + footprint + 3D) |
| `--output` | Custom output path (default: `~/Documents/Kicad/easyeda2kicad/`) |
| `--overwrite` | Replace existing component in library |
| `--v5` | Generate KiCad v5.x legacy format |
| `--project-relative` | Use `${KIPRJMOD}` prefix for 3D model paths |
| `--debug` | Enable debug logging |

### Output Structure

```
<output_path>.kicad_sym        # v6 symbol library (S-expression)
<output_path>.lib              # v5 symbol library (legacy text)
<output_path>.pretty/          # Footprint library (one .kicad_mod per component)
<output_path>.3dshapes/        # 3D models (.wrl + .step per component)
```

## Symbol Conversion Details

- EasyEDA shapes are parsed by single-letter designator: P(in), R(ectangle), E(llipse), C(ircle), A(rc), PL(polyline), PG(polygon), PT(path)
- Fields are split by `~` delimiter and mapped to Pydantic models via `dict(zip(Model.__fields__, fields))`
- Coordinate transform: subtract bbox origin, negate Y axis, scale px->mil (v5) or px->mm (v6)
- Pin types mapped: unspecified/input/output/bidirectional/power
- Pin styles: line/inverted/clock/inverted_clock (based on dot/clock display flags)
- Ellipses converted to circles only when radius_x == radius_y (true ellipses skipped)
- SVG paths partially supported: M(ove), L(ine), Z(close) work; C(ubic bezier) is a TODO
- Symbol lib management: regex-based search/replace for update, file append for add

## Footprint Conversion Details

- Unit conversion: all dimensions multiplied by `10 * 0.0254` (EasyEDA units to mm)
- Pad shapes mapped: ELLIPSE->circle, RECT->rect, OVAL->oval, POLYGON->custom
- Custom polygon pads use `gr_poly` primitives with relative coordinates
- Layer mapping via lookup dicts: `KI_PAD_LAYER`, `KI_PAD_LAYER_THT`, `KI_LAYERS` (EasyEDA layer IDs to KiCad layer names)
- Arc computation: full SVG elliptical arc endpoint-to-center conversion per W3C spec
- Drill specification: handles circular and oval drills
- Text placement: reference/value auto-positioned above/below pads
- Output: string template formatting with format constants (not S-expression builder)

## 3D Model Conversion Details

- **WRL generation**: Parses OBJ format (vertices, faces, materials), converts to VRML V2.0
  - Vertices scaled by `1/2.54` (mm to inches for WRL)
  - Materials extracted: diffuse, specular, ambient colors
  - Generates `IndexedFaceSet` geometry per material group
- **STEP**: Raw binary pass-through from EasyEDA's CDN (no conversion)
- Translation/rotation offsets applied relative to footprint bbox origin
- Both formats saved side-by-side in `.3dshapes/` folder

## Code Quality Assessment

### Strengths

1. **Clean separation of concerns**: EasyEDA parsing, KiCad generation, and API access are in separate modules
2. **Dual version support**: v5 and v6 KiCad formats with version-specific export methods on each data model
3. **Comprehensive primitive support**: Handles pins, rectangles, circles, arcs, ellipses, polylines, polygons, paths, pads, tracks, holes, vias, text
4. **Pydantic validation**: Input data sanitized via field validators (handles EasyEDA's messy/inconsistent data)
5. **3D model with color**: WRL export preserves material colors from OBJ, plus STEP for mechanical CAD
6. **Minimal dependencies**: Only pydantic and requests
7. **Library management**: Can append to existing libs, overwrite individual components, create new libs
8. **SVG arc math**: Proper W3C-spec elliptical arc endpoint-to-center conversion

### Weaknesses

1. **No KiCad 7/8 support**: Targets v5 and v6 only; no KiCad 7+ S-expression updates
2. **String template footprint output**: Footprint export uses format strings (`KI_PAD`, `KI_LINE`) instead of structured S-expression generation -- fragile and hard to extend
3. **No test suite in repo**: No test directory, no pytest, no CI visible
4. **Wildcard imports**: `from easyeda2kicad.easyeda.parameters_easyeda import *` and `from easyeda2kicad.kicad.parameters_kicad_symbol import *`
5. **Mixed model paradigm**: Pydantic BaseModel for leaf data, Python dataclasses for containers -- inconsistent
6. **Incomplete SVG path support**: Bezier curves (C command) are TODO, paths treated as polygons
7. **No error handling on API calls**: No retries, timeouts, or graceful failure for network issues
8. **Single-component CLI**: Can only convert one LCSC ID per invocation (no batch mode)
9. **Mutable state in conversion**: Footprint importer mutates input data in-place via `convert_to_mm()` methods
10. **No caching**: Every invocation hits the EasyEDA API, even for the same component
11. **Hardcoded API version**: `version=6.4.19.5` in API endpoint URL
12. **File I/O in exporters**: Exporters both generate content and write files (mixed responsibilities)
13. **Naming inconsistency**: `ee_footprint` class uses lowercase (PEP8 violation), `EeSymbol` uses CamelCase
14. **No multi-unit symbol support**: All symbols exported as single unit
15. **Regex-based library manipulation**: Symbol lib update/delete uses regex on file content -- brittle with special characters

## Key Patterns for Reuse

- **EasyEDA API endpoint structure**: Well-documented CDN paths for 3D models
- **Unit conversion formula**: `dim * 10 * 0.0254` for EasyEDA-to-mm
- **SVG arc endpoint-to-center algorithm**: Complete implementation per W3C SVG spec
- **OBJ-to-WRL conversion**: Vertex/face/material extraction with color preservation
- **EasyEDA shape designator parsing**: Tilde-delimited field extraction pattern
- **Layer ID mapping tables**: EasyEDA layer numbers to KiCad layer names

## Relevance to kicad-agent

This library provides a complete reference for:
1. **EasyEDA/LCSC data access** -- API endpoints, response structure, and 3D model CDN
2. **KiCad symbol/footprint S-expression format** (v5 and v6) -- field structure, coordinate systems, layer naming
3. **3D model integration** -- WRL/STEP file generation and footprint model references
4. **Coordinate system differences** -- EasyEDA pixel units vs KiCad mils (v5) and mm (v6), Y-axis inversion
5. **Pin type/style mapping** between EasyEDA and KiCad enums

The conversion pipeline architecture (parse -> intermediate model -> export) is a good pattern, though the implementation would benefit from structured S-expression output and proper KiCad 7/8 format support.

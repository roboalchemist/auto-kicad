# JLC2KiCad_lib Analysis

**Repository**: https://github.com/TousstNicolas/JLC2KiCad_lib
**Version**: 1.2.3
**License**: MIT
**Author**: TousstNicolas
**Python**: >=3.8
**Lines of Code**: ~1,785 (unique, across 8 source files)
**Dependencies**: `requests`, `KicadModTree`
**Status**: Author considers project "completed" — maintenance-only mode

## Purpose

CLI tool that takes JLCPCB part numbers (e.g., `C1337258`) and generates complete KiCad libraries: schematic symbols (`.kicad_sym`), footprints (`.kicad_mod`), and 3D models (STEP and/or WRL). Data is fetched from the EasyEDA/JLCPCB API.

## Architecture Overview

```
JLC2KiCadLib.py (CLI entry point + orchestrator)
├── helper.py (logging setup, user-agent)
├── symbol/
│   ├── symbol.py (symbol creation + library file management)
│   └── symbol_handlers.py (EasyEDA shape → KiCad symbol S-expression)
└── footprint/
    ├── footprint.py (footprint creation via KicadModTree)
    ├── footprint_handlers.py (EasyEDA shape → KicadModTree objects)
    └── model3d.py (STEP download + WRL generation)
```

### Data Flow

```
JLCPCB Part # (e.g., C1337258)
    │
    ▼
GET easyeda.com/api/products/{part_id}/svgs
    │  → Returns component UUIDs (symbol UUIDs + footprint UUID)
    │
    ├──▶ Footprint Pipeline
    │     GET easyeda.com/api/components/{uuid}
    │       → Returns shape data (tilde-delimited lines), head (origin), title, datasheet
    │     Parse each shape line → dispatch to handler (TRACK, PAD, ARC, CIRCLE, etc.)
    │     Handlers build KicadModTree objects (Pad, Line, Arc, Polygon, etc.)
    │     KicadFileHandler writes .kicad_mod
    │
    ├──▶ 3D Model Pipeline
    │     STEP: GET modules.easyeda.com/qAxj6KHrDKw4blvCG8QJPs7Y/{uuid}
    │       → Raw binary STEP file, saved directly
    │     WRL:  GET easyeda.com/analyzer/api/3dmodel/{uuid}
    │       → OBJ-like text format, converted to VRML 2.0 in-memory
    │
    └──▶ Symbol Pipeline
          GET easyeda.com/api/components/{uuid} (for each symbol unit)
            → Returns shape data (tilde-delimited)
          Parse each shape line → dispatch to handler (R, E, P, T, PL, PG, PT, A, AR)
          Handlers emit KiCad S-expression strings directly
          Write/update .kicad_sym file with regex-based replacement
```

## API Endpoints Used

| Endpoint | Purpose | Response |
|----------|---------|----------|
| `GET easyeda.com/api/products/{part_id}/svgs` | Resolve JLCPCB part# to component UUIDs | JSON with `component_uuid` list |
| `GET easyeda.com/api/components/{uuid}` | Get component shape data (footprint or symbol) | JSON with `dataStr.shape`, `head`, `title`, `c_para` |
| `GET modules.easyeda.com/qAxj6KHrDKw4blvCG8QJPs7Y/{uuid}` | Download STEP 3D model | Binary STEP file |
| `GET easyeda.com/analyzer/api/3dmodel/{uuid}` | Download 3D model in OBJ-like text format | Text (vertices, faces, materials) |

Note: The STEP endpoint uses a hardcoded bucket identifier (`qAxj6KHrDKw4blvCG8QJPs7Y`) extracted from EasyEDA's JS source.

## Conversion Pipeline Details

### EasyEDA Shape Format

EasyEDA stores shapes as tilde-delimited (`~`) strings. The first token identifies the shape type, remaining tokens are parameters. Example:
```
PAD~OVAL~3944~3071~3.543~9.843~1~1~1~1.969~~gge1~~0~
TRACK~0.394~3~~3944 3066 3944 3076~gge2
```

### Footprint Generation

Uses **KicadModTree** library for structured footprint creation:

- **Handler dispatch table**: Maps shape types to handler functions:
  - `TRACK` → Lines (polyline segments)
  - `PAD` → Pads (OVAL, RECT, ELLIPSE, POLYGON shapes; THT/SMT/NPTH types)
  - `ARC` → Arcs (SVG arc path parsing with full center-point parameterization)
  - `CIRCLE` → Circles
  - `SOLIDREGION` → Polygons (SVG path with M/L/A/Z commands)
  - `SVGNODE` → 3D model reference (triggers STEP/WRL download)
  - `RECT` → Rectangles (filled or outline)
  - `HOLE` → Non-plated through-holes
  - `TEXT` → Silkscreen text
  - `VIA` → Warning only (not supported)

- **Layer mapping**: EasyEDA numeric layers → KiCad named layers (e.g., "1"→"F.Cu", "3"→"F.SilkS")
- **Unit conversion**: `mil2mm()` = `value / 3.937` (mils to mm)
- **Origin handling**: Footprint is translated so EasyEDA origin maps to KiCad (0,0)
- **Auto-detection**: SMD vs through-hole attribute set based on pad types present

### Symbol Generation

Generates KiCad S-expression (`.kicad_sym`) **directly as formatted strings** (no AST/library):

- **Handler dispatch table**:
  - `R` → Rectangle
  - `E` → Circle (ellipse)
  - `P` → Pin (with electrical type mapping: 0=unspecified, 1=input, 2=output, 3=bidirectional, 4=power_in)
  - `T` → Text
  - `PL` → Polyline (open)
  - `PG` → Polygon (closed, filled)
  - `PT` → Triangle (SVG path → polygon)
  - `A` → Arc (SVG arc with full W3C center parameterization)
  - `AR` → Arrowhead (SVG path → filled polygon)

- **Library management**: Regex-based search/replace to update existing symbols in `.kicad_sym` files
- **Multi-unit symbols**: Handles multi-part components (multiple `component_uuid` entries)
- **Component properties**: Reference, Value, Footprint, Datasheet, LCSC part#, plus electrical values (Resistance, Capacitance, Inductance, Frequency)

### 3D Model Handling

- **STEP**: Downloaded as binary from EasyEDA's CDN, saved directly. Translation/rotation computed from EasyEDA's `c_origin` and `c_rotation` fields.
- **WRL (VRML 2.0)**: Fetched as OBJ-like text, parsed in-memory (materials via `newmtl/endmtl`, vertices via `v` lines, faces via `usemtl` + vertex indices), then written as VRML `Shape{}` nodes with `IndexedFaceSet` geometry.
- **Model path variables**: Supports KiCad path variables (e.g., `${KICAD6_3DMODEL_DIR}`) for portable library paths.
- **Duplicate prevention**: If both STEP and WRL are generated, only STEP is attached to the footprint.

## CLI Interface

```
JLC2KiCadLib <part#> [<part#> ...]
    -dir OUTPUT_DIR             # Base output directory (default: JLC2KiCad_lib)
    -symbol_lib NAME            # Symbol library name (default: component name)
    -symbol_lib_dir DIR         # Symbol library subdirectory (default: symbol)
    -footprint_lib NAME         # Footprint library name (default: footprint)
    -model_dir DIR              # 3D model subdirectory (default: packages3d)
    -models [STEP|WRL]          # 3D model format(s) (default: STEP)
    -model_base_variable VAR    # KiCad path variable for model paths
    --no_footprint              # Skip footprint generation
    --no_symbol                 # Skip symbol generation
    --skip_existing             # Don't overwrite existing files
    -logging_level LEVEL        # DEBUG/INFO/WARNING/ERROR/CRITICAL
    --log_file                  # Write logs to file
```

## Output Structure

```
<output_dir>/
├── <footprint_lib>/            # e.g., "footprint/"
│   ├── <name>.kicad_mod        # One per component footprint
│   └── <model_dir>/            # e.g., "packages3d/"
│       ├── <name>.step
│       └── <name>.wrl
└── <symbol_lib_dir>/           # e.g., "symbol/"
    └── <symbol_lib>.kicad_sym  # All symbols in one file
```

## Code Quality Assessment

### Strengths

1. **Clean handler-based architecture**: Both footprint and symbol processing use dispatch tables mapping shape types to handler functions. Easy to extend.
2. **Comprehensive shape support**: Handles arcs (with full W3C SVG spec center parameterization), polygons, solid regions, custom-shape pads — most EasyEDA primitives are covered.
3. **Proper use of KicadModTree**: Footprint generation leverages the official KiCad footprint generator library for structured output.
4. **Practical features**: Skip-existing, multiple model formats, path variables, library update (not just create).
5. **Small footprint**: ~1,785 LOC total. Easy to understand and modify.
6. **Minimal dependencies**: Only `requests` and `KicadModTree`.

### Weaknesses

1. **No programmatic API**: Everything runs through `argparse` CLI. No `create_component(part_id, **options)` function for library use. The `add_component()` function takes an `argparse.Namespace` object.
2. **Symbol generation via string concatenation**: Unlike footprints (which use KicadModTree), symbols are built by concatenating raw S-expression strings with f-strings. No validation, no AST — fragile and hard to extend.
3. **No error handling on API responses**: `json.loads(response.content.decode())` with no try/except. If EasyEDA returns unexpected JSON, it crashes.
4. **Hardcoded API endpoint for STEP models**: Uses a magic constant (`qAxj6KHrDKw4blvCG8QJPs7Y`) extracted from EasyEDA's minified JS. Will break silently if EasyEDA changes their CDN.
5. **No caching**: Every invocation re-downloads all data from EasyEDA. No local cache for repeated conversions.
6. **Regex-based library updates**: `update_library()` uses regex to find/replace symbol definitions in `.kicad_sym` files. Fragile — could corrupt files if symbol names contain regex metacharacters.
7. **No tests**: No test directory, no test files. Zero test coverage.
8. **KiCad version**: Outputs `kicad_symbol_lib (version 20210201)` — this is KiCad 6 format. KiCad 7/8 use newer format versions, though they maintain backward compatibility.
9. **Symbol class as inner class**: `kicad_symbol` is defined as a class inside `create_symbol()` with mutable class attributes. Unusual pattern, works but confusing.
10. **No rate limiting**: Rapid batch processing could hit EasyEDA API rate limits.
11. **Layer mapping gaps**: Some EasyEDA layers map to `User.Comments` as a fallback. Missing layers could cause incorrect placement.

### Architecture Patterns Worth Noting

- **Two-tier handler system**: Shape type dispatch is used in both footprint and symbol generation but with different handler signatures and output mechanisms (KicadModTree objects vs. string appending).
- **SVG arc parameterization**: Both footprint and symbol handlers implement the W3C SVG arc center parameterization algorithm (F.6.5). The code is duplicated between `footprint_handlers.py` and `symbol_handlers.py`.
- **WRL generation**: Custom OBJ-to-VRML converter. Handles materials (ambient, diffuse, specular, transparency) and indexed face sets.

## Key Takeaways for kicad-agent

1. **EasyEDA API is the data source**: The `easyeda.com/api/products/{id}/svgs` and `easyeda.com/api/components/{uuid}` endpoints are the key integration points for JLCPCB component data.
2. **Shape format is tilde-delimited**: EasyEDA's internal shape representation uses `~` as delimiter with type as first token.
3. **KicadModTree is the standard footprint library**: Used by both this project and the official kicad-footprint-generator.
4. **Symbol generation has no standard library**: This project (and likely others) resort to string concatenation for `.kicad_sym` output. This is a gap in the KiCad ecosystem.
5. **Unit conversion**: EasyEDA uses mils (1 mil = 0.0254mm), conversion is `value / 3.937`.
6. **The handler pattern is proven**: Dispatch tables mapping shape types to handler functions work well for both footprint and symbol conversion. Worth adopting.
7. **Multi-format 3D support**: STEP (direct download) + WRL (OBJ→VRML conversion) covers the two formats KiCad supports.

# lamaalrajih/kicad-mcp Analysis Report

**Repository**: https://github.com/lamaalrajih/kicad-mcp
**License**: MIT
**Python**: 3.10+
**KiCad**: 9.0+
**MCP Framework**: FastMCP 2.x

---

## Architecture Overview

This is the most feature-complete and well-structured KiCad MCP server among the analyzed implementations. It follows a clean modular architecture with clear separation of concerns:

```
kicad_mcp/
  server.py          # FastMCP server creation, signal handling, cleanup
  config.py          # Platform-specific configuration constants
  context.py         # Async lifespan context management (KiCadAppContext)
  resources/         # 6 resource modules (read-only data sources)
  tools/             # 8 tool modules (actionable operations)
  prompts/           # 4 prompt modules (conversation templates)
  utils/             # 12 utility modules (CLI, parsing, security, etc.)
```

**Key design decisions:**
- Uses `FastMCP` (not raw `mcp` SDK) for cleaner decorator-based registration
- CLI-first approach: explicitly removed KiCad Python API dependency, relies on `kicad-cli`
- Modular registration pattern: each domain has a `register_*()` function called from `server.py`
- Async lifespan context with in-memory cache (`KiCadAppContext`)
- Graceful shutdown with signal handlers, atexit hooks, and temp dir cleanup

---

## Technology Stack & Dependencies

| Dependency | Purpose |
|-----------|---------|
| `fastmcp>=2.0.0` | MCP server framework |
| `mcp[cli]>=1.0.0` | MCP protocol SDK |
| `pandas>=2.0.0` | BOM data analysis |
| `pyyaml>=6.0.0` | YAML config parsing |
| `defusedxml>=0.7.0` | Secure XML parsing (BOM files) |

**Dev tools**: ruff, mypy, bandit, pytest (with pytest-asyncio, pytest-cov, pytest-xdist), pre-commit

**Optional deps**: cairosvg, Pillow, playwright (visualization), sphinx (docs)

---

## Complete MCP Tools (20 tools)

### Project Management (3 tools)
| Tool | Signature | Description |
|------|-----------|-------------|
| `list_projects` | `() -> List[Dict]` | Scan configured directories for all `.kicad_pro` files |
| `get_project_structure` | `(project_path: str) -> Dict` | Return project files, metadata, directory info |
| `open_project` | `(project_path: str) -> Dict` | Launch KiCad app with specified project (macOS `open -a`, Linux `xdg-open`) |

### Analysis & Validation (3 tools)
| Tool | Signature | Description |
|------|-----------|-------------|
| `validate_project` | `(project_path: str) -> Dict` | Check for missing PCB/schematic files, JSON validity |
| `validate_project_boundaries` | `(project_path: str, ctx) -> Dict` | Validate component positions against A4 schematic bounds |
| `generate_validation_report` | `(project_path: str, output_path: str, ctx) -> Dict` | Generate and save JSON boundary validation report |

### PCB Visualization (2 tools)
| Tool | Signature | Description |
|------|-----------|-------------|
| `generate_pcb_thumbnail` | `(project_path: str, ctx) -> Image` | Export SVG thumbnail via `kicad-cli pcb export svg` with layer selection |
| `generate_project_thumbnail` | `(project_path: str, ctx) -> Image` | Alias for `generate_pcb_thumbnail` |

### Design Rule Checking (2 tools)
| Tool | Signature | Description |
|------|-----------|-------------|
| `run_drc_check` | `(project_path: str, ctx) -> Dict` | Run DRC via `kicad-cli pcb drc --format json`, save to history, compare with previous |
| `get_drc_history_tool` | `(project_path: str) -> Dict` | Retrieve stored DRC history with trend analysis (improving/degrading/stable) |

### BOM Management (2 tools)
| Tool | Signature | Description |
|------|-----------|-------------|
| `analyze_bom` | `(project_path: str, ctx) -> Dict` | Parse CSV/XML/JSON BOMs, analyze component counts, categories, costs |
| `export_bom_csv` | `(project_path: str, ctx) -> Dict` | Generate BOM via `kicad-cli sch export bom` |

### Netlist Analysis (4 tools)
| Tool | Signature | Description |
|------|-----------|-------------|
| `extract_schematic_netlist` | `(schematic_path: str, ctx) -> Dict` | Parse `.kicad_sch` S-expressions to extract components, nets, labels |
| `extract_project_netlist` | `(project_path: str, ctx) -> Dict` | Convenience wrapper: find schematic from project, then extract netlist |
| `analyze_schematic_connections` | `(schematic_path: str, ctx) -> Dict` | Identify power nets, signal nets, floating nets (potential issues) |
| `find_component_connections` | `(project_path: str, component_ref: str, ctx) -> Dict` | Find all nets/pins connected to a specific component (e.g., "U3") |

### Circuit Pattern Recognition (2 tools)
| Tool | Signature | Description |
|------|-----------|-------------|
| `identify_circuit_patterns` | `(schematic_path: str, ctx) -> Dict` | Identify power supplies, amplifiers, filters, oscillators, digital interfaces, MCUs, sensors |
| `analyze_project_circuit_patterns` | `(project_path: str, ctx) -> Dict` | Convenience wrapper: find schematic from project, then identify patterns |

---

## MCP Resources (13 resources)

| URI Pattern | Description |
|-------------|-------------|
| `kicad://project/{project_path}` | Markdown-formatted project details (files, metadata) |
| `kicad://schematic/{schematic_path}` | Basic schematic info (estimated component count, sample) |
| `kicad://drc/{project_path}` | Full DRC report with violations, categories, recommendations |
| `kicad://drc/history/{project_path}` | DRC history with ASCII trend chart, progress tracking |
| `kicad://bom/{project_path}` | Markdown BOM report with categories, costs, component table |
| `kicad://bom/{project_path}/csv` | Raw CSV BOM data |
| `kicad://bom/{project_path}/json` | JSON BOM data with analysis |
| `kicad://netlist/{schematic_path}` | Netlist report (components, nets, connections) |
| `kicad://project_netlist/{project_path}` | Project-level netlist report |
| `kicad://component/{schematic_path}/{component_ref}` | Deep component analysis (pins, connections, properties) |
| `kicad://patterns/{schematic_path}` | Circuit pattern analysis report |
| `kicad://patterns/project/{project_path}` | Project-level circuit pattern report |

---

## MCP Prompts (14 prompts)

### General (3)
- `create_new_component` - Guide for creating KiCad components
- `debug_pcb_issues` - Systematic PCB troubleshooting
- `pcb_manufacturing_checklist` - Pre-manufacturing verification

### DRC (2)
- `fix_drc_violations` - Step-by-step DRC error resolution
- `custom_design_rules` - Custom DRC rule configuration

### BOM (5)
- `analyze_components` - Component distribution analysis
- `cost_estimation` - Prototype/production cost estimation
- `bom_export_help` - BOM export guidance
- `component_sourcing` - Supplier and availability guidance
- `bom_comparison` - Cross-revision BOM diff

### Pattern Analysis (4)
- `analyze_circuit_patterns` - General circuit block identification
- `analyze_power_supplies` - Power supply circuit review
- `analyze_sensor_interfaces` - Sensor integration review
- `analyze_microcontroller_connections` - MCU pin mapping review
- `find_and_improve_circuits` - Circuit improvement suggestions
- `compare_circuit_patterns` - Cross-design pattern comparison
- `explain_circuit_function` - Circuit function explanation

---

## Circuit Pattern Recognition Capabilities

The pattern recognition engine (`utils/pattern_recognition.py`, ~860 lines) uses regex-based component identification against known part numbers. Recognized patterns:

### Power Supplies
- **Linear regulators**: 78xx, 79xx, LDO families (LM, LD, AMS, LT, TLV, AP, MIC, NCP, LP, TPS)
- **Switching regulators**: Buck, boost, buck-boost (LM, TPS, MP, RT, LT, MC, NCP, TL, LTC, MAX)
- Identifies regulator IC + inductor pairs for switching supplies

### Amplifiers
- **Op-amps**: General purpose (LM358, TL072, etc.), audio (NE5534, OPA134), instrumentation (INA, AD620)
- **Transistor amplifiers**: BJT and FET with biasing network detection
- **Audio amplifier ICs**: LM386, TDA, TPA, SSM, PAM, TAS families

### Filters
- **Passive**: RC low-pass (resistor + capacitor to ground)
- **Active**: Op-amp with feedback RC components
- **Crystal/ceramic filters**: Y/X prefix components

### Oscillators
- Crystal oscillators with load capacitor detection
- Oscillator ICs
- RC oscillators (555 timer family)

### Digital Interfaces
- I2C (SCL/SDA signal detection)
- SPI (MOSI/MISO/SCK/SS)
- UART (TX/RX)
- USB (D+/D- signals + interface ICs like FT232, CH340, CP210)
- Ethernet (TX/RX pairs + PHY ICs like W5500, ENC28J60)

### Microcontrollers
- AVR (ATmega, ATtiny), STM32, PIC, ESP32/ESP8266, MSP430, RP2040, NXP, SAM, 8051
- Development boards: Arduino, NodeMCU, Nucleo, Discovery, BluePill, Raspberry Pi Pico

### Sensors (~40 specific IC patterns)
- Temperature: DS18B20, BME280, LM35, DHT11/22, TMP, MCP9808, MAX31855
- Motion: MPU6050, MPU9250, ADXL, LIS3DH, LSM6DS3
- Optical: APDS9960, VL53L0X, BH1750, TSL
- Pressure, humidity, air quality, current, voltage, ADC, GPS
- Analog sensors: thermistors, photodiodes, LDRs, potentiometers

---

## KiCad Interface Approach

**CLI-based** -- the server explicitly removed all KiCad Python API (`pcbnew`) dependencies. All KiCad operations use `kicad-cli`:

### CLI Commands Used
| Operation | Command |
|-----------|---------|
| PCB thumbnail | `kicad-cli pcb export svg --output <file> --layers F.Cu,B.Cu,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts <pcb>` |
| DRC check | `kicad-cli pcb drc --format json --output <file> <pcb>` |
| BOM export | `kicad-cli sch export bom --output <file> <sch>` |
| Open project | `open -a KiCad.app <project>` (macOS) / `xdg-open` (Linux) |

### CLI Detection
Two parallel implementations exist (a design flaw):
1. `utils/kicad_cli.py` - `KiCadCLIManager` class with caching, env var override (`KICAD_CLI_PATH`), platform-specific paths, validation
2. `tools/drc_impl/cli_drc.py` - Standalone `find_kicad_cli()` with `which`/`where` + hardcoded paths

The `KiCadCLIManager` is the more robust implementation but the DRC tool uses its own simpler finder.

### Schematic Parsing
Direct parsing of `.kicad_sch` S-expression format via `utils/netlist_parser.py`:
- Extracts components, wires, junctions, labels (local/global/hierarchical), power symbols, no-connects
- **Limitation**: The `_build_netlist()` method has a `TODO` comment -- full wire connectivity tracing is not implemented. Nets are only built from labels and power symbols, not from wire geometry tracing.

---

## Security Considerations

**Strong security posture** -- several dedicated security utilities:

1. **`PathValidator`** (`utils/path_validator.py`):
   - Trusted root directories with path traversal prevention
   - Symlink resolution via `os.path.realpath()`
   - KiCad file extension validation
   - Safe temp file creation within trusted directories

2. **`SecureSubprocessRunner`** (`utils/secure_subprocess.py`):
   - Input/output file path validation before command execution
   - Working directory validation
   - Command whitelist support (`allowed_commands` parameter)
   - Configurable timeouts from `TIMEOUT_CONSTANTS`
   - Async wrapper for non-blocking execution

3. **`defusedxml`** for XML BOM parsing (prevents XXE attacks)

4. **`bandit`** in dev dependencies for security linting

**However**: The `SecureSubprocessRunner` is defined but not consistently used. Export tools and DRC tools call `subprocess.run()` directly instead of using the secure runner.

---

## Code Quality Assessment

### Strengths
- **Comprehensive documentation**: 11 doc guides in `docs/`, detailed docstrings, extensive README
- **Well-organized modules**: Clean separation between resources/tools/prompts/utils
- **Type hints throughout**: `mypy` configured with strict options
- **Progress reporting**: All async tools report progress via `ctx.report_progress()`
- **Error handling**: Consistent error return format `{"success": False, "error": "..."}`
- **Caching**: Thumbnail caching via lifespan context, CLI path caching via `KiCadCLIManager`
- **DRC history tracking**: Persistent history with trend analysis and ASCII visualization
- **BOM format detection**: Handles CSV, XML, JSON with delimiter auto-detection
- **Pattern recognition**: Extensive part number database for circuit identification
- **Testing infrastructure**: pytest with coverage, markers, asyncio support

### Weaknesses
- **Duplicate CLI detection**: Two separate `find_kicad_cli` implementations that could diverge
- **Incomplete netlist builder**: `_build_netlist()` has TODO -- cannot trace wire connectivity, only label-based nets
- **Inconsistent security usage**: `SecureSubprocessRunner` exists but direct `subprocess.run()` calls bypass it
- **Excessive print statements**: Many tools use `print()` instead of `logging`, mixing stdout with MCP stdio transport
- **Dead code paths**: `kicad_modules_available` is always `False` but code paths still check it (BOM export)
- **Validation tools not registered**: `register_validation_tools()` defined in `validation_tools.py` but NOT called in `server.py`
- **Boundary validator imports**: References `component_layout.py` and `coordinate_converter.py` which are not in the repo (would cause import errors)
- **No `subprocess` timeout in DRC CLI**: `subprocess.run()` in `cli_drc.py` has no timeout parameter
- **Test coverage minimal**: Only 2 unit test files (path_validator, secure_subprocess) -- no tool or resource tests
- **Config reload hack**: `main.py` uses `importlib.reload(config)` to handle dotenv loading order -- fragile

### Notable Design Patterns
- **Register pattern**: Each module exports a `register_*(mcp)` function -- clean and composable
- **Dual-path tools**: Many operations have both project-path and schematic-path variants
- **Resource/tool symmetry**: DRC, BOM, netlist, patterns each have both resources (read-only) and tools (actionable)
- **Lifespan context**: FastMCP lifespan with `functools.partial` for kwargs -- handles server init/shutdown lifecycle

---

## Summary Statistics

| Metric | Count |
|--------|-------|
| MCP Tools | 20 |
| MCP Resources | 13 |
| MCP Prompts | 14+ |
| Python source files | ~30 |
| Utility modules | 12 |
| Lines of code (est.) | ~5,000+ |
| Doc guides | 11 |
| Test files | 2 |
| Recognized sensor ICs | ~40 patterns |
| MCU families recognized | 11 |
| Digital interfaces detected | 5 (I2C, SPI, UART, USB, Ethernet) |

---

## Key Differentiators

1. **Richest feature set**: Most tools, resources, and prompts of any analyzed KiCad MCP server
2. **Circuit pattern recognition**: Unique capability -- no other implementation has this
3. **DRC history tracking**: Persistent history with trend analysis and comparison
4. **BOM analysis with pandas**: Multi-format parsing, cost estimation, category mapping
5. **Security infrastructure**: Path validation and secure subprocess runner (though inconsistently used)
6. **Extensive prompt library**: 14+ domain-specific conversation starters
7. **Multiple output formats**: Resources available as markdown, CSV, and JSON

## Weaknesses to Learn From

1. **Incomplete netlist connectivity** limits usefulness of connection analysis tools
2. **Dead/broken imports** (boundary_validator -> missing modules) would cause runtime errors
3. **Unregistered tools** (validation_tools) -- code exists but isn't wired up
4. **Minimal test coverage** despite test infrastructure being configured
5. **Print vs logging inconsistency** could interfere with stdio MCP transport

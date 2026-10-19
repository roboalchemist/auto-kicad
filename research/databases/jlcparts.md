# jlcparts (yaqwsx/jlcparts)

A client-side parametric search tool for the JLC PCB SMT assembly component catalogue. Hosted as a static site on GitHub Pages with no backend -- all queries run locally in the browser via IndexedDB.

**Author**: Jan Mrazek (yaqwsx)
**License**: MIT
**Language**: Python (data pipeline) + JavaScript/React (frontend)
**URL**: https://github.com/yaqwsx/jlcparts

## Architecture Overview

The system has two distinct halves:

1. **Python data pipeline** -- scrapes JLCPCB and LCSC APIs, builds a SQLite database, then exports per-category JSON files for the static frontend.
2. **React web UI** -- downloads those JSON files into browser IndexedDB and provides parametric search, sorting, and filtering entirely client-side.

```
JLCPCB API ──> CSV ──> SQLite DB ──> per-category JSON.gz ──> GitHub Pages
                         ▲                                         │
                    LCSC API                                       ▼
                  (extra data)                              Browser IndexedDB
                                                           (Dexie.js wrapper)
                                                                   │
                                                                   ▼
                                                          React UI (parametric
                                                          search, sort, filter)
```

## Data Pipeline

### Step 1: Fetch Component Table (`jlcparts fetchTable`)

- Uses JLCPCB's external API (`jlcpcb.py`) with `JLCPCB_KEY`/`JLCPCB_SECRET` env vars
- Authenticates via `POST /external/genToken`, then paginates through `POST /external/component/getComponentInfos`
- Outputs a CSV with columns: LCSC Part, First Category, Second Category, MFR.Part, Package, Solder Joint, Manufacturer, Library Type, Description, Datasheet, Stock, Price

### Step 2: Build Library Database (`jlcparts getLibrary`)

- Reads the CSV, upserts into a SQLite database (`PartLibraryDb`)
- For new/stale components, fetches extra data from LCSC API (`lcsc.py`) using `LCSC_KEY`/`LCSC_SECRET` env vars
- LCSC requests use HMAC-SHA1 signed authentication: `GET https://ips.lcsc.com/rest/wmsc2agent/product/info/{lcscNumber}`
- Extra data includes: detailed attributes, images, product URLs, manufacturer info
- Uses multiprocessing pool (10 workers) for parallel fetching
- Supports incremental updates with `--age` (refresh N oldest) and `--limit` flags
- Marks preferred components via separate `updatePreferred` command

### Step 3: Build Static Data Tables (`jlcparts buildtables`)

- Reads from SQLite, groups components by category/subcategory
- For each subcategory, outputs:
  - `{category}.json.gz` -- gzipped JSON with component data + attribute schema
  - `{category}.stock.json` -- stock levels (separate for lightweight updates)
  - SHA256 hash files for cache invalidation
- Generates `index.json` mapping categories to their source files and hashes
- Supports parallel processing (`--jobs 0` = all cores)
- `--ignoreoldstock N` filters out components not in stock for N+ days

## Database Schema (SQLite)

### Tables

**components**
| Column | Type | Notes |
|--------|------|-------|
| lcsc | INTEGER PK | LCSC number without "C" prefix (e.g., C7063 -> 7063) |
| category_id | INTEGER FK | References categories.id |
| mfr | TEXT | Manufacturer part number |
| package | TEXT | Package type (0402, SOIC-8, etc.) |
| joints | INTEGER | Solder joint count |
| manufacturer_id | INTEGER FK | References manufacturers.id |
| basic | INTEGER | 1 = basic part (lower assembly fee) |
| preferred | INTEGER | 1 = JLCPCB preferred part |
| description | TEXT | Part description |
| datasheet | TEXT | Datasheet URL |
| stock | INTEGER | Current stock level |
| price | TEXT | JSON string of price breaks `[{qFrom, qTo, price}]` |
| last_update | INTEGER | Unix timestamp of last LCSC fetch |
| last_on_stock | INTEGER | Unix timestamp when last in stock |
| extra | TEXT | JSON blob of all LCSC extra data (attributes, images, URLs) |
| flag | INTEGER | Internal flag for incremental sync (0=old, 1=refreshed) |

**categories**
| Column | Type |
|--------|------|
| id | INTEGER PK |
| category | TEXT |
| subcategory | TEXT |

**manufacturers**
| Column | Type |
|--------|------|
| id | INTEGER PK |
| name | TEXT |

**v_components** (view) -- joins components + categories + manufacturers for easy querying.

## JSON Output Format

Each category JSON file has this structure:
```json
{
  "category": "Resistors",
  "subcategory": "Chip Resistor - Surface Mount",
  "schema": ["lcsc", "mfr", "joints", "description", "datasheet", "price", "img", "url", "attributes"],
  "components": [
    ["C7063", "RC0402JR-0710KL", 2, "10kOhm ...", "http://...", [...prices], "img.jpg", "slug", {...attrs}]
  ]
}
```

Components are stored as arrays (not objects) to minimize JSON size; the `schema` array provides field names.

### Attribute Format (Normalized)

Attributes are normalized into structured objects:
```json
{
  "Resistance": {
    "format": "${Resistance}",
    "primary": "Resistance",
    "values": {
      "Resistance": [10000, "resistance"]
    }
  }
}
```

Each attribute value is a tuple `[numericValue, unitType]` where unitType is one of: `resistance`, `voltage`, `current`, `power`, `capacitance`, `inductance`, `temperature`, `charge`, `count`, `frequency`, `length`, `string`. This enables type-aware sorting and formatting on the frontend.

The `attributes.py` module (750+ lines) handles parsing of dozens of attribute types from LCSC's inconsistent strings (with SI prefixes, units, ranges, compound values like "RDS(on)@Vgs,Id").

## Web UI

### Tech Stack
- **React 16** with class components (no hooks)
- **Tailwind CSS 1.x** (via PostCSS)
- **Dexie.js 3.x** -- IndexedDB wrapper for client-side storage
- **pako** -- gzip decompression in browser
- **react-router-dom 5** (HashRouter)
- **immer** -- immutable state updates
- **Font Awesome** icons

### Client-Side Database (IndexedDB via Dexie)

```javascript
db.version(1).stores({
    settings: 'key',
    components: 'lcsc, category, mfr, *indexWords',
    categories: 'id++,[category+subcategory], subcategory, category'
});
```

- `components` table indexed on `lcsc`, `category`, `mfr`, and multi-entry `indexWords` for full-text search
- `categories` table with compound index on `[category+subcategory]`
- SHA256 hashes stored per category to enable incremental updates (only re-download changed categories)

### Parametric Search Implementation

1. **Category browsing**: User selects category/subcategory, components loaded from IndexedDB
2. **Full-text search**: Components indexed by `indexWords` (split from lcsc + mfr + description)
3. **Attribute columns**: User adds attribute columns from a dropdown; each column shows the normalized attribute value
4. **Sorting**: `SortableTable` component sorts by any column using type-aware comparators (`units.js`):
   - Numeric quantities (resistance, voltage, etc.) use numeric comparison
   - String quantities use natural comparison (`@discoveryjs/natural-compare`)
5. **Price sorting**: Sort by unit price at specific quantity breakpoints
6. **Attribute filtering**: Filter by attribute value ranges within a category

### Cache Download Mechanism

On first visit:
1. Frontend fetches `data/index.json` from GitHub Pages
2. For each category, fetches `{sourcename}.json.gz` (gzip-compressed)
3. Decompresses with pako, stores into IndexedDB
4. On subsequent visits, compares SHA256 hashes -- only re-downloads changed categories
5. Stock levels update separately via lightweight `.stock.json` files

The initial download is large (all JLCPCB components) and can take a while. After that, all queries are local.

## How to Use Offline

1. Download the pre-built cache: `wget https://yaqwsx.github.io/jlcparts/data/cache.zip` (+ split volumes `cache.z01..z08`)
2. Extract: `7z x cache.zip` (produces `cache.sqlite3`)
3. Build JSON tables: `jlcparts buildtables cache.sqlite3 web/public/data/`
4. Serve locally: `cd web && npm install && npm start`

Alternatively, just visit the GitHub Pages site once -- the IndexedDB cache persists across browser sessions.

## Strengths

- **No backend required** -- fully static hosting, runs on GitHub Pages for free
- **Parametric search** -- the killer feature JLCPCB's own UI lacks; type-aware sorting for resistance, capacitance, voltage, etc.
- **Incremental updates** -- SHA256 hash-based diffing means only changed categories are re-downloaded
- **Rich attribute normalization** -- extensive parsing of LCSC's messy attribute strings into structured, sortable values (750+ lines of parsing code)
- **Separate stock updates** -- lightweight stock-only JSON files for frequent updates without full re-download
- **Offline-capable** -- once downloaded, all queries run locally from IndexedDB
- **Price-aware** -- sort by unit price at different quantity breakpoints

## Weaknesses

- **Large initial download** -- entire JLCPCB catalogue must be loaded into browser IndexedDB before first use; can take significant time/bandwidth
- **Stale React/tooling** -- React 16 class components, Tailwind 1.x, no TypeScript; would need modernization
- **JLCPCB-specific** -- tightly coupled to JLCPCB's API and component structure; not usable for generic component search
- **API keys required for scraping** -- needs `JLCPCB_KEY`/`JLCPCB_SECRET` and `LCSC_KEY`/`LCSC_SECRET` environment variables; not documented how to obtain these
- **No KiCad integration** -- purely a web browsing/search tool; no symbol/footprint data, no direct KiCad library output
- **Limited search within browser** -- IndexedDB queries are less powerful than SQL; no complex joins or aggregations
- **Single developer project** -- maintenance depends on one person (yaqwsx, also author of KiKit and PcbDraw)
- **CI/space issues noted** -- README and code comments mention space-related CI issues; `db.vacuum()` is disabled as a workaround

## Relevance to KiCad-Claude

**Useful patterns to adopt**:
- Attribute normalization approach (`attributes.py`) for parsing component parameters into sortable numeric values
- SHA256-based incremental cache updates
- The schema+array JSON format for compact component serialization

**Not directly usable because**:
- No KiCad symbol/footprint data
- JLCPCB-only component coverage
- The web UI architecture (browser IndexedDB) doesn't translate to a KiCad plugin workflow
- Would need a fundamentally different approach for KiCad integration (local database, not browser-based)

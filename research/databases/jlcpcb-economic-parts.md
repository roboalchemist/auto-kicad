# jlcpcb-economic-parts Analysis

**Source**: https://github.com/lrks/jlcpcb-economic-parts
**Author**: lrks
**Purpose**: Weekly-updated lists of JLCPCB's Economic Parts (Basic + Preferred Extended) in CSV and HTML formats.

## Scraping Method

- **API**: `download.py` POSTs to JLCPCB's internal SMT component API endpoint (`/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList/v2`)
- **Pagination**: Fetches 100 parts per page, iterates until all pages consumed, 1-second delay between requests
- **Parameters**: Requests with `componentLibraryType: 'base'` and `preferredComponentFlag: True`, which returns both Basic and Preferred Extended parts
- **Output**: Raw JSON saved as `parts-page{N}.json` files
- **No auth required**: Uses JLCPCB's public-facing API (no API key)

## CSV Format and Fields

`generate-csv.py` processes the JSON pages into `economic-parts.csv` with these columns:

| Column | Description |
|--------|-------------|
| `code` | JLCPCB component code (e.g., C1234) |
| `url` | URL suffix for part detail page |
| `file` | Datasheet file access ID |
| `library` | `base` (Basic) or other (Preferred Extended) |
| `deleted` | `0` = active, `1` = no longer in economic parts list |
| `lastSeen` | UTC timestamp of last scrape where part appeared |
| `brand` | Component brand (English) |
| `model` | Component model (English) |
| `package` | Package/specification (English) |
| `type` | Component category/type (English) |
| `describe` | Part description |
| `erpComponentName` | ERP component name |
| `price` | Unit price at MOQ (cheapest tier >= MOQ) |
| `stock` | Current stock count |
| `MOQ` | Minimum order quantity |

## Data Scope

- **Economic parts only**: Basic parts (no extra fee) and Preferred Extended parts (reduced fee vs standard extended)
- **NOT included**: Standard extended parts, all 100K+ JLCPCB parts
- **Deletion tracking**: When parts drop out of the economic list, they're marked `deleted=1` rather than removed, preserving history
- **Sorted by**: Component code, with deleted parts sorted after active ones

## Update Mechanism

- **Weekly automation** via GitHub Actions (workflow files not in local clone but referenced in README)
- **Incremental updates**: `generate-csv.py` merges new data with existing CSV, tracking deletions
- **GitHub Pages hosting**: HTML and CSV published at `lrks.github.io/jlcpcb-economic-parts/`

## How to Use

1. **Direct download**: Grab `economic-parts.csv` from GitHub Pages
2. **Browse online**: HTML tables at the GitHub Pages URL with sorting, filtering, stock highlighting
3. **Run locally**: `python download.py` then `python generate-csv.py` to get fresh data
4. **For KiCad integration**: CSV could be imported into a KiCad database library, mapping `code` to LCSC part number, `package` to footprint, `type` to category

## HTML Viewer Features

`generate-html.py` produces two views:
- **Full list** (`index.html`): All parts including deleted, with stock/MOQ color coding
- **Active list** (`active.html`): Filters out deleted parts, out-of-stock (< 10), and high MOQ (> 5)
- Uses jQuery TableSorter with filtering, sticky headers, zebra striping
- Stock highlighted: green (> 100), yellow (10-100), red (< 10)
- MOQ highlighted: normal (1), yellow (2-5), red (> 5)

## Strengths

- **Simple and focused**: Three clean Python scripts, easy to understand and modify
- **Economic parts filter**: Specifically targets the no-fee / low-fee parts that matter for cost-optimized PCB assembly
- **Deletion tracking**: Preserves history of parts leaving the economic list
- **Active view**: Pre-filtered view showing only practically usable parts (in-stock, low MOQ)
- **No dependencies beyond requests/pandas**: Lightweight scraper
- **Weekly updates**: Reasonably fresh data via GitHub Actions

## Weaknesses

- **No parametric data**: Only has brand/model/package/description -- no electrical parameters (resistance, capacitance, voltage rating, etc.)
- **No footprint mapping**: No KiCad footprint or symbol association
- **Flat CSV only**: No database structure, no relational data, no search optimization
- **Limited pricing**: Only captures price at MOQ tier, not full price breaks
- **No category hierarchy**: `type` field is a flat string, not structured
- **Fragile API dependency**: Uses JLCPCB's internal API which could change without notice
- **Small subset**: Only economic parts (~10K-20K estimated), not the full JLCPCB catalog of 100K+ parts
- **No datasheet content**: Has datasheet file ID but doesn't download or parse datasheets

## Relevance to KiCad Database Library

This data could serve as a **parts availability and pricing layer** for a KiCad database library. The CSV provides LCSC part numbers, stock levels, and pricing that could be joined with a more complete parametric database (like CDFER's SQLite DB or yaqwsx's jlcparts). On its own, it lacks the electrical parameters and footprint mappings needed for a complete KiCad database library.

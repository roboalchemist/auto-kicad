# CDFER/jlcpcb-parts-database Analysis

**Repository**: [CDFER/jlcpcb-parts-database](https://github.com/CDFER/jlcpcb-parts-database)
**License**: MIT
**Language**: Python (scripts + Jupyter notebooks)
**Dependencies**: pandas, requests, brotli, numpy, matplotlib

## Overview

A downstream processor of the [yaqwsx/jlcparts](https://github.com/yaqwsx/jlcparts) database. Does NOT scrape JLCPCB directly for the main parts database — instead downloads the pre-built ~10GB multi-volume ZIP from yaqwsx/jlcparts, then filters, optimizes, and republishes it in two smaller formats hosted on GitHub Pages.

Additionally, it runs a separate scraper (`scrape-jlcpcb.py`) that hits the JLCPCB API directly to track basic/preferred part availability and assembly details.

## How the Database is Built

### Pipeline (GitHub Actions: `.github/workflows/sync-db.yml`)

Three sequential jobs run daily at 05:45 UTC:

#### Job 1: `scrape-jlc` — Scrape JLCPCB Basic/Preferred List
1. Runs `scrape-jlcpcb.py` which:
   - Hits the JLCPCB API endpoint (`/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList/v2`) to enumerate basic/preferred parts (paginated, 100 per page, up to 64 pages)
   - Updates `scraped/ComponentList.csv` with LCSC codes, tracking "First Seen" and "Last Seen" dates
   - For new components not yet in `scraped/assembly-details.csv`, fetches individual part details from JLCPCB's cart API
   - Randomly re-checks 400 existing components to keep assembly details fresh
   - Commits updated CSV files back to the repo
2. Rate limiting: 3-second delay between paginated requests

#### Job 2: `update-database` — Process yaqwsx/jlcparts Data
1. Frees disk space on GitHub Actions runner (removes .NET, GHC, Boost)
2. Downloads multi-volume ZIP from `yaqwsx.github.io/jlcparts/data/cache.zip` (plus `.z01`-`.z99` volumes)
3. Extracts with 7zip (standard zip libraries can't handle the multi-volume format)
4. Runs `generate-database.py` which:
   - Renames `cache.sqlite3` to `jlcpcb-components.sqlite3`
   - Deletes components with stock < 5
   - Creates FTS5 full-text search index on: `lcsc`, `mfr`, `package`, `description`, `datasheet`
   - REINDEXes and VACUUMs the database
   - Corrects preferred part flags using scraped ComponentList.csv data
   - Exports basic/preferred parts (excluding 0201 package) to CSV, merging assembly details
5. Uploads to GitHub Pages artifact

#### Job 3: `deploy` — Publish to GitHub Pages
- Deploys the SQLite database (~1GB) and CSV file (~3MB) to GitHub Pages
- Cleans up the artifact after deployment

### Update Frequency
- **Daily** at 05:45 UTC (2h45m after yaqwsx/jlcparts updates at 03:00 UTC)
- Also triggers on push to main and manual workflow dispatch

## Data Outputs

### 1. SQLite Database (~1GB after filtering)
**URL**: `https://cdfer.github.io/jlcpcb-parts-database/jlcpcb-components.sqlite3`

#### Tables
- **`components`** — Main table with all JLCPCB components (stock >= 5 after filtering)
  - Key columns (inferred from queries in notebooks): `lcsc` (int), `mfr` (text), `package` (text), `description` (text), `datasheet` (text), `stock` (int), `price` (JSON string), `joints` (int), `basic` (int/bool), `preferred` (int/bool), `category` (text), `subcategory` (text)
  - Price is stored as JSON array of tier objects: `[{"qFrom": 1, "qTo": 10, "price": 0.05}, ...]`
- **`components_fts`** — FTS5 virtual table for full-text search across `lcsc`, `mfr`, `package`, `description`, `datasheet`
- **`v_components`** — View (defined in upstream yaqwsx/jlcparts) that provides a convenient query interface

#### Data Scope
- ~304,635 components (after filtering out stock < 5)
- Original upstream database: ~10GB, all JLCPCB parts regardless of stock

#### Performance Settings Applied
```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA temp_store = MEMORY;
PRAGMA mmap_size = 536870912;  -- 512MB
```

### 2. Basic/Preferred Parts CSV (~3MB)
**URL**: `https://cdfer.github.io/jlcpcb-parts-database/jlcpcb-components-basic-preferred.csv`

Contains only basic and preferred parts (free feeder loading), excluding 0201 packages. Merged with assembly details from the scraper.

Columns: `lcsc`, `mfr`, `package`, `description`, `datasheet`, `stock`, `price`, `joints`, `basic`, `preferred`, `category`, `subcategory`, `Assembly Process`, `Min Order Qty`, `Attrition Qty` (and potentially more from the v_components view)

### 3. Scraped Data (committed to repo)

#### `scraped/ComponentList.csv` (~3,492 parts)
Fields: `lcsc`, `First Seen`, `Last Seen`
- Tracks which LCSC codes appear in JLCPCB's basic/preferred parts listing over time
- Dates in `YYYY/MM/DD` format

#### `scraped/assembly-details.csv` (~3,559 parts)
Fields: `lcsc`, `Assembly Type`, `Assembly Type Batch`, `Assembly Process`, `Min Order Qty`, `Attrition Qty`, `Special Component Fee`, `Component Library Type`
- Assembly-specific metadata from JLCPCB's cart API
- `Assembly Process`: SMT or through-hole
- `Component Library Type`: base, expand, etc.

## How to Query Programmatically

### Download and search SQLite (Python)
```python
import sqlite3, requests, json

# Download (~1GB)
r = requests.get("https://cdfer.github.io/jlcpcb-parts-database/jlcpcb-components.sqlite3", stream=True)
with open("jlcpcb-components.sqlite3", "wb") as f:
    for chunk in r.iter_content(None):
        f.write(chunk)

# Query
conn = sqlite3.connect("jlcpcb-components.sqlite3")
cur = conn.cursor()
cur.execute("PRAGMA mmap_size = 2147483648")

# Full-text search
cur.execute("""
    SELECT c.price, c.stock, f.*
    FROM components c
    JOIN components_fts f ON c.lcsc = f.lcsc
    WHERE f.description LIKE '%USB%'
""")
for row in cur.fetchall():
    price = json.loads(row[0])[0]["price"]
    print(f"C{row[2]} - ${price:.3f} - Stock: {row[1]} - {row[5]}")

conn.close()
```

### Use CSV with pandas
```python
import pandas as pd
df = pd.read_csv("https://cdfer.github.io/jlcpcb-parts-database/jlcpcb-components-basic-preferred.csv")
# Filter by category, sort by price, etc.
```

## Strengths

1. **Solves a real problem**: The upstream 10GB multi-volume ZIP is unusable by most tools. This provides a ~1GB filtered SQLite and ~3MB CSV.
2. **FTS5 index**: Full-text search across multiple fields makes querying fast.
3. **Daily updates**: Automated pipeline keeps data current, running 2h45m after upstream updates.
4. **GitHub Pages hosting**: Free, reliable CDN distribution of the database files.
5. **Assembly details enrichment**: Merges JLCPCB assembly metadata (process type, MOQ, attrition) not present in the upstream database.
6. **Basic/preferred tracking**: Historical tracking of when parts enter/leave the basic/preferred lists.
7. **Jupyter notebooks**: Working examples for searching, analyzing, and visualizing the data.
8. **Lightweight CSV option**: The ~3MB CSV of basic/preferred parts is trivially downloadable for simple use cases.

## Weaknesses

1. **Schema is inherited and undocumented**: The `components` table schema comes from yaqwsx/jlcparts and isn't documented in this repo. Column names and types must be inferred from query patterns in notebooks.
2. **1GB download**: The SQLite database is still large. No incremental update mechanism — must re-download the entire file.
3. **Fragile scraper**: The `scrape-jlcpcb.py` script hardcodes JLCPCB API endpoints and uses browser-like headers to avoid detection. Any API change breaks it.
4. **No API/query endpoint**: Must download the full database locally. No hosted query service.
5. **Stock >= 5 filter is aggressive**: Parts with 1-4 in stock are silently dropped, which may exclude niche but available components.
6. **No KiCad integration**: Pure data files with no symbol/footprint mapping. Would need external mapping to be useful in KiCad.
7. **Price is JSON blob**: Price tiers stored as JSON strings require parsing, complicating SQL queries.
8. **Limited error handling**: The scraper has minimal retry logic and could fail silently on rate limiting.
9. **No parametric search**: While FTS5 enables text search, there's no structured parametric data (resistance values, capacitance, voltage ratings as separate columns).
10. **CSV lacks full schema**: The basic/preferred CSV drops many parts and columns vs. the full SQLite database.

## Relevance to KiCad-Claude

- **Good source for part selection**: The filtered SQLite database with FTS5 is well-suited for programmatic part lookups by description/manufacturer.
- **Assembly cost modeling**: The assembly details CSV enables BOM cost estimation including SMT/through-hole process costs.
- **Would need symbol/footprint mapping**: This database has no KiCad library references. A mapping layer from LCSC part numbers to KiCad symbols/footprints would be needed.
- **Basic/preferred part optimization**: The CSV makes it easy to identify which parts have zero feeder loading fees, enabling BOM cost optimization.

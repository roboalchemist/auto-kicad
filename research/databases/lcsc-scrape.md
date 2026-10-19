# lcsc-scrape.rs Analysis

**Repository**: [cs2dsb/lcsc-scrape.rs](https://github.com/cs2dsb/lcsc-scrape.rs)
**Language**: Rust (edition 2021)
**Version**: 0.1.1
**License**: MIT + Apache 2.0

## Overview

A Rust CLI tool that scrapes LCSC product pages and JLCPCB SMT assembly service data, stores raw HTTP responses in a file-based cache, parses them into a SQLite database, and provides a SQL query interface. Designed specifically for parts available through the JLCPCB SMT assembly service.

## Architecture

The entire codebase is a single `src/main.rs` file (~1450 lines). There are no modules, traits (beyond simple helpers), or separate crates. Everything -- CLI parsing, HTTP fetching, HTML parsing, JSON deserialization, SQLite operations, post-processing -- lives in one file.

### Key Dependencies

| Crate | Purpose |
|-------|---------|
| `reqwest` (blocking) | HTTP client for LCSC/JLCPCB APIs |
| `scraper` | HTML parsing with CSS selectors |
| `rusqlite` | SQLite database access |
| `calamine` | Spreadsheet reading (ODS/XLSX) for JLC parts list |
| `clap` | CLI argument parsing |
| `serde` / `serde_json` | JSON serialization/deserialization |
| `regex` | Parsing voltages, currents, prices, resistance, etc. |
| `linked_hash_set` | Insertion-order-preserving set for column ordering |

### CLI Structure (clap subcommands)

```
lcsc-scrape
  fetch           # Download data from LCSC + JLCPCB, populate DB
    --parts / --parts-list / --parts-spreadsheet  (one required)
    --jlc-data                    # Also fetch JLCPCB stock/price/basic-extended
    --refresh-cache-jlc           # Ignore JLC cache
    --refresh-cache-lcsc          # Ignore LCSC cache
    --download-to-cache-only      # Cache only, don't update DB
    --purge-cached-errors         # Delete cached files that fail to parse
  manage
    post-process   # Parse string columns into typed pp_ columns
    clear-database # DROP tables + VACUUM
    clear-cache    # Delete cache directory
  query            # Execute arbitrary SQL, output CSV
    --drop-null-columns
    --drop-price-columns
    --omit-headers
```

## Scraping Strategy

### Data Sources

1. **LCSC Product Pages** (HTML scraping)
   - First resolves part number to URL via: `GET https://lcsc.com/api/global/additional/search?q={part_number}`
   - Then fetches the full product page HTML
   - Parses three HTML tables using CSS selectors:
     - `table.products-specifications` -- component specifications (key-value pairs)
     - `table.info-table` -- general info (manufacturer, package, description, datasheet link, RoHS)
     - `table.main-table` -- LCSC pricing tiers

2. **JLCPCB SMT Assembly API** (JSON API)
   - `POST https://jlcpcb.com/shoppingCart/smtGood/selectSmtComponentList`
   - Paginated JSON responses with stock, prices, basic/extended status, descriptions
   - Handles pagination with empty-response detection (stops after 5 consecutive empty pages)

### Part Number Input Methods

- Direct CLI args (`--parts C1234 C5678`)
- Text file (`--parts-list`, whitespace-delimited)
- JLC spreadsheet (`--parts-spreadsheet`, reads ODS/XLSX, finds "LCSC Part" and "Library Type" columns)
- The `_b` suffix on part numbers marks them as basic parts

## HTTP Caching

File-based cache in a `./cache/` directory (configurable via `--cache-path`):

- **LCSC pages**: cached as `cache/{part_number}` (raw HTML)
- **JLC data**: cached as `cache/{part_number}_jlc_data` (raw JSON)
- Cache hit: file exists and has non-zero size
- No TTL/expiration -- cache is permanent unless manually refreshed
- Selective refresh via `--refresh-cache-jlc` and `--refresh-cache-lcsc` flags
- `--purge-cached-errors` deletes cached files that fail to parse

The cache directory is ~3.5GB for the full JLC parts list (~37k parts). The README strongly advises against running without cache.

## Rate Limiting

Two rate limit constants:

| Target | Rate | Strategy |
|--------|------|----------|
| LCSC | 1 request/second | Sleep after each request if elapsed time < 1s |
| JLCPCB | 1 request/300ms | Sleep after each request if elapsed time < 300ms |

Additional protections:
- **HTTP 429 handling**: On `TOO_MANY_REQUESTS`, sleeps for `rate * 10` (10s for LCSC, 3s for JLC) then retries
- **`x-ratelimit-remaining` header**: If remaining < 10, sleeps for `rate * 10` preemptively
- No concurrent requests -- everything is single-threaded blocking

## SQLite Schema

### Dynamic Schema (EAV-like)

The schema is **not fixed** -- columns are added dynamically as new key-value pairs are discovered from HTML scraping. This is the most distinctive architectural choice.

**Table: `parts`**
- `part_number TEXT PRIMARY KEY` -- the only guaranteed column
- All other columns are added via `ALTER TABLE parts ADD COLUMN "{name}" text` as new attribute keys are encountered
- Column names come directly from HTML table cell text (e.g., "Manufacturer", "Package", "Voltage - Input (Min)")

**Table: `keys`**
- `key TEXT PRIMARY KEY` -- tracks which columns have been added to `parts`
- Acts as a registry to avoid duplicate `ALTER TABLE` calls

### Post-Processed Columns (pp_ prefix)

The `post-process` command creates typed columns from string data:

| Original Column | PP Column | Type | Parsing |
|-----------------|-----------|------|---------|
| `Basic` | `pp_Basic` | INTEGER (bool) | "true"->1, "false"->0 |
| `Resistance (Ohms)` | `pp_Resistance (Ohms)` | REAL | Regex with SI prefixes |
| `Inductance` | `pp_Inductance` | REAL | Regex with SI prefixes |
| `Capacitance` | `pp_Capacitance` | REAL | Regex with SI prefixes |
| `Price *` | `pp_Price *` | REAL | Regex for USD prices |
| `*Voltage*` | `pp_*Voltage*` | REAL | Regex with SI prefixes (V, kV, mV) |
| `*Current*` | `pp_*Current*` | REAL | Regex with SI prefixes (A, mA, uA, kA) |

SI prefix handling: K/k=1e3, M=1e6, m=1e-3, u=1e-6, n=1e-9, p=1e-12.

### Data Fields Captured

From **LCSC HTML** (varies by component category):
- Manufacturer, Package, Description, Datasheet (URL), RoHS status
- Category-specific specs (resistance, capacitance, voltage ratings, etc.)
- LCSC pricing tiers (as "Price {tier}" columns)

From **JLCPCB JSON API**:
- `Basic` -- basic/extended library type
- `JLC_Stock` -- current stock count
- `JLC_Description` -- JLCPCB description
- `JLC_Datasheet` -- JLCPCB datasheet URL
- `LCSC_URL` -- canonical LCSC product URL
- `Price JLC {n}+` -- JLCPCB pricing at quantity breaks

## Build & Run Instructions

```bash
# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Install SQLite dev lib (Ubuntu/Debian)
sudo apt-get install libsqlite3-dev  # or run ./bootstrap.sh

# Build
cargo build --release
# Binary: ./target/release/lcsc-scrape (also symlinked as ./lcsc-scrape)

# Full pipeline (build + fetch + post-process)
./run.sh

# Manual steps
./lcsc-scrape fetch --jlc-data --parts-spreadsheet JLC_Components.ods
./lcsc-scrape manage post-process
./lcsc-scrape query "SELECT * FROM parts WHERE Category = 'Resistors'"
```

## Strengths

1. **Aggressive caching** -- file-based cache means the full ~37k parts dataset can be rebuilt from cache in minutes without any network requests
2. **Post-processing pipeline** -- converts string values to proper numeric types with SI prefix handling, enabling meaningful range queries (e.g., "capacitors < 100pF")
3. **Dual data source** -- combines LCSC product specs with JLCPCB assembly service info (stock, pricing, basic/extended status) in one database
4. **Flexible query interface** -- raw SQL access with useful output options (drop null columns, drop price columns, CSV output)
5. **Selective cache refresh** -- can refresh just JLC data (fast) without re-scraping LCSC pages (slow, risky)
6. **Rate limiting with backoff** -- handles 429 responses and monitors rate limit headers
7. **Spreadsheet input** -- reads the official JLC parts spreadsheet directly

## Weaknesses

1. **Single-file monolith** -- 1450 lines in one file with no module structure; hard to maintain or extend
2. **Fragile HTML scraping** -- relies on specific CSS selectors (`table.info-table`, `table.products-specifications`, `table.main-table`); any LCSC redesign breaks everything
3. **SQL injection vulnerability** -- `save_pairs()` builds SQL via string formatting with only quote-stripping (no parameterized queries for dynamic columns/values)
4. **No parallelism** -- single-threaded blocking HTTP; full scrape of 37k parts takes hours
5. **Dynamic schema is hard to work with** -- column names contain spaces and special characters (e.g., `"Voltage - Input (Min)"`), requiring quoting everywhere
6. **Outdated dependencies** -- `clap` v2 (current is v4), `rusqlite` 0.23 (current is 0.31+), `scraper` 0.13 (current is 0.18+)
7. **No incremental updates** -- can't easily add new parts without re-processing existing ones; the `_b` suffix mechanism for basic parts is fragile
8. **Cache has no TTL** -- stale data stays forever unless manually refreshed
9. **LCSC API dependency** -- the search API (`/api/global/additional/search`) is undocumented and could change without notice
10. **Linux-only releases** -- only builds for linux-amd64 in CI
11. **Unsafe code** -- `TrimInPlace` trait uses `unsafe` pointer copy for an optimization that could be done safely

## Relevance to KiCad Database

- Demonstrates a working approach to scraping LCSC/JLCPCB data into SQLite
- The dynamic column approach is interesting but would need significant cleanup for a structured KiCad database
- Post-processing pipeline for SI-prefixed values is reusable logic
- The file-based cache pattern is worth considering for any scraping approach
- Rate limiting constants (1s for LCSC, 300ms for JLCPCB) are useful reference points

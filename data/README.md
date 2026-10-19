# Parts database

`jlcpcb-components.sqlite3` is a ~1.2 GB SQLite database of JLCPCB/LCSC parts used by
`demo/blinker.py` and the harness's part search. It is stored with Git LFS:

```bash
git lfs install
git lfs pull
```

Schema highlights:

| Column | Meaning |
|---|---|
| `lcsc` | LCSC part number as an integer, without the `C` prefix (C7593 → `7593`) |
| `basic` | `1` for a JLC Basic part (no extended-part fee) |
| `stock`, `price` | Availability and price at the time the snapshot was taken |

The database is in WAL mode. Open it read-only with `immutable=1` so no `-wal`/`-shm`
files are created:

```python
sqlite3.connect("file:data/jlcpcb-components.sqlite3?immutable=1", uri=True)
```

`components_fts` is empty; use `LIKE` queries. The data is a snapshot and may be stale —
refresh it from [CDFER/jlcpcb-parts-database](https://github.com/CDFER/jlcpcb-parts-database)
if you need current stock or pricing.

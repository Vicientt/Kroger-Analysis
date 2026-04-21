# Prefect setup for Kroger Analysis

Uses **Prefect 3** to orchestrate the daily ELT pipeline:

1. `task_extract_load` — Kroger API -> Parquet staging -> DuckDB raw
2. `task_dbt_run` — `dbt run` against the local DuckDB profile

---

## Quick start

```bash
make run      # one-off: extract + load
make dbt      # one-off: dbt transform
make serve    # schedule: run daily at 18:00 (keeps terminal open)
make ui       # open Prefect UI at http://127.0.0.1:4200
```

Change timezone (default `America/Chicago`):

```bash
make serve TZ=Asia/Ho_Chi_Minh
```

---

## Troubleshooting

- **`import main` fails:** always run from the repo root via `make`.
- **`dbt` cannot find profile:** check `kroger_analysis/profiles.yml`.
- **Kroger rate limit:** one run per day maximum (10,000 calls/day).

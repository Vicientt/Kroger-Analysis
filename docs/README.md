# Kroger Analysis - Extract, Load & Transform (ELT) Pipeline

ELT pipeline using the **Kroger Products API** and **DuckDB**. Collects product-level data across 33 categories and 32 states, writes to CSV staging, loads into DuckDB, then transforms with dbt.

---

## Pipeline Overview

- **API interaction:** Kroger Locations API + Products API
- **Pagination:** 200 products per category (4 pages of 50)
- **Store validation:** Skip states with no product-available stores
- **Staging:** CSV per day in `data/staging/YYYY-MM-DD/products.csv`
- **Load:** Raw tables `raw.kroger_products_YYYY_MM_DD` (one per day)
- **Transform:** dbt staging views and mart tables

---

## Architecture

```
Kroger API
    |
    v
Locations API -> validated store per state (32 states)
    |
    v
Products API (33 categories, 200 products each)
    |
    v
data/staging/YYYY-MM-DD/products.csv
    |
    v
DuckDB raw.kroger_products_YYYY_MM_DD
    |
    v
raw.kroger_products_all (view union of all daily tables)
    |
    v
dbt: staging.stg_kroger_products -> mart.*
```

---

## Project Structure

```
Kroger-Analysis/
├── main.py              # Extract + Load (API -> CSV -> DuckDB)
├── dbt                  # dbt wrapper script (./dbt run)
├── pyproject.toml       # Python deps (uv)
├── uv.lock
├── kroger_analysis/     # dbt project
│   ├── profiles.yml    # Local profile (no ~/.dbt needed)
│   └── models/
│       ├── staging/    # stg_kroger_products
│       └── marts/      # mart_category_summary, mart_state_summary, mart_product_analysis
└── data/               # Generated at runtime
    ├── kroger.duckdb
    └── staging/
        └── YYYY-MM-DD/
            └── products.csv
```

---

## Run Commands

```bash
# 1. Extract + Load (API -> CSV staging -> DuckDB)
uv run main.py

# 2. Transform
./dbt run
```

---

## Setup

### 1. Kroger API Credentials

1. Go to [Kroger Developer Portal](https://developer.kroger.com/)
2. Create account and application
3. Get Client ID and Client Secret
4. Redirect URI: `http://localhost`

### 2. Clone and Install

```bash
git clone https://github.com/<your-username>/Kroger-Analysis.git
cd Kroger-Analysis
uv sync
```

### 3. Environment Variables

Create `.env` in project root:

```env
KROGER_CLIENT_ID=your_client_id
KROGER_CLIENT_SECRET=your_client_secret
```

### 4. Run

```bash
uv run main.py
./dbt run
```

---

## Database (DuckDB)

- **File:** `data/kroger.duckdb`
- **Schemas:** `raw`, `staging`, `mart`

### Raw Layer

- `raw.kroger_products_YYYY_MM_DD` - Flat table per day (from CSV)
- `raw.kroger_products_all` - View union of all daily tables

### dbt Transform

- `staging.stg_kroger_products` - View from raw.kroger_products_all
- `mart.mart_category_summary` - Aggregates by category
- `mart.mart_state_summary` - Aggregates by state
- `mart.mart_product_analysis` - Product-level with has_promo

### profiles.yml

The project uses `kroger_analysis/profiles.yml`. Run `./dbt run` from project root (not `dbt run` directly) so the script sets `DBT_PROFILES_DIR=.`.

---

## API Details

### Token

- OAuth2 client credentials flow
- Token expires in ~30 minutes (1800s)
- Pipeline auto-refreshes when 401 is received

### Rate Limit

- 10,000 calls/day
- Script prints usage at end

### States (32)

Optimized ZIP codes: Alabama, Arizona, Arkansas, California, Colorado, Florida, Georgia, Idaho, Illinois, Indiana, Kansas, Kentucky, Louisiana, Michigan, Mississippi, Missouri, Nebraska, Nevada, New Mexico, North Carolina, Ohio, Oklahoma, Oregon, South Carolina, Tennessee, Texas, Utah, Virginia, Washington, West Virginia, Wisconsin, Wyoming.

### Categories (33)

- Fresh: meat, seafood, produce, deli, bakery, eggs
- Food & beverage: pantry, beverage, breakfast, organic, alcohol, frozen
- Health & beauty: health, vitamins, personal care, beauty, baby
- Home: batteries, kitchen appliances, electronics, patio grilling, cleaning
- Other: pet food, toys, flowers
- Popular: snacks, chips, cookies, nuts, pasta sauce, canned goods, honey, peanut butter

---

## Data Flow

1. **Extract:** API returns products per store per category
2. **Flatten:** `flatten_product_rows()` converts to flat rows
3. **Staging:** `save_to_staging_parquet()` writes `data/staging/YYYY-MM-DD/products.parquet`
4. **Load:** `load_parquet_to_duckdb()` creates `raw.kroger_products_YYYY_MM_DD`, rebuilds `raw.kroger_products_all`
5. **Transform:** dbt staging and marts read from raw.kroger_products_all

# Kroger Analysis – Extract, Load & Transform (ELT) Pipeline

This document describes the full **ELT pipeline** using the **Kroger Products API** and **DuckDB**.  
The goal is to collect product-level data across multiple categories and states, load raw data into DuckDB, then transform it with dbt.

This pipeline focuses on:
- API interaction (Locations + Products)
- Pagination handling
- Store validation (skip states with no product-available stores)
- Loading raw JSON into DuckDB
- Transforming with dbt (staging + marts)

---

## Project Overview

### Data Source
- **Kroger Products API**
- **Kroger Locations API**

### What the pipeline does
1. Authenticate with the Kroger API using OAuth2
2. Find a store per state (validates product availability; skips state if none found)
3. Query 33 product categories per store
4. Handle API pagination to fetch **200 products per category**
5. Load raw data into DuckDB (`data/kroger.duckdb`)
6. Transform with dbt (staging views, mart tables)

---

## Pipeline Architecture

```
Kroger API
│
├── Locations API → Store per state (validated)
│
├── Products API (with pagination)
│       ├── 33 categories per store
│       ├── 50 products per request (API max)
│       └── 200 products per category (4 pages)
│
└── DuckDB (data/kroger.duckdb)
    ├── raw.kroger_products_raw (one row per state, full JSON)
    │
    └── dbt Transform
            ├── staging.stg_kroger_products (view)
            └── mart.mart_category_summary, mart_state_summary, mart_product_analysis (tables)
```

---

## Database (DuckDB)

- **DuckDB file:** `data/kroger.duckdb`
- **Schemas:** `raw` (raw data), `staging` (views), `mart` (tables)

### profiles.yml

The project includes `kroger_analysis/profiles.yml` so you don't need to configure `~/.dbt/profiles.yml`. Use the `./dbt` script from project root (e.g. `./dbt run`) to run dbt with the local profile.

---

## Project Structure

```
kroger-analysis/
│
├── main.py               # Extract + Load pipeline
├── pyproject.toml        # Project configuration (uv)
├── uv.lock               # Dependency lock file
├── kroger_analysis/      # dbt project (Transform)
│   ├── profiles.yml     # Local dbt profile (no ~/.dbt needed)
│   └── models/
└── data/
    └── kroger.duckdb     # DuckDB database (raw + staging + mart)
```

> The `data/` directory is generated at runtime.

---

## Run Commands

```bash
# 1. Extract + Load (main.py creates raw table automatically)
uv run main.py

# 2. Transform
./dbt run
```

---

## Setup Instructions

### 1. Get Kroger API Credentials

Before you can run this pipeline, you need to register for Kroger API access:

#### Step-by-step guide:

1. **Go to the Kroger Developer Portal**
   - Visit: https://developer.kroger.com/

2. **Create an account**
   - Click "Sign Up" or "Get Started"
   - Fill in your information and verify your email

3. **Create a new application**
   - Log in to the developer portal
   - Navigate to "My Applications" or "Dashboard"
   - Click "Create Application" or "New App"

4. **Fill in application details**
   - **Application Name**: `Kroger Analysis Pipeline` (or any name)
   - **Description**: Brief description of your project
   - **Redirect URI**: `http://localhost` (for development)
   - Accept the terms and conditions

5. **Get your credentials**
   - After creating the app, you'll see:
     - **Client ID**: A long alphanumeric string
     - **Client Secret**: Another long alphanumeric string (keep this secure!)
   - Copy both values - you'll need them in the next step

> **Important**: Keep your Client Secret private! Never commit it to GitHub or share it publicly.

---

### 2. Clone (or fork) the repository

```bash
git clone https://github.com/<your-username>/Kroger-Analysis.git
cd Kroger-Analysis
uv sync
```

**Required:** Run `uv sync` after cloning to install dependencies (duckdb, requests, dbt-core, dbt-duckdb, etc.).

---

### 3. Set up environment variables

Create a `.env` file in the project root:

```env
KROGER_CLIENT_ID=your_client_id_here
KROGER_CLIENT_SECRET=your_client_secret_here
```

Replace `your_client_id_here` and `your_client_secret_here` with the credentials you obtained from the Kroger Developer Portal.

**Example:**
```env
KROGER_CLIENT_ID=abc123xyz-0000-1111-2222-333344445555
KROGER_CLIENT_SECRET=XyZ9876aBcDeF1234567890qWeRtY
```

> The `.env` file should be listed in `.gitignore` to prevent accidentally committing your credentials.

---

### 4. (Optional) Reinstall dependencies

If you add or change dependencies later:

```bash
uv sync
```

---

## How the Code Works

### Code Structure

The Extract & Load pipeline consists of one main file: `main.py`

#### **Class: KrogerAPI**

**`__init__()`**  
Initializes the API client with credentials from environment variables and sets up tracking for API calls.

**`auth()`**  
Authenticates with Kroger API using OAuth2 client credentials flow. Returns access token for subsequent requests.

**`get_largest_store_per_state(state_zip_codes)`**  
For each state's ZIP code, fetches nearby Kroger locations. Tries each store until one returns products; skips the state if none do.

**`search_products(term, location_id, limit=200)`**  
Searches for products at a store with pagination. API returns max 50 per request; multiple calls are made to reach the limit (default: 200).

**`load_to_duckdb(all_products_data)`**  
Loads raw product data into DuckDB `raw.kroger_products_raw`. Creates schema and table if they do not exist.

---

#### **Main Pipeline: `main()`**

Orchestrates the Extract & Load process:

1. **Authentication** - Connects to Kroger API
2. **Store Discovery** - Finds validated store in each enabled state
3. **Product Search** - Queries 33 categories per store with pagination (200 products each)
4. **Load to DuckDB** - Inserts raw data into `data/kroger.duckdb`
5. **Summary Report** - Prints execution statistics and API usage

---

### Key Implementation Details

#### 1. Authentication

The `KrogerAPI` class handles OAuth authentication and stores the access token for subsequent requests.

```python
api = KrogerAPI()
api.auth()
```

---

#### 2. Store Selection Strategy

For each selected U.S. state, the pipeline:
- Uses a representative ZIP code
- Fetches up to 50 nearby Kroger locations (API order: by distance)
- Validates each store with a quick product search (`term="milk"`, limit=1)
- Uses the first store that returns products
- Skips the state if no store returns products (tries up to 20 stores)

---

#### 3. Pagination Logic

The Kroger Products API returns a maximum of **50 products per request**.

To fetch more:
- Pagination is implemented using `filter.start` parameter
- Multiple API calls are combined to reach **200 products per category**

Example:
```text
200 products = 4 API calls (50 × 4)
```

**Code snippet:**
```python
# Calculate pages needed
pages_needed = (limit + 49) // 50

# Loop through pages
for page in range(pages_needed):
    params = {
        "filter.limit": 50,
        "filter.start": page * 50,  # Skip previous results
        ...
    }
```

---

#### 4. Categories Covered (33 total)

The pipeline queries multiple product domains, including:
- **Fresh foods** (6): meat, seafood, produce, deli, bakery, eggs
- **Food & beverage** (6): pantry, beverage, breakfast, organic, alcohol, frozen
- **Health & personal care** (5): health, vitamins, personal care, beauty, baby
- **Home essentials** (5): batteries, kitchen appliances, electronics, patio grilling, cleaning
- **Pet, toys & floral** (3): pet food, toys, flowers
- **Additional popular items** (8): snacks, chips, cookies, nuts, pasta sauce, canned goods, honey, peanut butter

This ensures broad coverage of Kroger's catalog.

---

### 5. Data Output

Raw data is loaded into DuckDB at `data/kroger.duckdb`:

- **raw.kroger_products_raw** - One row per state; `raw_data` column contains full JSON (state, store_id, store_name, search_results with all products)

After running `dbt run`:
- **staging.stg_kroger_products** - Flattened product rows
- **mart.mart_category_summary** - Aggregates by category
- **mart.mart_state_summary** - Aggregates by state
- **mart.mart_product_analysis** - Product-level analysis

---

## Running the Pipeline

```bash
# Step 1: Extract + Load
uv run main.py

# Step 2: Transform
./dbt run
```

The script will:
- Authenticate with Kroger API
- Fetch stores and products
- Load raw data to DuckDB
- Print a summary including API usage

---

## API Usage & Limits

- Kroger API rate limit: **10,000 calls/day**
- The script tracks total API calls during execution
- Only a subset of states is enabled by default to minimize usage

You can enable more states by uncommenting them in `main.py`.

# Kroger Analysis – Extract & Load Pipeline

This first process implements a simple **Extract & Load (EL) data pipeline** using the **Kroger Products API**.  
The goal is to collect product-level data across multiple categories and states, then store the raw and summarized data locally for further analysis.

This repository focuses on:
- API interaction
- Pagination handling
- Data extraction at scale
- Saving raw and aggregated datasets

---

## Project Overview

### Data Source
- **Kroger Products API**
- **Kroger Locations API**

### What the pipeline does
1. Authenticate with the Kroger API using OAuth2
2. Identify the largest Kroger store per selected U.S. state
3. Query multiple product categories per store
4. Handle API pagination to fetch **200+ products per category**
5. Save raw and aggregated data into local files

---

## Pipeline Architecture

```
Kroger API
│
├── Locations API → Largest store per state
│
├── Products API (with pagination)
│       ├── Category search
│       ├── Multiple pages (limit = 50 per request)
│       └── Accumulate results
│
└── Local Storage (data/)
    ├── all_products.csv
    ├── state_summary.csv
    ├── category_summary.csv
    └── products_raw.json
```

---

## Project Structure

```
kroger-analysis/
│
├── main.py               # Main pipeline script
├── pyproject.toml        # Project configuration (uv)
├── uv.lock               # Dependency lock file
├── token.json            # API token (ignored in .gitignore)
├── README.md             # Project documentation
└── data/
    ├── all_products.csv
    ├── state_summary.csv
    ├── category_summary.csv
    └── products_raw.json
```

> ⚠️ The `data/` directory is generated at runtime and is **not pushed to GitHub**.

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

> ⚠️ **Important**: Keep your Client Secret private! Never commit it to GitHub or share it publicly.

---

### 2. Clone the repository

```bash
git clone https://github.com/<your-username>/Kroger-Analysis.git
cd Kroger-Analysis
```

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

> 💡 The `.env` file should be listed in `.gitignore` to prevent accidentally committing your credentials.

---

### 4. Install dependencies (using uv)

```bash
uv sync
```

---

## How the Code Works

### Code Structure

The pipeline consists of one main file: `main.py`

#### **Class: KrogerAPI**

**`__init__()`**  
Initializes the API client with credentials from environment variables and sets up tracking for API calls.

**`auth()`**  
Authenticates with Kroger API using OAuth2 client credentials flow. Returns access token for subsequent requests.

**`get_largest_store_per_state(state_zip_codes)`**  
For each state's ZIP code, queries the Locations API to find nearby Kroger stores. Returns the largest store (first result) per state.

**`search_products(term, location_id, limit=200)`**  
Searches for products at a specific store location with pagination support. Since the API returns max 50 products per request, this function automatically makes multiple calls to reach the desired limit (default: 200 products).

---

#### **Data Export Functions**

**`save_all_products_csv(all_products_data, filename)`**  
Exports detailed product-level data to CSV with columns: State, Store Name, Product Category, Brand, Price, Size, etc.

**`save_state_summary_csv(all_products_data, filename)`**  
Creates aggregated summary per state showing total products, unique brands, and categories found.

**`save_category_summary_csv(all_products_data, filename)`**  
Aggregates data by category across all states, showing total products and brand diversity per category.

**`save_raw_json(all_products_data, filename)`**  
Saves complete raw API response data in JSON format for reproducibility and future analysis.

---

#### **Main Pipeline: `main()`**

Orchestrates the entire data collection process:

1. **Authentication** - Connects to Kroger API
2. **Store Discovery** - Finds largest store in each enabled state
3. **Product Search** - Queries 33 categories per store with pagination (200 products each)
4. **Data Export** - Saves results in 4 different formats
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
- Queries nearby Kroger locations
- Selects the largest store (first result)

This reduces noise and standardizes product comparisons across states.

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

All extracted data is saved locally under the `data/` directory.

#### Generated files:

**all_products.csv**  
Detailed product-level dataset (state, store, category, brand, price, size)

**state_summary.csv**  
Aggregated metrics per state (total products, unique brands, categories found)

**category_summary.csv**  
Aggregated metrics per category across states

**products_raw.json**  
Full raw API response for reproducibility and downstream processing

---

## Running the Pipeline

Simply run:

```bash
uv run main.py
```

The script will:
- Authenticate with Kroger API
- Fetch stores and products
- Save all datasets locally
- Print a summary including API usage

---

## API Usage & Limits

- Kroger API rate limit: **10,000 calls/day**
- The script tracks total API calls during execution
- Only a subset of states is enabled by default to minimize usage

You can enable more states by uncommenting them in `main.py`.
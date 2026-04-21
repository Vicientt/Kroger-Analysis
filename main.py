"""
Kroger API - Extract & Load to DuckDB
Get 200+ products per category using pagination, load raw data to DuckDB.
"""

import os
from datetime import date
from pathlib import Path

import duckdb
import requests
from dotenv import load_dotenv

load_dotenv()

DB_PATH = Path(__file__).resolve().parent / "data" / "kroger.duckdb"
STAGING_DIR = Path(__file__).resolve().parent / "data" / "staging"  # one dir per day

STAGING_COLUMNS = [
    "State",
    "Store Name",
    "Store ID",
    "Product Category",
    "Product ID",
    "Description",
    "Brand",
    "Regular Price",
    "Promo Price",
    "Size",
]


def _sql_quote_path(path: Path) -> str:
    return str(path.resolve()).replace("'", "''")


def get_load_date():
    return date.today().strftime("%Y-%m-%d")

class KrogerAPI:
    def __init__(self):
        self.client_id = os.getenv("KROGER_CLIENT_ID")
        self.client_secret = os.getenv("KROGER_CLIENT_SECRET")
        self.token = None
        self.base_url = "https://api.kroger.com/v1"
        self.api_calls = 0
    
    def auth(self):
        """Authenticate with Kroger API"""
        print("Authenticating...")
        url = f"{self.base_url}/connect/oauth2/token"
        data = {
            "grant_type": "client_credentials",
            "scope": "product.compact"
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        try:
            resp = requests.post(
                url,
                auth=(self.client_id, self.client_secret),
                headers=headers,
                data=data
            )
            if resp.status_code == 200:
                self.token = resp.json().get("access_token")
                print("Authenticated!")
                return True
            print(f"Auth failed: {resp.status_code}")
            return False
        except Exception as e:
            print(f"Auth Error: {e}")
            return False

    def _ensure_token(self):
        """Refresh token if expired (401). Token lasts ~30 min."""
        if self.auth():
            return True
        return False

    def _store_has_products(self, location_id: str) -> bool:
        """Quick check: does this store return any products?"""
        products = self.search_products(term="milk", location_id=location_id, limit=1)
        return len(products) > 0

    def get_largest_store_per_state(self, state_zip_codes):
        """
        Get store per state: fetches locations (by distance), validates products.
        Skips state if no store returns products.
        """
        if not self.token:
            return {}

        print("Fetching stores per state (validating product availability)...")
        largest_stores = {}

        for state, zip_code in state_zip_codes.items():
            headers = {"Authorization": f"Bearer {self.token}"}
            params = {
                "filter.zipCode.near": zip_code,
                "filter.radiusInMiles": 100,
                "filter.limit": 50,
            }

            try:
                resp = requests.get(
                    f"{self.base_url}/locations",
                    headers=headers,
                    params=params,
                )

                if resp.status_code != 200:
                    print(f"{state}: API error {resp.status_code}")
                    continue

                locations = resp.json().get("data", [])
                if not locations:
                    print(f"{state}: No stores found")
                    continue

                # Try each store until one returns products; if none do, skip state
                chosen = None
                max_tries = 20  # Cap to limit API calls; increase if needed
                for store in locations[:max_tries]:
                    store_id = store.get("locationId")
                    store_name = store.get("name", "Unknown")
                    if self._store_has_products(store_id):
                        chosen = store
                        print(f"{state}: {store_name} (validated)")
                        break
                    print(f"  {state}: {store_name} - no products, trying next...")

                if chosen:
                    largest_stores[state] = chosen
                else:
                    # Skip state: no store in this state returns products
                    print(f"{state}: SKIPPED - no store with products found (tried {min(max_tries, len(locations))} stores)")

            except Exception as e:
                print(f"{state}: Error - {e}")

        return largest_stores

    def search_products(self, term, location_id, limit=200):
        """
        Search products with PAGINATION support
        
        Args:
            term (str): Search term
            location_id (str): Store location ID
            limit (int): Total products to get (default 200)
                        API max per request = 50, so this uses pagination
        """
        if not self.token:
            return []
        
        # Calculate how many pages needed
        # Each page returns max 50 products
        pages_needed = (limit + 49) // 50  # Ceiling division
        all_products = []
        
        for page in range(pages_needed):
            self.api_calls += 1  # Count this API call
            
            headers = {"Authorization": f"Bearer {self.token}"}
            params = {
                "filter.term": term,
                "filter.locationId": location_id,
                "filter.limit": 50,  # API max
                "filter.start": page * 50,  # Pagination: skip (page * 50) results
                "filter.fulfillment": "ais"
            }
            
            try:
                resp = requests.get(
                    f"{self.base_url}/products",
                    headers=headers,
                    params=params
                )
                if resp.status_code == 401:
                    print("  Token expired, refreshing...")
                    if self._ensure_token():
                        headers = {"Authorization": f"Bearer {self.token}"}
                        resp = requests.get(f"{self.base_url}/products", headers=headers, params=params)
                if resp.status_code == 200:
                    products = resp.json().get("data", [])
                    if not products:
                        break
                    all_products.extend(products)
                    if len(all_products) >= limit:
                        all_products = all_products[:limit]
                        break
                else:
                    print(f"  Products API {resp.status_code} (term={term})")
                    break
            except Exception as e:
                print(f"Error on page {page}: {e}")
                break
        
        return all_products


def flatten_product_rows(all_products_data):
    """squash api response into flat rows"""
    rows = []
    for state_data in all_products_data:
        state = state_data.get("state", "")
        store_id = state_data.get("store_id", "")
        store_name = state_data.get("store_name", "")
        for sr in state_data.get("search_results", []):
            category = sr.get("term", "")
            for p in sr.get("products", []):
                items = p.get("items", [])
                price = items[0].get("price", {}) if items else {}
                price = price if isinstance(price, dict) else {}
                rows.append({
                    "State": state,
                    "Store Name": store_name,
                    "Store ID": store_id,
                    "Product Category": category,
                    "Product ID": p.get("productId", ""),
                    "Description": p.get("description", ""),
                    "Brand": p.get("brand", ""),
                    "Regular Price": str(price.get("regular", "") or ""),
                    "Promo Price": str(price.get("promo", "") or ""),
                    "Size": items[0].get("size", "") if items else "",
                })
    return rows


def save_to_staging_parquet(rows, load_date_str):
    """dump to data/staging/YYYY-MM-DD/products.parquet"""
    dir_path = STAGING_DIR / load_date_str
    dir_path.mkdir(parents=True, exist_ok=True)
    parquet_path = dir_path / "products.parquet"
    if not rows:
        print("No rows to save.")
        return None
    col_defs = ", ".join(f'"{c}" VARCHAR' for c in STAGING_COLUMNS)
    insert_cols = ", ".join(f'"{c}"' for c in STAGING_COLUMNS)
    placeholders = ", ".join(["?"] * len(STAGING_COLUMNS))
    mem = duckdb.connect(":memory:")
    try:
        mem.execute(f"CREATE TABLE staging ({col_defs})")
        sql = f"INSERT INTO staging ({insert_cols}) VALUES ({placeholders})"
        tuples = [tuple(r.get(c, "") for c in STAGING_COLUMNS) for r in rows]
        mem.executemany(sql, tuples)
        pq = _sql_quote_path(parquet_path)
        mem.execute(f"COPY staging TO '{pq}' (FORMAT PARQUET)")
    finally:
        mem.close()
    print(f"Saved {len(rows)} rows to {parquet_path}")
    return parquet_path


def load_parquet_to_duckdb(parquet_path: Path | str, load_date_str):
    """create table per day, rebuild union view"""
    parquet_path = Path(parquet_path)
    table_name = f"kroger_products_{load_date_str.replace('-', '_')}"
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(DB_PATH))
    try:
        conn.execute("CREATE SCHEMA IF NOT EXISTS raw")
        pq = _sql_quote_path(parquet_path)
        conn.execute(f"""
            CREATE OR REPLACE TABLE raw.{table_name} AS
            SELECT *, '{load_date_str}'::DATE as load_date
            FROM read_parquet('{pq}')
        """)
        tables = conn.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'raw' AND table_name LIKE 'kroger_products_20%'
            ORDER BY table_name
        """).fetchall()
        union_parts = [f"SELECT * FROM raw.{t[0]}" for t in tables]
        if union_parts:
            union_sql = "CREATE OR REPLACE VIEW raw.kroger_products_all AS " + " UNION ALL ".join(union_parts)
            conn.execute(union_sql)
        print(f"Loaded {table_name} from {parquet_path}")
        return True
    except Exception as e:
        print(f"Error loading to DuckDB: {e}")
        return False
    finally:
        conn.close()


def main():    
    # Initialize API
    api = KrogerAPI()
    if not api.auth():
        return
    
    # 32 states with Kroger products
    state_zip_codes = {
        "Alabama": "35203",
        "Arizona": "85001",
        "Arkansas": "72201",
        "California": "90210",
        "Colorado": "80201",
        "Florida": "32202",
        "Georgia": "30303",
        "Idaho": "83702",
        "Illinois": "60601",
        "Indiana": "46201",
        "Kansas": "66101",
        "Kentucky": "40202",
        "Louisiana": "70801",   # Baton Rouge, NOLA had 0
        "Michigan": "48201",
        "Mississippi": "39201",
        "Missouri": "64101",   # KC, St Louis stores didnt validate
        "Nebraska": "68102",
        "Nevada": "89101",
        "New Mexico": "87101",
        "North Carolina": "28202",
        "Ohio": "45202",
        "Oklahoma": "74101",   
        "Oregon": "97201",
        "South Carolina": "29201",
        "Tennessee": "37201",
        "Texas": "77001",
        "Utah": "84101",
        "Virginia": "23510",
        "Washington": "98101",
        "West Virginia": "25301",
        "Wisconsin": "53201",
        "Wyoming": "82001",
    }
    
    # --- STEP 1: Get largest store per state ---
    
    largest_stores = api.get_largest_store_per_state(state_zip_codes)
    print(f"\nFound {len(largest_stores)}/{len(state_zip_codes)} states with stores\n")
    
    if not largest_stores:
        print("No stores found.")
        return
    
    # --- STEP 2: Define categories ---
    
    search_terms = [
        # FRESH FOODS (6)
        "meat", "seafood", "produce", "deli", "bakery", "eggs",
        
        # FOOD & BEVERAGE (6)
        "pantry", "beverage", "breakfast", "organic", "alcohol", "frozen",
        
        # HEALTH, BEAUTY & BABY (5)
        "health", "vitamins", "personal care", "beauty", "baby",
        
        # HOME ESSENTIALS (5)
        "batteries", "kitchen appliances", "electronics", "patio grilling", "cleaning",
        
        # PET, TOYS & FLORAL (3)
        "pet food", "toys", "flowers",
        
        # ADDITIONAL POPULAR (8)
        "snacks", "chips", "cookies", "nuts", "pasta sauce", "canned goods", "honey", "peanut butter"
    ]
    
    print(f"\nCategories: {len(search_terms)}")
    
    all_products_data = []
    total_products = 0
    
    for state, store in largest_stores.items():
        store_id = store.get('locationId')
        store_name = store.get('name')
        
        print(f"\n[{state}] {store_name}")
        
        store_search_results = []
        store_product_count = 0
        
        for term in search_terms:
            # Request 200 products (uses pagination internally)
            products = api.search_products(
                term=term,
                location_id=store_id,
                limit=200
            )
            
            if products:
                store_product_count += len(products)
                total_products += len(products)
                
                store_search_results.append({
                    'term': term,
                    'products': products
                })
                
                print(f"{term}: {len(products)} products")
            else:
                print(f"{term}: 0 products")
        
        print(f"Total for {state}: {store_product_count} products")
        
        all_products_data.append({
            'state': state,
            'store_id': store_id,
            'store_name': store_name,
            'search_results': store_search_results
        })
    
    # --- STEP 3: staging parquet + load to duckdb ---
    print("\n" + "=" * 90)
    print("STEP 3: STAGING PARQUET + LOADING TO DUCKDB")
    print("=" * 90 + "\n")

    load_date_str = get_load_date()
    rows = flatten_product_rows(all_products_data)
    parquet_path = save_to_staging_parquet(rows, load_date_str)
    if parquet_path:
        load_parquet_to_duckdb(parquet_path, load_date_str)
    
    # --- Summary ---
    print("\n" + "=" * 90)
    print("  COMPLETED SUCCESSFULLY")
    print("=" * 90)
    print(f"\nSummary:")
    print(f"   States searched: {len(largest_stores)}")
    print(f"   Categories per store: {len(search_terms)}")
    print(f"   Products per category: 100 (with pagination)")
    print(f"   Total API calls: {api.api_calls}")
    print(f"   Total unique products: {total_products}")
    
    print(f"\nData loaded to: data/staging/{load_date_str}/products.parquet -> raw.kroger_products_{load_date_str.replace('-', '_')}")
    
    print(f"\nAPI Rate Limit: 10,000 calls/day")
    print(f"   Used: {api.api_calls} calls")
    print(f"   Remaining: {10000 - api.api_calls} calls")

if __name__ == "__main__":
    main()
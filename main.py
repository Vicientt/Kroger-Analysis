"""
Kroger API - With Pagination Support
Get 200+ products per category using pagination
"""

import requests
import csv
import json
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class KrogerAPI:
    def __init__(self):
        self.client_id = os.getenv("KROGER_CLIENT_ID")
        self.client_secret = os.getenv("KROGER_CLIENT_SECRET")
        self.token = None
        self.base_url = "https://api.kroger.com/v1"
        self.api_calls = 0
    
    def auth(self):
        """Authenticate with Kroger API"""
        print("🔐 Authenticating...")
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
                print("✅ Authenticated!")
                return True
            print(f"❌ Auth failed: {resp.status_code}")
            return False
        except Exception as e:
            print(f"❌ Auth Error: {e}")
            return False

    def get_largest_store_per_state(self, state_zip_codes):
        """Get the largest store per state"""
        if not self.token:
            return {}
        
        print("📍 Fetching LARGEST store per state...")
        largest_stores = {}
        
        for state, zip_code in state_zip_codes.items():
            headers = {"Authorization": f"Bearer {self.token}"}
            params = {
                "filter.zipCode.near": zip_code,
                "filter.radiusInMiles": 100,
                "filter.limit": 10
            }
            
            try:
                resp = requests.get(
                    f"{self.base_url}/locations",
                    headers=headers,
                    params=params
                )
                
                if resp.status_code == 200:
                    locations = resp.json().get("data", [])
                    if locations:
                        largest_store = locations[0]
                        store_name = largest_store.get('name', 'Unknown')
                        store_id = largest_store.get('locationId', 'N/A')
                        largest_stores[state] = largest_store
                        print(f"{state}: {store_name}")
                    else:
                        print(f"{state}: No stores found")
                else:
                    print(f"{state}: API error {resp.status_code}")
            
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
                if resp.status_code == 200:
                    products = resp.json().get("data", [])
                    if not products:
                        # No more products available
                        break
                    all_products.extend(products)
                    
                    # Stop if we have enough
                    if len(all_products) >= limit:
                        all_products = all_products[:limit]
                        break
                else:
                    break
            
            except Exception as e:
                print(f"Error on page {page}: {e}")
                break
        
        return all_products

def save_all_products_csv(all_products_data, filename="all_products.csv"):
    """Save all products to CSV"""
    Path("data").mkdir(exist_ok=True)
    filepath = f"data/{filename}"
    
    try:
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'State', 'Store Name', 'Store ID', 'Product Category', 'Product ID',
                'Description', 'Brand', 'Regular Price', 'Promo Price', 'Size'
            ])
            writer.writeheader()
            
            for state_data in all_products_data:
                state = state_data['state']
                store_name = state_data['store_name']
                store_id = state_data['store_id']
                
                for search_cat in state_data['search_results']:
                    category = search_cat['term']
                    products = search_cat['products']
                    
                    for p in products:
                        items = p.get('items', [])
                        first_item = items[0] if items else {}
                        price_info = first_item.get('price', {})
                        
                        writer.writerow({
                            'State': state,
                            'Store Name': store_name,
                            'Store ID': store_id,
                            'Product Category': category,
                            'Product ID': p.get('productId'),
                            'Description': p.get('description'),
                            'Brand': p.get('brand'),
                            'Regular Price': price_info.get('regular', 'N/A'),
                            'Promo Price': price_info.get('promo', 'N/A'),
                            'Size': first_item.get('size', 'N/A')
                        })
        
        print(f"💾 Saved: {filepath}")
        return True
    except Exception as e:
        print(f"Error saving CSV: {e}")
        return False

def save_state_summary_csv(all_products_data, filename="state_summary.csv"):
    """Save summary per state"""
    Path("data").mkdir(exist_ok=True)
    filepath = f"data/{filename}"
    
    try:
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'State', 'Store Name', 'Total Products', 'Unique Brands', 'Categories Found'
            ])
            writer.writeheader()
            
            for state_data in all_products_data:
                all_products = []
                all_brands = set()
                categories_found = 0
                
                for search_cat in state_data['search_results']:
                    products = search_cat['products']
                    if products:
                        categories_found += 1
                        all_products.extend(products)
                        
                        for p in products:
                            brand = p.get('brand')
                            if brand:
                                all_brands.add(brand)
                
                writer.writerow({
                    'State': state_data['state'],
                    'Store Name': state_data['store_name'],
                    'Total Products': len(all_products),
                    'Unique Brands': len(all_brands),
                    'Categories Found': categories_found
                })
        
        print(f"💾 Saved: {filepath}")
        return True
    except Exception as e:
        print(f"Error saving summary: {e}")
        return False

def save_category_summary_csv(all_products_data, filename="category_summary.csv"):
    """Save summary per category"""
    Path("data").mkdir(exist_ok=True)
    filepath = f"data/{filename}"
    
    try:
        category_stats = {}
        
        for state_data in all_products_data:
            for search_cat in state_data['search_results']:
                term = search_cat['term']
                products = search_cat['products']
                
                if term not in category_stats:
                    category_stats[term] = {
                        'total_products': 0,
                        'states_with_products': 0,
                        'brands': set()
                    }
                
                if products:
                    category_stats[term]['total_products'] += len(products)
                    category_stats[term]['states_with_products'] += 1
                    
                    for p in products:
                        brand = p.get('brand')
                        if brand:
                            category_stats[term]['brands'].add(brand)
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'Category', 'Total Products', 'States with Products', 'Unique Brands'
            ])
            writer.writeheader()
            
            for term in sorted(category_stats.keys()):
                stats = category_stats[term]
                writer.writerow({
                    'Category': term,
                    'Total Products': stats['total_products'],
                    'States with Products': stats['states_with_products'],
                    'Unique Brands': len(stats['brands'])
                })
        
        print(f"Saved: {filepath}")
        return True
    except Exception as e:
        print(f"Error saving category summary: {e}")
        return False

def save_raw_json(all_products_data, filename="products_raw.json"):
    """Save raw data as JSON"""
    Path("data").mkdir(exist_ok=True)
    filepath = f"data/{filename}"
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(all_products_data, f, ensure_ascii=False, indent=2)
        print(f"💾 Saved: {filepath}")
        return True
    except Exception as e:
        print(f"Error saving JSON: {e}")
        return False

def main():
    print("=" * 90)
    print("   KROGER API - WITH PAGINATION (100+ PRODUCTS PER CATEGORY)")
    print("=" * 90 + "\n")
    
    # Initialize API
    api = KrogerAPI()
    if not api.auth():
        return
    
    # Test with 3 states only (to keep API calls low)
    state_zip_codes = {
        # West
        "California": "90210",
        "Washington": "98101",
        # "Oregon": "97201",
        # "Nevada": "89101",
        # "Arizona": "85001",
        # "New Mexico": "87101",
        # "Utah": "84101",
        # "Colorado": "80201",
        # "Wyoming": "82001",
        # "Idaho": "83702",
        # "Montana": "59101",
        
        # # Midwest
        # "Ohio": "44101",
        # "Indiana": "46201",
        # "Illinois": "60601",
        # "Michigan": "48201",
        # "Wisconsin": "53201",
        # "Minnesota": "55401",
        # "Missouri": "63101",
        # "Kansas": "66101",
        # "Nebraska": "68102",
        # "Iowa": "50301",
        
        # # South
        # "Texas": "75001",
        # "Oklahoma": "73102",
        # "Louisiana": "70112",
        # "Arkansas": "72201",
        # "Tennessee": "37201",
        # "Kentucky": "40202",
        # "Virginia": "23510",
        # "West Virginia": "25301",
        # "North Carolina": "28202",
        # "South Carolina": "29201",
        # "Georgia": "30303",
        # "Florida": "33101",
        # "Alabama": "35203",
        # "Mississippi": "39201",
    }
    
    # --- STEP 1: Get largest store per state ---
    print("\n" + "=" * 90)
    print("STEP 1: FINDING LARGEST STORE IN EACH STATE")
    print("=" * 90 + "\n")
    
    largest_stores = api.get_largest_store_per_state(state_zip_codes)
    print(f"\nFound {len(largest_stores)}/{len(state_zip_codes)} states with stores\n")
    
    if not largest_stores:
        print("No stores found.")
        return
    
    # --- STEP 2: Define categories ---
    print("=" * 90)
    print("STEP 2: SEARCHING CATEGORIES (WITH PAGINATION)")
    print("=" * 90)
    
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
    
    print(f"\n🔍 Categories: {len(search_terms)}")
    print(f"📊 Products per category: 200 (using pagination)")
    print(f"Note: 200 products = 4 API calls per search\n")
    
    all_products_data = []
    total_products = 0
    
    for state, store in largest_stores.items():
        store_id = store.get('locationId')
        store_name = store.get('name')
        
        print(f"\n[{state}] 🏢 {store_name}")
        
        store_search_results = []
        store_product_count = 0
        
        for term in search_terms:
            # Request 200 products (uses pagination internally)
            products = api.search_products(
                term=term,
                location_id=store_id,
                limit=200  # Now supports 100+!
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
        
        print(f"   📊 Total for {state}: {store_product_count} products")
        
        all_products_data.append({
            'state': state,
            'store_id': store_id,
            'store_name': store_name,
            'search_results': store_search_results
        })
    
    # --- STEP 3: Save data ---
    print("\n" + "=" * 90)
    print("STEP 3: SAVING DATA")
    print("=" * 90 + "\n")
    
    # Save without timestamp - will overwrite existing files
    save_all_products_csv(all_products_data, "all_products.csv")
    save_state_summary_csv(all_products_data, "state_summary.csv")
    save_category_summary_csv(all_products_data, "category_summary.csv")
    save_raw_json(all_products_data, "products_raw.json")
    
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
    
    print(f"\nFiles saved in data/ directory:")
    print(f"   1. all_products.csv")
    print(f"   2. state_summary.csv")
    print(f"   3. category_summary.csv")
    print(f"   4. products_raw.json")
    
    print(f"\nAPI Rate Limit: 10,000 calls/day")
    print(f"   Used: {api.api_calls} calls")
    print(f"   Remaining: {10000 - api.api_calls} calls")

if __name__ == "__main__":
    main()
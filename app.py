from flask import Flask, render_template, request, jsonify
import requests
import pandas as pd
import os
import re
import json
import urllib.parse
from datetime import datetime, timedelta

app = Flask(__name__)

# Configuration - Update these as needed
COMPARIFY_API_URL = "https://api.comparify.pro/api/aggregate"
LOCATION_AUTOCOMPLETE_URL = "https://api.comparify.pro/api/location-autocomplete"
STORE_IDS_API_URL = "https://api.comparify.pro/api/store-ids"
SHOP_NAME = "My Local Shop"
SHOP_CSV_FILE = "shop_prices.csv"

# Default location parameters (you can change these)
DEFAULT_LOCATION = {"latitude": 28.4838282, "longitude": 77.00285219999999}
DEFAULT_PINCODE = "122006"

# Cache for store IDs to avoid frequent API calls
store_ids_cache = {}
CACHE_DURATION = timedelta(hours=1)  # Cache store IDs for 1 hour

def load_shop_prices():
    """Load shop prices from CSV file"""
    if os.path.exists(SHOP_CSV_FILE):
        try:
            df = pd.read_csv(SHOP_CSV_FILE)
            print(f"succesfully read file")
            # Convert to dictionary for easy lookup
            # Expected columns: product_name, price, unit, in_stock
            return df.to_dict('records')
        except Exception as e:
            print(f"Error loading shop prices: {e}")
            return []
    return []

def find_shop_price(product_name, shop_data):
    """Find matching price from shop data"""
    product_name_lower = product_name.lower()
    for item in shop_data:
        item_name_lower = item['product_name'].lower()
        if item_name_lower in product_name_lower or product_name_lower in item_name_lower:
            return {
                'price': item.get('price'),
                'unit': item.get('unit', ''),
                'in_stock': item.get('in_stock', True)
            }
    return None

def get_store_ids(location, pincode):
    """Fetch store IDs dynamically based on location"""
    cache_key = f"{location['latitude']}_{location['longitude']}_{pincode}"
    
    print(f"🔍 GET_STORE_IDS CALLED - Cache Key: {cache_key}")
    
    # Check cache first
    if cache_key in store_ids_cache:
        cache_data = store_ids_cache[cache_key]
        time_diff = datetime.now() - cache_data['timestamp']
        if time_diff < CACHE_DURATION:
            print(f"✅ USING CACHED STORE IDs (age: {time_diff})")
            return cache_data['store_ids']
        else:
            # Remove expired cache
            print(f"🗑️ REMOVING EXPIRED CACHE: {cache_key}")
            del store_ids_cache[cache_key]
    
    try:
        params = {
            'userLocation': json.dumps(location),
            'provider': 'instamart,zepto,flipkart-minutes,dmart,jiomart,blinkit,bigbasket',
            'pincode': pincode
        }
        
        print(f"🚀 CALLING STORE IDS API: {params}")
        response = requests.get(STORE_IDS_API_URL, params=params, timeout=10)
        response.raise_for_status()
        store_data = response.json()
        
        print(f"✅ STORE IDS API RESPONSE: {store_data}")
        
        # Extract store IDs from response
        store_ids = {
            'instamart': store_data.get('instamart', {}).get('storeId'),
            'zepto': store_data.get('zepto', {}).get('storeId'),
            'dmart': store_data.get('dmart', {}).get('storeId'),
            'blinkit': store_data.get('blinkit', {}).get('storeId'),
            'bigbasket': store_data.get('bigbasket', {}).get('storeId'),
            'jiomart': {
                'jsc': store_data.get('jiomart', {}).get('jsc'),
                'jrc': store_data.get('jiomart', {}).get('jrc')
            },
            'flipkart-minutes': store_data.get('flipkart-minutes', {}).get('storeId')
        }
        
        # Cache the store IDs
        store_ids_cache[cache_key] = {
            'store_ids': store_ids,
            'timestamp': datetime.now()
        }
        
        print(f"💾 STORE IDs CACHED: {store_ids}")
        
        return store_ids
        
    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR FETCHING STORE IDs: {e}")
        # Return fallback store IDs if API fails
        fallback = get_fallback_store_ids()
        print(f"🔄 USING FALLBACK STORE IDs: {fallback}")
        return fallback
    

def get_fallback_store_ids():
    """Fallback store IDs in case API fails"""
    return {
        'instamart': '1389005',
        'zepto': '005dcc9a-d50c-442f-ae5e-f89f35d1a01a',
        'dmart': '10711',
        'blinkit': None,
        'bigbasket': None,
        'jiomart': {
            'jsc': 'TM8H',
            'jrc': '6701'
        },
        'flipkart-minutes': None
    }

def fetch_comparify_data(query, location, pincode):
    """Fetch data from API using dynamic store IDs"""
    try:

         # 🔥 DEBUG: Print before getting store IDs
        print(f"🔥 FETCH_COMPARIFY_DATA - Query: {query}, Location: {location}, Pincode: {pincode}")
        
        # Get store IDs for this location
        store_ids = get_store_ids(location, pincode)
        print(f"🔥 STORE IDs RECEIVED: {store_ids}")
        
        # Prepare parameters for aggregate API
        params = {
            'query': query,
            'userLocation': json.dumps(location),
            'pincode': pincode
        }
        
        # Add store IDs for each provider that has one
        if store_ids.get('instamart'):
            params['instamartStoreId'] = store_ids['instamart']
        if store_ids.get('zepto'):
            params['zeptoStoreId'] = store_ids['zepto']
        if store_ids.get('dmart'):
            params['dmartStoreId'] = store_ids['dmart']
        if store_ids.get('blinkit'):
            params['blinkitStoreId'] = store_ids['blinkit']
        if store_ids.get('bigbasket'):
            params['bigbasketStoreId'] = store_ids['bigbasket']
        if store_ids.get('flipkart-minutes'):
            params['flipkartMinutesStoreId'] = store_ids['flipkart-minutes']
        
        # JioMart uses different parameters
        if store_ids.get('jiomart', {}).get('jsc'):
            params['jiomartJSC'] = store_ids['jiomart']['jsc']
        if store_ids.get('jiomart', {}).get('jrc'):
            params['jiomartJRC'] = store_ids['jiomart']['jrc']
       
        print(f"API Params: {params}")
        response = requests.get(COMPARIFY_API_URL, params=params, timeout=15)
        print(f"API Status: {response.status_code}")
        
        # Parse response
        api_response = response.json()
        
        # Print summary
        print(f"API Response Keys: {list(api_response.keys())}")
        print("=== SOURCES RECEIVED ===")
        for source, data in api_response.items():
            if isinstance(data, dict):
                products_count = len(data.get('products', []))
                print(f"{source}: {type(data)} - {products_count} products")
                
                # 🔥 DEBUG EMPTY SOURCES
                if products_count == 0:
                    # Print the full dict for empty sources
                    print(f"  📦 Full response: {json.dumps(data, indent=2)}")
                    
            elif isinstance(data, list):
                print(f"{source}: {type(data)} - {len(data)} products")
                if len(data) == 0:
                    print(f"  📦 Empty list response")
        print("========================")
        
        response.raise_for_status()
        return api_response
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from Comparify: {e}")
        return None

def normalize_product_name(name):
    """Normalize product name for matching"""
    if not name:
        return ""
    # Remove extra spaces, convert to lowercase
    name = re.sub(r'\s+', ' ', name.lower().strip())
    # Remove special characters in parentheses (units, descriptions)
    name = re.sub(r'\([^)]*\)', '', name)
    # Remove common unit suffixes if they are standalone
    name = re.sub(r'\b(kg|g|ml|l|pack|pcs?)\b', '', name)
    return name.strip()

def build_image_url(source, image):
    """Build full image URL based on source-specific patterns"""
    if not image:
        return ""
    
    # Take first image if array
    if isinstance(image, list):
        image = image[0] if image else ""
    
    source_lower = source.lower()
    
    # Instamart/Swiggy: Relative paths like "NI_CATALOG/IMAGES/CIW/..."
    if source_lower == 'instamart' and isinstance(image, str) and image.startswith('NI_CATALOG/IMAGES/'):
        return f"https://media-assets.swiggy.com/swiggy/image/upload/fl_lossy,f_auto,q_auto,w_252,h_272/{image}"
    
    # Zepto: Nested path like "cms/product_variant/..."
    elif source_lower == 'zepto' and isinstance(image, dict) and 'path' in image:
        path = image['path']
        if path.startswith('cms/'):
            return f"https://cdn.zeptonow.com/production/{path}"
    
    # Blinkit: Uses Grofers CDN
    elif source_lower == 'blinkit' and isinstance(image, str):
        if not image.startswith('http'):
            return f"https://cdn.grofers.com/{image}" if image else ""
        return image
    
    # BigBasket: Usually has full URLs
    elif source_lower == 'bigbasket' and isinstance(image, str):
        if not image.startswith('http'):
            return f"https://www.bbassets.com/{image}" if image else ""
        return image
    
    # DMart: Already has full URLs in the response
    elif source_lower == 'dmart' and isinstance(image, str):
        if not image.startswith('http'):
            # If somehow we get relative URLs for DMart
            return f"https://cdn.dmart.in/{image}" if image else ""
        return image
    
    # JioMart: Already has full URLs in the response  
    elif source_lower == 'jiomart' and isinstance(image, str):
        if not image.startswith('http'):
            # If somehow we get relative URLs for JioMart
            return f"https://www.jiomart.com/{image}" if image else ""
        return image
    
    # Flipkart: Usually full URLs
    elif source_lower == 'flipkart-minutes' and isinstance(image, str):
        if not image.startswith('http'):
            return f"https://fkcdn.com/{image}" if image else ""
        return image
    
    # Direct URLs for other sources
    elif isinstance(image, str) and image.startswith('http'):
        return image
    
    return ""  # Invalid/empty

def get_selling_price(raw, source):
    """Extract selling price from raw value (dict or scalar), normalize paise"""
    if raw is None:
        return None
    if isinstance(raw, dict):
        price = (raw.get('offer_price') or raw.get('offerPrice') or
                 raw.get('sellingPrice') or raw.get('superSaverSellingPrice') or
                 raw.get('mrp') or raw.get('price') or raw.get('offer'))
    else:
        price = raw
    if price is None:
        return None
    if isinstance(price, (int, float)):
        if source.lower() == 'zepto' or price > 1000:
            price /= 100.0
    return price

def get_mrp(raw, source):
    """Extract MRP from raw value (dict or scalar), normalize paise"""
    if raw is None:
        return None
    if isinstance(raw, dict):
        mrp_val = (raw.get('mrp') or raw.get('sellingPrice') or
                   raw.get('superSaverSellingPrice') or
                   raw.get('offer_price') or raw.get('offerPrice') or
                   raw.get('price'))
    else:
        mrp_val = raw
    if mrp_val is None:
        return None
    if isinstance(mrp_val, (int, float)):
        if source.lower() == 'zepto' or mrp_val > 1000:
            mrp_val /= 100.0
    return mrp_val

def merge_shop_data(query, comparify_data, shop_data):
    """Merge shop data with Comparify data - GROUP BY PRODUCT"""
    if not comparify_data:
        return None
   
    query_lower = query.lower()
   
    # Filter shop data
    filtered_shop_data = []
    for item in shop_data:
        normalized_item = normalize_product_name(item['product_name'])
        if query_lower in normalized_item or normalized_item in query_lower:
            filtered_shop_data.append(item)
   
    print(f"Filtered {len(filtered_shop_data)} shop items for query '{query}'")
   
    products_map = {}
   
    # Process all Comparify sources
    for source, data in comparify_data.items():
        print(f"\n=== Processing source: {source} ===")
        print(f"Data type: {type(data)}")
        
        products = []
        
        # 🔥 IMPROVED DATA EXTRACTION FOR ALL SOURCES
        if isinstance(data, list):
            # Handle Zepto and other array-based responses
            products = data
            print(f"✅ Processing {source} as LIST with {len(products)} items")
            
        elif isinstance(data, dict):
            # Handle all dict-based responses with different structures
            if 'products' in data:
                products = data['products']
                print(f"✅ Processing {source} as DICT with 'products' key - {len(products)} items")
            elif source.lower() == 'dmart' and 'data' in data:
                # DMart might use 'data' instead of 'products'
                products = data.get('data', [])
                print(f"✅ Processing {source} as DICT with 'data' key - {len(products)} items")
            else:
                # Try to find any list in the dict that might contain products
                for key, value in data.items():
                    if isinstance(value, list) and key not in ['variants', 'variations']:
                        products = value
                        print(f"✅ Processing {source} as DICT with '{key}' key - {len(products)} items")
                        break
                if not products:
                    print(f"⚠️ No products found in {source} dict structure")
        else:
            print(f"⚠️ Skipping {source} - unexpected structure: {type(data)}")
            continue
       
        print(f"📦 Final extracted {len(products)} products from {source}")
       
        # Add each product to the map
        for product in products:
            # 🔥 IMPROVED NAME EXTRACTION FOR ALL SOURCES
            name = ""
            
            # Try different name fields based on source
            if source.lower() == 'zepto':
                name = product.get('product', {}).get('name', '') if isinstance(product, dict) else ''
            elif source.lower() == 'dmart':
                name = product.get('product_name') or product.get('name', '')
            elif source.lower() == 'jiomart':
                name = product.get('product_name') or product.get('name', '')
            elif source.lower() == 'flipkart-minutes':
                name = product.get('product_name') or product.get('name', '')
            else:
                # Default name extraction
                name = (product.get('name') or 
                       product.get('display_name') or 
                       product.get('normalizedName') or
                       product.get('product', {}).get('name', ''))
            
            if not name:
                # Debug: Print product structure if name not found
                print(f"  🔍 No name found in product: {str(product)[:200]}")
                continue
            
            # Normalize name for grouping
            normalized_name = normalize_product_name(name)
           
            # 🔥 IMPROVED PRICE EXTRACTION
            price = None
            mrp = None
            
            if source.lower() == 'zepto':
                # Zepto specific price fields
                price = product.get('sellingPrice')
                mrp = product.get('superSaverSellingPrice') or price
                # Handle paise conversion
                if price and isinstance(price, (int, float)) and price > 1000:
                    price = price / 100.0
                if mrp and isinstance(mrp, (int, float)) and mrp > 1000:
                    mrp = mrp / 100.0
                    
            elif source.lower() == 'dmart':
                # DMart specific price fields
                price = product.get('selling_price') or product.get('price')
                mrp = product.get('mrp') or product.get('actual_price') or price
                
            elif source.lower() == 'jiomart':
                # JioMart specific price fields  
                price = product.get('selling_price') or product.get('price')
                mrp = product.get('mrp') or product.get('actual_price') or price
                
            elif source.lower() == 'flipkart-minutes':
                # Flipkart specific price fields
                price = product.get('selling_price') or product.get('price')
                mrp = product.get('mrp') or product.get('actual_price') or price
                
            else:
                # Default price extraction for other sources
                if 'price' in product:
                    if isinstance(product['price'], dict):
                        price = product['price'].get('offerPrice') or product['price'].get('offer_price') or product['price'].get('mrp')
                    else:
                        price = product['price']
                elif 'sellingPrice' in product:
                    price = product['sellingPrice']
                elif 'offer_price' in product:
                    price = product['offer_price']
               
                # Extract MRP
                if 'mrp' in product:
                    mrp = product['mrp']
                elif 'price' in product and isinstance(product['price'], dict):
                    mrp = product['price'].get('mrp')
                elif 'superSaverSellingPrice' in product:
                    mrp = product['superSaverSellingPrice']
                
                if not mrp:
                    mrp = price
                    
                # Handle paise conversion for other sources
                if source.lower() == 'zepto' and price and isinstance(price, (int, float)) and price > 1000:
                    price = price / 100.0
                if source.lower() == 'zepto' and mrp and isinstance(mrp, (int, float)) and mrp > 1000:
                    mrp = mrp / 100.0
            
            # 🔥 IMPROVED UNIT EXTRACTION
            unit = ""
            if source.lower() == 'zepto':
                unit = product.get('productVariant', {}).get('formattedPacksize', '')
            elif source.lower() in ['dmart', 'jiomart', 'flipkart-minutes']:
                unit = product.get('unit') or product.get('quantity') or product.get('pack_size', '')
            else:
                unit = (product.get('unit') or 
                       product.get('quantity') or 
                       product.get('sku_quantity_with_combo') or
                       product.get('productVariant', {}).get('formattedPacksize', ''))
           
            # 🔥 IMPROVED STOCK STATUS
            out_of_stock = False
            if source.lower() == 'zepto':
                out_of_stock = product.get('outOfStock', False)
            elif source.lower() in ['dmart', 'jiomart', 'flipkart-minutes']:
                out_of_stock = product.get('out_of_stock') or product.get('outOfStock') or not product.get('in_stock', True)
            else:
                out_of_stock = (product.get('out_of_stock') or 
                               product.get('outOfStock') or 
                               not product.get('in_stock', True))
           
            # Extract image
            raw_image = None
            if source.lower() == 'zepto':
                if 'productVariant' in product and product['productVariant']:
                    images = product['productVariant'].get('images', [])
                    if images and isinstance(images, list):
                        raw_image = images[0].get('path') if isinstance(images[0], dict) else images[0]
            elif source.lower() in ['dmart', 'jiomart', 'flipkart-minutes']:
                raw_image = product.get('image_url') or product.get('imageUrl') or product.get('image')
            else:
                if 'productVariant' in product and product['productVariant']:
                    images = product['productVariant'].get('images', [])
                    if images and isinstance(images, list):
                        raw_image = images[0].get('path') if isinstance(images[0], dict) else images[0]
                elif 'image_url' in product:
                    raw_image = product['image_url']
                elif 'imageUrl' in product:
                    raw_image = product['imageUrl']
                elif 'image' in product:
                    raw_image = product['image']
           
            image_url = build_image_url(source, raw_image)
           
            # ===== HANDLE VARIATIONS/VARIANTS =====
            # (Yeh part same rahega, but source-specific variations handle karega)
            variations_list = (product.get('variations') or 
                             product.get('variants') or [])
            
            if variations_list:
                print(f"Found {len(variations_list)} variations for {name} in {source}")
                # ... variations handling code same as before ...
                continue
           
            # ===== ADD REGULAR PRODUCT =====
            if normalized_name not in products_map:
                products_map[normalized_name] = {
                    'name': name,
                    'image_url': image_url,
                    'platforms': []
                }
           
            if price is not None:
                products_map[normalized_name]['platforms'].append({
                    'source': source.title(),
                    'price': price,
                    'mrp': mrp,
                    'unit': unit,
                    'in_stock': not out_of_stock,
                    'is_my_shop': False
                })
                print(f"  ✅ Added product: {name} - ₹{price}")
            else:
                print(f"  ❌ Skipped product (no price): {name}")
   
    # Add filtered shop's data (same as before)
    for item in filtered_shop_data:
        normalized_name = normalize_product_name(item['product_name'])
       
        if normalized_name not in products_map:
            products_map[normalized_name] = {
                'name': item['product_name'],
                'image_url': '',
                'platforms': []
            }
       
        shop_price = item.get('price')
        if shop_price and isinstance(shop_price, (int, float)) and shop_price > 1000:
            shop_price = shop_price / 100.0
       
        products_map[normalized_name]['platforms'].append({
            'source': SHOP_NAME,
            'price': shop_price,
            'mrp': shop_price,
            'unit': item.get('unit', ''),
            'in_stock': item.get('in_stock', True),
            'is_my_shop': True
        })
   
    # Convert to list and sort platforms by price (same as before)
    result_products = []
    for key, product_data in products_map.items():
        platforms = sorted(product_data['platforms'],
                          key=lambda x: (not x['in_stock'], x['price'] or float('inf')))
       
        # Mark cheapest (first in-stock)
        for plat in platforms:
            if plat['in_stock']:
                plat['is_cheapest'] = True
                break
       
        result_products.append({
            'name': product_data['name'],
            'image_url': product_data['image_url'],
            'platforms': platforms,
            'platform_count': len(platforms),
            'cheapest_price': platforms[0]['price'] if platforms and platforms[0]['in_stock'] else None
        })
   
    # Sort products by cheapest price
    result_products.sort(key=lambda x: x['cheapest_price'] if x['cheapest_price'] is not None else float('inf'))
    
    print(f"\n🎯 FINAL RESULT: {len(result_products)} unique products with data from {len([p for p in result_products if p['platforms']])} sources")
   
    return {'products': result_products}
@app.route('/location-search')
def location_search():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify({'info': {'status': 'success'}, 'data': []})
    
    lat_bias = request.args.get('lat', '28.4838282')
    lng_bias = request.args.get('lng', '77.0028522')
    
    try:
        payload = {
            "searchWord": q,
            "location": {
                "lat": float(lat_bias),
                "lng": float(lng_bias)
            }
        }
        headers = {'Content-Type': 'application/json'}
        response = requests.post(LOCATION_AUTOCOMPLETE_URL, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Return data directly without geocoding - this makes autocomplete fast
        # Geocoding will happen only on selection via /get-coords
        if data.get('info', {}).get('status') == 'success':
            return jsonify(data)
        else:
            return jsonify({'info': {'status': 'success'}, 'data': []})
    except Exception as e:
        print(f"Location search error: {e}")
        return jsonify({"info": {"status": "success"}, "data": []})

@app.route('/get-coords')
def get_coords():
    """Get lat/lng for a selected location description (called after selection)"""
    desc = request.args.get('desc', '')
    if not desc:
        return jsonify({'lat': DEFAULT_LOCATION['latitude'], 'lng': DEFAULT_LOCATION['longitude']})
    
    try:
        nom_url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(desc)}&format=json&limit=1&countrycodes=in"
        nom_resp = requests.get(nom_url, headers={'User-Agent': 'SmartCompare/1.0'}, timeout=5)
        nom_resp.raise_for_status()
        nom_data = nom_resp.json()
        if nom_data:
            lat_ = float(nom_data[0].get('lat', DEFAULT_LOCATION['latitude']))
            lng_ = float(nom_data[0].get('lon', DEFAULT_LOCATION['longitude']))
            return jsonify({'lat': lat_, 'lng': lng_})
    except Exception as e:
        print(f"Geocoding error: {e}")
    
    # Fallback
    return jsonify({'lat': DEFAULT_LOCATION['latitude'], 'lng': DEFAULT_LOCATION['longitude']})

@app.route('/')
def index():
    """Home page"""
    return render_template('index.html', shop_name=SHOP_NAME)

@app.route('/search')
@app.route('/search')
def search():
    """Search endpoint"""
    query = request.args.get('query', '').strip()
   
    lat_str = request.args.get('lat')
    lng_str = request.args.get('lng')
    pincode = request.args.get('pincode', DEFAULT_PINCODE)
    
    if lat_str and lng_str:
        location = {"latitude": float(lat_str), "longitude": float(lng_str)}
    else:
        location = DEFAULT_LOCATION
   
    if not query:
        return jsonify({'error': 'Query parameter is required'}), 400
    
    # 🔥 DEBUG: Print incoming location
    print(f"🔥 SEARCH CALLED - Location: {location}, Pincode: {pincode}")
   
    # Load shop prices
    shop_data = load_shop_prices()
   
    # Fetch Comparify data with dynamic store IDs
    comparify_data = fetch_comparify_data(query, location, pincode)
   
    if comparify_data is None:
        return jsonify({'error': 'Failed to fetch data from Comparify'}), 500
   
    # Merge data with query filter
    merged_data = merge_shop_data(query, comparify_data, shop_data)
    if not merged_data or not merged_data.get('products'):
        return jsonify({'error': 'No data available'}), 404
   
    return jsonify(merged_data)

@app.route('/clear-store-cache')
def clear_store_cache():
    """Clear store IDs cache (for debugging)"""
    store_ids_cache.clear()
    return jsonify({'success': True, 'message': 'Store cache cleared'})

if __name__ == '__main__':
    # Check if shop CSV exists, create template if not
    if not os.path.exists(SHOP_CSV_FILE):
        print(f"Creating template CSV file: {SHOP_CSV_FILE}")
        template_df = pd.DataFrame({
            'product_name': ['Aashirvaad Shudh Chakki Atta (5 kg)', 'Fortune Chakki Fresh Atta (5 kg)'],
            'price': [235, 210],
            'unit': ['5 kg', '5 kg'],
            'in_stock': [True, True]
        })
        template_df.to_csv(SHOP_CSV_FILE, index=False)
   
    app.run(debug=True, port=5000)
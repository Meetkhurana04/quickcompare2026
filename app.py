from flask import Flask, render_template, request, jsonify
import requests
import pandas as pd
import os
import re
import json

app = Flask(__name__) 

# Configuration - Update these as needed
COMPARIFY_API_URL = "https://api.comparify.pro/api/aggregate"
SHOP_NAME = "My Local Shop"
SHOP_CSV_FILE = "shop_prices.csv"

# Default location parameters (you can change these)
DEFAULT_STORE_ID = "005dcc9a-d50c-442f-ae5e-f89f35d1a01a"
DEFAULT_INSTAMART_STORE_ID = "1389005"
DEFAULT_DMART_STORE_ID = "10711"
DEFAULT_LOCATION = {"latitude": 28.4838282, "longitude": 77.00285219999999}
DEFAULT_PINCODE = "122006"

def load_shop_prices():
    """Load shop prices from CSV file"""
    if os.path.exists(SHOP_CSV_FILE):
        try:
            df = pd.read_csv(SHOP_CSV_FILE)
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

def fetch_comparify_data(query):
    """Fetch data from Comparify API"""
    try:
        params = {
            'query': query,
            'storeId': DEFAULT_STORE_ID,
            'instamartStoreId': DEFAULT_INSTAMART_STORE_ID,
            'dmartStoreId': DEFAULT_DMART_STORE_ID,
            'userLocation': json.dumps(DEFAULT_LOCATION),  # Use json.dumps for proper JSON string
            'pincode': DEFAULT_PINCODE
        }
        
        response = requests.get(COMPARIFY_API_URL, params=params, timeout=10)
        # Debug prints (remove once fixed)
        print(f"API Status: {response.status_code}")
        print(f"API Response: {response.text[:500]}...")  # First 500 chars for debugging
        response.raise_for_status()
        return response.json()
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
        image = image[0]
    
    # Instamart/Swiggy: Relative paths like "NI_CATALOG/IMAGES/CIW/..."
    if source.lower() == 'instamart' and isinstance(image, str) and image.startswith('NI_CATALOG/IMAGES/'):
        return f"https://media-assets.swiggy.com/swiggy/image/upload/fl_lossy,f_auto,q_auto,w_252,h_272/{image}"
    
    # Zepto: Nested path like "cms/product_variant/..."
    elif source.lower() == 'zepto' and isinstance(image, dict) and 'path' in image:
        path = image['path']
        if path.startswith('cms/'):
            return f"https://cdn.zeptonow.com/production/{path}"
    
    # Direct URLs (Blinkit, BigBasket, DMart, JioMart, Flipkart): Use as-is or prepend if needed
    elif isinstance(image, str):
        if not image.startswith('http'):
            # DMart-specific prepend (if needed, but usually direct)
            if 'dmart' in source.lower() and image.startswith('images/products/'):
                return f"https://cdn.dmart.in/{image}"
            # Others (rare relative)
            return f"https://via.placeholder.com/200?text=Product"  # Fallback if truly relative
        return image
    
    return ""  # Invalid/empty

def merge_shop_data(query, comparify_data, shop_data):
    """Merge shop data with Comparify data - GROUP BY PRODUCT"""
    if not comparify_data:
        return None
    
    query_lower = query.lower()
    
    # Filter shop data to only include items relevant to the query
    filtered_shop_data = []
    for item in shop_data:
        normalized_item = normalize_product_name(item['product_name'])
        if query_lower in normalized_item or normalized_item in query_lower:
            filtered_shop_data.append(item)
    
    print(f"Filtered {len(filtered_shop_data)} shop items for query '{query}'")  # Debug
    
    # Dictionary to store products: key = normalized name, value = product data
    products_map = {}
    
    # Process all Comparify sources
    for source, data in comparify_data.items():
        products = []
        if isinstance(data, list):
            products = data  # zepto, flipkart-minutes, etc.
        elif isinstance(data, dict) and 'products' in data:
            products = data['products']  # instamart, bigbasket, etc.
        
        # Add each product to the map
        for product in products:
            name = product.get('name') or product.get('display_name') or product.get('normalizedName', '')
            if not name:
                continue
            
            # Normalize name for grouping
            normalized_name = normalize_product_name(name)
            
            # Get product details
            price = product.get('price') or product.get('sellingPrice') or product.get('offer_price')
            if isinstance(price, dict):
                price = price.get('offer_price') or price.get('mrp')
            
            # Handle paise (e.g., Zepto uses paise - large numbers)
            if source.lower() == 'zepto' and price and isinstance(price, (int, float)):
                price = price / 100.0
            
            # Handle price in paise vs rupees for other sources if needed (threshold)
            elif price and isinstance(price, (int, float)) and price > 1000:
                price = price / 100.0
            
            mrp = product.get('mrp') or product.get('superSaverSellingPrice') or price
            if source.lower() == 'zepto' and mrp and isinstance(mrp, (int, float)):
                mrp = mrp / 100.0
            elif mrp and isinstance(mrp, (int, float)) and mrp > 1000:
                mrp = mrp / 100.0
            
            unit = product.get('unit') or product.get('quantity') or product.get('sku_quantity_with_combo') or product.get('productVariant', {}).get('formattedPacksize', '')
            out_of_stock = product.get('out_of_stock') or product.get('outOfStock') or not product.get('in_stock', True)
            
            # Extract raw image (before building full URL)
            raw_image = (product.get('productVariant', {}).get('images', [{}])[0].get('path') if product.get('productVariant') else 
                         product.get('image_url') or product.get('imageUrl') or '')
            
            # Build full URL
            image_url = build_image_url(source, raw_image)
            
            # Handle variations for instamart/bigbasket etc.
            if 'variations' in product and product['variations']:
                added_variations = set()  # To avoid duplicates
                for variation in product['variations']:
                    var_price = variation.get('price', {}).get('offer_price') or price
                    if source.lower() == 'zepto' and var_price and isinstance(var_price, (int, float)):
                        var_price = var_price / 100.0
                    elif var_price and isinstance(var_price, (int, float)) and var_price > 1000:
                        var_price = var_price / 100.0
                    
                    var_unit = variation.get('quantity', unit)
                    var_mrp = variation.get('price', {}).get('mrp') or mrp
                    if source.lower() == 'zepto' and var_mrp and isinstance(var_mrp, (int, float)):
                        var_mrp = var_mrp / 100.0
                    elif var_mrp and isinstance(var_mrp, (int, float)) and var_mrp > 1000:
                        var_mrp = var_mrp / 100.0
                    
                    # Extract raw image for variation
                    var_images = variation.get('images', [])
                    if var_images and isinstance(var_images, list) and var_images:
                        var_image_raw = var_images[0]
                    else:
                        var_image_raw = raw_image
                    
                    # Build full URL for variation
                    var_image = build_image_url(source, var_image_raw)
                    
                    var_key = normalize_product_name(f"{name} {var_unit}")
                    if var_key not in added_variations:
                        if var_key not in products_map:
                            products_map[var_key] = {
                                'name': f"{name} ({var_unit})",
                                'image_url': var_image,
                                'platforms': []
                            }
                        
                        products_map[var_key]['platforms'].append({
                            'source': source.title(),
                            'price': var_price,
                            'mrp': var_mrp,
                            'unit': var_unit,
                            'in_stock': variation.get('inventory', {}).get('in_stock', not out_of_stock),
                            'is_my_shop': False
                        })
                        added_variations.add(var_key)
                continue  # Skip adding the main product if variations were processed
            
            # Regular product (non-variation)
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
    
    # Add filtered shop's data
    for item in filtered_shop_data:
        normalized_name = normalize_product_name(item['product_name'])
        
        if normalized_name not in products_map:
            products_map[normalized_name] = {
                'name': item['product_name'],
                'image_url': '',  # Add image support in CSV if needed
                'platforms': []
            }
        
        shop_price = item.get('price')
        # Handle shop price if in paise (unlikely, but consistent)
        if shop_price and isinstance(shop_price, (int, float)) and shop_price > 1000:
            shop_price = shop_price / 100.0
        
        products_map[normalized_name]['platforms'].append({
            'source': SHOP_NAME,
            'price': shop_price,
            'mrp': shop_price,  # Assume no MRP for shop
            'unit': item.get('unit', ''),
            'in_stock': item.get('in_stock', True),
            'is_my_shop': True
        })
    
    # Convert to list and sort platforms by price
    result_products = []
    for key, product_data in products_map.items():
        # Sort platforms by price (cheapest first, in-stock preferred)
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
    
    return {'products': result_products}

@app.route('/')
def index():
    """Home page"""
    return render_template('index.html', shop_name=SHOP_NAME)

@app.route('/search')
def search():
    """Search endpoint"""
    query = request.args.get('query', '').strip()
    
    if not query:
        return jsonify({'error': 'Query parameter is required'}), 400
    
    # Load shop prices
    shop_data = load_shop_prices()
    
    # Fetch Comparify data
    comparify_data = fetch_comparify_data(query)
    
    if comparify_data is None:
        return jsonify({'error': 'Failed to fetch data from Comparify'}), 500
    
    # Merge data with query filter
    merged_data = merge_shop_data(query, comparify_data, shop_data)
    if not merged_data or not merged_data.get('products'):
        return jsonify({'error': 'No data available'}), 404
    
    return jsonify(merged_data)

@app.route('/update-location', methods=['POST'])
def update_location():
    """Update location settings"""
    data = request.json
    # You can implement location update logic here
    return jsonify({'success': True})

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
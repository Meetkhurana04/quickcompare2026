from flask import Flask, render_template, request, jsonify, session
import requests
import pandas as pd
import os
import re
import json
from urllib.parse import quote

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'  # Change this!

# Configuration
COMPARIFY_API_URL = "https://api.comparify.pro/api/aggregate"
SHOP_NAME = "My Local Shop"
SHOP_CSV_FILE = "shop_prices.csv"

# Nominatim API (OpenStreetMap) - FREE, no API key needed!
NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"

def get_user_location():
    """Get user's location from session or return None"""
    return session.get('user_location')

def set_user_location(location_data):
    """Store user's location in session"""
    session['user_location'] = location_data

def load_shop_prices():
    """Load shop prices from CSV file"""
    if os.path.exists(SHOP_CSV_FILE):
        try:
            df = pd.read_csv(SHOP_CSV_FILE)
            return df.to_dict('records')
        except Exception as e:
            print(f"Error loading shop prices: {e}")
            return []
    return []

def fetch_store_ids_from_location(lat, lng):
    """
    Fetch store IDs based on location
    This is a placeholder - you'll need to implement the actual logic
    based on how Comparify determines store IDs from location
    """
    # For now, return default IDs
    # You may need to call a Comparify endpoint or implement geo-based logic
    return {
        'storeId': '005dcc9a-d50c-442f-ae5e-f89f35d1a01a',
        'instamartStoreId': '1389005',
        'dmartStoreId': '10711'
    }

def extract_pincode_from_address(address_components):
    """Extract pincode from Nominatim address components"""
    return address_components.get('postcode', '122006')

def fetch_comparify_data(query, location_data):
    """Fetch data from Comparify API with dynamic location"""
    try:
        # Get store IDs based on location
        store_ids = fetch_store_ids_from_location(
            location_data['latitude'],
            location_data['longitude']
        )
        
        params = {
            'query': query,
            'storeId': store_ids['storeId'],
            'instamartStoreId': store_ids['instamartStoreId'],
            'dmartStoreId': store_ids['dmartStoreId'],
            'userLocation': json.dumps({
                'latitude': location_data['latitude'],
                'longitude': location_data['longitude']
            }),
            'pincode': location_data.get('pincode', '122006')
        }
        
        print(f"Fetching Comparify data with params: {params}")
        response = requests.get(COMPARIFY_API_URL, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from Comparify: {e}")
        return None

def normalize_product_name(name):
    """Normalize product name for matching"""
    if not name:
        return ""
    name = re.sub(r'\s+', ' ', name.lower().strip())
    name = re.sub(r'\([^)]*\)', '', name)
    name = re.sub(r'\b(kg|g|ml|l|pack|pcs?)\b', '', name)
    return name.strip()

def build_image_url(source, image):
    """Build full image URL based on source-specific patterns"""
    if not image:
        return ""
    
    if isinstance(image, list):
        image = image[0]
    
    if source.lower() == 'instamart' and isinstance(image, str) and image.startswith('NI_CATALOG/IMAGES/'):
        return f"https://media-assets.swiggy.com/swiggy/image/upload/fl_lossy,f_auto,q_auto,w_252,h_272/{image}"
    
    elif source.lower() == 'zepto' and isinstance(image, dict) and 'path' in image:
        path = image['path']
        if path.startswith('cms/'):
            return f"https://cdn.zeptonow.com/production/{path}"
    
    elif isinstance(image, str):
        if not image.startswith('http'):
            if 'dmart' in source.lower() and image.startswith('images/products/'):
                return f"https://cdn.dmart.in/{image}"
            return f"https://via.placeholder.com/200?text=Product"
        return image
    
    return ""

def merge_shop_data(query, comparify_data, shop_data):
    """Merge shop data with Comparify data - GROUP BY PRODUCT"""
    if not comparify_data:
        return None
    
    query_lower = query.lower()
    
    filtered_shop_data = []
    for item in shop_data:
        normalized_item = normalize_product_name(item['product_name'])
        if query_lower in normalized_item or normalized_item in query_lower:
            filtered_shop_data.append(item)
    
    products_map = {}
    
    for source, data in comparify_data.items():
        products = []
        if isinstance(data, list):
            products = data
        elif isinstance(data, dict) and 'products' in data:
            products = data['products']
        
        for product in products:
            name = product.get('name') or product.get('display_name') or product.get('normalizedName', '')
            if not name:
                continue
            
            normalized_name = normalize_product_name(name)
            
            price = product.get('price') or product.get('sellingPrice') or product.get('offer_price')
            if isinstance(price, dict):
                price = price.get('offer_price') or price.get('mrp')
            
            if source.lower() == 'zepto' and price and isinstance(price, (int, float)):
                price = price / 100.0
            elif price and isinstance(price, (int, float)) and price > 1000:
                price = price / 100.0
            
            mrp = product.get('mrp') or product.get('superSaverSellingPrice') or price
            if source.lower() == 'zepto' and mrp and isinstance(mrp, (int, float)):
                mrp = mrp / 100.0
            elif mrp and isinstance(mrp, (int, float)) and mrp > 1000:
                mrp = mrp / 100.0
            
            unit = product.get('unit') or product.get('quantity') or product.get('sku_quantity_with_combo') or product.get('productVariant', {}).get('formattedPacksize', '')
            out_of_stock = product.get('out_of_stock') or product.get('outOfStock') or not product.get('in_stock', True)
            
            raw_image = (product.get('productVariant', {}).get('images', [{}])[0].get('path') if product.get('productVariant') else 
                         product.get('image_url') or product.get('imageUrl') or '')
            
            image_url = build_image_url(source, raw_image)
            
            if 'variations' in product and product['variations']:
                added_variations = set()
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
                    
                    var_images = variation.get('images', [])
                    if var_images and isinstance(var_images, list) and var_images:
                        var_image_raw = var_images[0]
                    else:
                        var_image_raw = raw_image
                    
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
                continue
            
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
    
    result_products = []
    for key, product_data in products_map.items():
        platforms = sorted(product_data['platforms'], 
                          key=lambda x: (not x['in_stock'], x['price'] or float('inf')))
        
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
    
    result_products.sort(key=lambda x: x['cheapest_price'] if x['cheapest_price'] is not None else float('inf'))
    
    return {'products': result_products}

@app.route('/')
def index():
    """Home page"""
    user_location = get_user_location()
    return render_template('index.html', 
                         shop_name=SHOP_NAME,
                         user_location=user_location)

@app.route('/search')
def search():
    """Search endpoint"""
    query = request.args.get('query', '').strip()
    
    if not query:
        return jsonify({'error': 'Query parameter is required'}), 400
    
    # Get user location
    user_location = get_user_location()
    if not user_location:
        return jsonify({'error': 'Location not set. Please select your location first.'}), 400
    
    shop_data = load_shop_prices()
    comparify_data = fetch_comparify_data(query, user_location)
    
    if comparify_data is None:
        return jsonify({'error': 'Failed to fetch data from Comparify'}), 500
    
    merged_data = merge_shop_data(query, comparify_data, shop_data)
    if not merged_data or not merged_data.get('products'):
        return jsonify({'error': 'No data available'}), 404
    
    return jsonify(merged_data)

@app.route('/autocomplete-location')
def autocomplete_location():
    """Autocomplete location using Nominatim (OpenStreetMap)"""
    query = request.args.get('query', '').strip()
    
    if not query or len(query) < 3:
        return jsonify({'suggestions': []})
    
    try:
        # Search locations in India using Nominatim
        params = {
            'q': query,
            'format': 'json',
            'addressdetails': 1,
            'countrycodes': 'in',  # Restrict to India
            'limit': 5
        }
        
        headers = {
            'User-Agent': 'PriceComparisonApp/1.0'  # Required by Nominatim
        }
        
        response = requests.get(NOMINATIM_SEARCH_URL, params=params, headers=headers, timeout=5)
        response.raise_for_status()
        results = response.json()
        
        suggestions = []
        for result in results:
            # Format the address nicely
            address = result.get('display_name', '')
            
            suggestions.append({
                'display_name': address,
                'lat': float(result['lat']),
                'lon': float(result['lon']),
                'place_id': result.get('place_id'),
                'address': result.get('address', {})
            })
        
        return jsonify({'suggestions': suggestions})
        
    except Exception as e:
        print(f"Error fetching location suggestions: {e}")
        return jsonify({'suggestions': []})

@app.route('/set-location', methods=['POST'])
def set_location():
    """Set user location from place selection"""
    try:
        data = request.json
        lat = data.get('lat')
        lon = data.get('lon')
        display_name = data.get('display_name')
        address_data = data.get('address', {})
        
        if not lat or not lon:
            return jsonify({'error': 'Location coordinates are required'}), 400
        
        # Extract pincode from address
        pincode = extract_pincode_from_address(address_data)
        
        # Store location data
        location_data = {
            'latitude': float(lat),
            'longitude': float(lon),
            'address': display_name,
            'pincode': pincode,
            'city': address_data.get('city') or address_data.get('town') or address_data.get('village', ''),
            'state': address_data.get('state', '')
        }
        
        set_user_location(location_data)
        
        return jsonify({
            'success': True,
            'location': location_data
        })
        
    except Exception as e:
        print(f"Error setting location: {e}")
        return jsonify({'error': 'Failed to set location'}), 500

@app.route('/get-location')
def get_location():
    """Get current user location"""
    user_location = get_user_location()
    if user_location:
        return jsonify({'success': True, 'location': user_location})
    return jsonify({'success': False, 'message': 'No location set'})

if __name__ == '__main__':
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
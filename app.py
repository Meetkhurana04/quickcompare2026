# app.py
from flask import Flask, render_template, request, jsonify
import requests
import json
from urllib.parse import quote

app = Flask(__name__)
DEFAULT_LAT = 28.4792711
DEFAULT_LNG = 77.00450409999999
DEFAULT_PIN = 122006
STORE_ID = "607dfe88-5e9b-4db8-bfb0-73bea3e8fb54"
DEFAULT_INSTAMART_STORE_ID = "1389005"
DEFAULT_DMART_STORE_ID = "10711"

@app.route('/')
def index():
    return render_template('index.html')

# NEW ROUTE: Handle store-ids requests from frontend
@app.route('/store-ids', methods=['POST'])
def store_ids():
    data = request.json
    lat = data.get('lat', DEFAULT_LAT)
    lng = data.get('lng', DEFAULT_LNG)
    pincode = data.get('pincode', DEFAULT_PIN)
    
    # Create the userLocation string exactly as expected by external API
    user_location_json = {"latitude": lat, "longitude": lng}
    user_location_str = json.dumps(user_location_json)
    
    # print(f"Store IDs Request - Lat: {lat}, Lng: {lng}, Pincode: {pincode}")
    # print(f"User Location String: {user_location_str}")
    
    # Parameters for external API
    params = {
        'userLocation': user_location_str,
        'provider': 'instamart,zepto,flipkart-minutes,dmart,jiomart',
        'pincode': pincode
    }
    
    try:
        # print("Making request to external store-ids API...")
        resp = requests.get("https://api.comparify.pro/api/store-ids", params=params)
        # print(f"External API Status: {resp.status_code}")
        
        if resp.status_code == 200:
            store_data = resp.json()
            # print(f"External API Response: {store_data}")
            return jsonify(store_data)
        else:
            # print(f"External API Error: {resp.status_code} - {resp.text}")
            return jsonify({"error": "Failed to fetch store IDs"}), resp.status_code
            
    except Exception as e:
        print(f"Error in store-ids route: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/autocomplete', methods=['POST'])
def autocomplete():
    data = request.json
    search_word = data.get('searchWord')
    loc = data.get('location', {})
    lat = loc.get('lat', DEFAULT_LAT)
    lng = loc.get('lng', DEFAULT_LNG)
    payload = {
        "searchWord": search_word,
        "location": {"lat": lat, "lng": lng}
    }
    resp = requests.post("https://api.comparify.pro/api/location-autocomplete", json=payload)
    return resp.json()

@app.route('/geocode', methods=['POST'])
def geocode():
    data = request.json
    place = data.get('place')
    if not place:
        return jsonify({"error": "No place provided"})
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': place,
        'format': 'json',
        'limit': 1
    }
    headers = {'User-Agent': 'PriceCompareApp/1.0'}
    resp = requests.get(url, params=params, headers=headers)
    results = resp.json()
    if results:
        loc = results[0]
        addr = loc.get('address', {})
        postcode = addr.get('postcode', '')
        return jsonify({
            "lat": float(loc['lat']),
            "lng": float(loc['lon']),
            "postcode": postcode,
            "display_name": loc['display_name']
        })
    return jsonify({"error": "Place not found"})

@app.route('/aggregate', methods=['POST'])
def aggregate():
    data = request.json
    query = data.get('query')
    lat = data.get('lat', DEFAULT_LAT)
    lng = data.get('lng', DEFAULT_LNG)
    pincode = data.get('pincode', DEFAULT_PIN)
    
    user_location_json = {"latitude": lat, "longitude": lng}
    user_location_str = json.dumps(user_location_json)
    
    # Fetch store IDs
    store_params = {
        'userLocation': user_location_str,
        'provider': 'instamart,zepto,flipkart-minutes,dmart,jiomart',
        'pincode': pincode
    }
    
    try:
        store_resp = requests.get("https://api.comparify.pro/api/store-ids", params=store_params)
        store_data = store_resp.json()
        
        instamart_store_id = store_data.get('instamart', {}).get('storeId', DEFAULT_INSTAMART_STORE_ID)
        dmart_store_id = store_data.get('dmart', {}).get('storeId', DEFAULT_DMART_STORE_ID)
        zepto_store_id = store_data.get('zepto', {}).get('storeId')
        
        # Extract JioMart and other data
        jiomart_jsc = store_data.get('jiomart', {}).get('jsc')
        jiomart_jrc = store_data.get('jiomart', {}).get('jrc')
        
    except Exception as e:
        print(f"Error fetching store IDs: {e}")
        instamart_store_id = DEFAULT_INSTAMART_STORE_ID
        dmart_store_id = DEFAULT_DMART_STORE_ID
        zepto_store_id = None
        jiomart_jsc = None
        jiomart_jrc = None
    
    # Prepare params
    params = {
        'query': query,
        'storeId': zepto_store_id or STORE_ID,  # Use Zepto store ID
        'instamartStoreId': instamart_store_id,
        'dmartStoreId': dmart_store_id,
        'userLocation': user_location_str,
        'pincode': pincode
    }
    
    # ✅ ADD HEADERS - This is what's missing!
    headers = {
        'x-web': 'true',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    # Add DMart header
    if dmart_store_id:
        headers['x-dms'] = str(dmart_store_id)
    
    # Add JioMart headers
    if jiomart_jsc and jiomart_jrc:
        headers['x-jsc'] = jiomart_jsc
        headers['x-jrc'] = jiomart_jrc
    
    # print(f"Aggregate params: {params}")
    # print(f"Aggregate headers: {headers}")
    
    # Make request WITH headers
    resp = requests.get("https://api.comparify.pro/api/aggregate", 
                       params=params, 
                       headers=headers)
    
    result = resp.json()
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True)

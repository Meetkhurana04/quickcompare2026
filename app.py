# app.py
from flask import Flask, render_template, request, jsonify
import requests
import json
from urllib.parse import quote
import os
import traceback

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

@app.route('/store-ids', methods=['POST'])
def store_ids():
    try:
        data = request.json
        lat = data.get('lat', DEFAULT_LAT)
        lng = data.get('lng', DEFAULT_LNG)
        pincode = data.get('pincode', DEFAULT_PIN)
        
        user_location_json = {"latitude": lat, "longitude": lng}
        user_location_str = json.dumps(user_location_json)
        
        params = {
            'userLocation': user_location_str,
            'provider': 'instamart,zepto,flipkart-minutes,dmart,jiomart',
            'pincode': pincode
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        resp = requests.get(
            "https://api.comparify.pro/api/store-ids", 
            params=params, 
            headers=headers,
            timeout=15
        )
        
        if resp.status_code == 200 and 'application/json' in resp.headers.get('Content-Type', ''):
            return jsonify(resp.json())
        else:
            print(f"[STORE-IDS] Error: {resp.status_code} - {resp.text[:200]}")
            return jsonify({"error": "Failed to fetch store IDs"}), 500
            
    except Exception as e:
        print(f"[STORE-IDS] ERROR: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/autocomplete', methods=['POST'])
def autocomplete():
    try:
        data = request.json
        search_word = data.get('searchWord')
        loc = data.get('location', {})
        lat = loc.get('lat', DEFAULT_LAT)
        lng = loc.get('lng', DEFAULT_LNG)
        
        payload = {
            "searchWord": search_word,
            "location": {"lat": lat, "lng": lng}
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        print(f"[AUTOCOMPLETE] Payload: {payload}")
        
        resp = requests.post(
            "https://api.comparify.pro/api/location-autocomplete", 
            json=payload,
            headers=headers,
            timeout=10
        )
        
        print(f"[AUTOCOMPLETE] Status: {resp.status_code}, Content-Type: {resp.headers.get('Content-Type')}")
        print(f"[AUTOCOMPLETE] Response preview: {resp.text[:300]}")
        
        if resp.status_code != 200:
            return jsonify({"error": f"API error {resp.status_code}", "data": []}), 200
        
        content_type = resp.headers.get('Content-Type', '')
        if 'application/json' not in content_type:
            print(f"[AUTOCOMPLETE] Non-JSON response: {resp.text}")
            return jsonify({"error": "Invalid API response", "data": []}), 200
        
        try:
            return jsonify(resp.json())
        except ValueError:
            print(f"[AUTOCOMPLETE] JSON parse error. Text: {resp.text}")
            return jsonify({"error": "Invalid JSON", "data": []}), 200
        
    except requests.exceptions.Timeout:
        print("[AUTOCOMPLETE] Timeout")
        return jsonify({"error": "Timeout", "data": []}), 200
    except Exception as e:
        print(f"[AUTOCOMPLETE] ERROR: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e), "data": []}), 200

@app.route('/geocode', methods=['POST'])
def geocode():
    try:
        data = request.json
        place = data.get('place')
        if not place:
            return jsonify({"error": "No place provided"}), 400
            
        url = "https://nominatim.openstreetmap.org/search"
        params = {'q': place, 'format': 'json', 'limit': 1}
        headers = {'User-Agent': 'PriceCompareApp/1.0'}
        
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        
        if resp.status_code != 200:
            return jsonify({"error": "Geocoding failed"}), 500
            
        results = resp.json()
        if results:
            loc = results[0]
            addr = loc.get('address', {})
            return jsonify({
                "lat": float(loc['lat']),
                "lng": float(loc['lon']),
                "postcode": addr.get('postcode', ''),
                "display_name": loc['display_name']
            })
        return jsonify({"error": "Place not found"}), 404
        
    except Exception as e:
        print(f"[GEOCODE] ERROR: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/aggregate', methods=['POST'])
def aggregate():
    try:
        data = request.json
        query = data.get('query')
        lat = data.get('lat', DEFAULT_LAT)
        lng = data.get('lng', DEFAULT_LNG)
        pincode = data.get('pincode', DEFAULT_PIN)
        
        user_location_json = {"latitude": lat, "longitude": lng}
        user_location_str = json.dumps(user_location_json)
        
        # Get store IDs
        store_params = {
            'userLocation': user_location_str,
            'provider': 'instamart,zepto,flipkart-minutes,dmart,jiomart',
            'pincode': pincode
        }
        
        try:
            store_resp = requests.get(
                "https://api.comparify.pro/api/store-ids",
                params=store_params,
                headers={'User-Agent': 'Mozilla/5.0'},
                timeout=15
            )
            store_data = store_resp.json() if store_resp.status_code == 200 else {}
            
            instamart_store_id = store_data.get('instamart', {}).get('storeId', DEFAULT_INSTAMART_STORE_ID)
            dmart_store_id = store_data.get('dmart', {}).get('storeId', DEFAULT_DMART_STORE_ID)
            zepto_store_id = store_data.get('zepto', {}).get('storeId')
            jiomart_jsc = store_data.get('jiomart', {}).get('jsc')
            jiomart_jrc = store_data.get('jiomart', {}).get('jrc')
            
        except:
            instamart_store_id = DEFAULT_INSTAMART_STORE_ID
            dmart_store_id = DEFAULT_DMART_STORE_ID
            zepto_store_id = None
            jiomart_jsc = None
            jiomart_jrc = None
        
        params = {
            'query': query,
            'storeId': zepto_store_id or STORE_ID,
            'instamartStoreId': instamart_store_id,
            'dmartStoreId': dmart_store_id,
            'userLocation': user_location_str,
            'pincode': pincode
        }
        
        headers = {
            'x-web': 'true',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        if dmart_store_id:
            headers['x-dms'] = str(dmart_store_id)
        if jiomart_jsc and jiomart_jrc:
            headers['x-jsc'] = jiomart_jsc
            headers['x-jrc'] = jiomart_jrc
        
        resp = requests.get(
            "https://api.comparify.pro/api/aggregate",
            params=params,
            headers=headers,
            timeout=30
        )
        
        if resp.status_code == 200:
            return jsonify(resp.json())
        else:
            print(f"[AGGREGATE] Error: {resp.status_code}")
            return jsonify({"error": "Search failed"}), 500
            
    except Exception as e:
        print(f"[AGGREGATE] ERROR: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG', 'False') == 'True'
    app.run(debug=debug_mode)
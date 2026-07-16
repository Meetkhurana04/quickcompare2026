from flask import Flask, render_template, request, Response
import requests

app = Flask(__name__)

API_BASE = 'https://api.quickcommerceapi.com'
API_KEY = '396cbef2-2fc2-4b91-8308-721687262e2f'
HEADERS = {'X-API-Key': API_KEY}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/groupsearch')
def proxy_groupsearch():
    q = request.args.get('q')
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    platforms = request.args.get('platforms')
    pincode = request.args.get('pincode')

    url = f'{API_BASE}/v1/groupsearch?q={q}&lat={lat}&lon={lon}&platforms={platforms}'
    if pincode:
        url += f'&pincode={pincode}'

    resp = requests.get(url, headers=HEADERS, timeout=25)
    return Response(resp.content, resp.status_code, {'Content-Type': 'application/json'})

@app.route('/api/search')
def proxy_search():
    q = request.args.get('q')
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    platform = request.args.get('platform')
    pincode = request.args.get('pincode')

    url = f'{API_BASE}/v1/search?q={q}&lat={lat}&lon={lon}&platform={platform}'
    if pincode:
        url += f'&pincode={pincode}'

    resp = requests.get(url, headers=HEADERS, timeout=25)
    return Response(resp.content, resp.status_code, {'Content-Type': 'application/json'})

@app.route('/api/credits')
def proxy_credits():
    resp = requests.get(f'{API_BASE}/v1/credits', headers=HEADERS, timeout=10)
    return Response(resp.content, resp.status_code, {'Content-Type': 'application/json'})

if __name__ == '__main__':
    app.run(debug=True)

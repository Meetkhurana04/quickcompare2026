# QuickCompare - Project Context

## Purpose
Price comparison SPA for Indian quick-commerce (Blinkit, Instamart, Zepto, BigBasket, Flipkart Minutes, JioMart, DMart). Users search products, see prices across platforms, and local shop owners can merge their CSV prices.

---

## Architecture

```
Browser (index.html) --fetch()--> Cloudflare Worker (api.meetwillstudy.workers.dev) --proxy--> Comparify.pro API
  |
  +-- Flask (app.py) -- serves index.html only (10 lines, literally just render_template)
  +-- shop_prices.csv -- local shop data (63 products, currently UNUSED in code)
```

**Critical:** The entire app logic lives in `templates/index.html` (1743 lines, all inline). Flask is just a static file server.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python Flask 3.0.0 (vestigial) |
| Frontend | Vanilla HTML/CSS/JS (no framework) |
| Icons | Font Awesome 6.5.0 (CDN) |
| HTTP | Native browser `fetch()` |
| Data | Cloudflare Worker API + CSV |

---

## API Contracts (Cloudflare Worker)

**Base URL:** `https://api.meetwillstudy.workers.dev` (line 1132)
**All requests:** POST, `Content-Type: application/json`

### 1. `/autocomplete` (line 1239)
**Purpose:** Location search dropdown

**Request:**
```json
{ "searchWord": "gurugram", "location": { "lat": 28.47, "lng": 77.0 } }
```

**Response:**
```json
{ "data": [{ "description": "Gurugram, Haryana, India", "name": "Gurugram" }] }
```

**Used by:** `showLocationSuggestions()` renders suggestion items.

---

### 2. `/geocode` (line 1272)
**Purpose:** Convert selected place to lat/lng/pincode

**Request:**
```json
{ "place": "Gurugram, Haryana, India" }
```

**Response:**
```json
{ "lat": 28.47, "lng": 77.0, "postcode": "122006" }
```

**Error response:**
```json
{ "error": "..." }
```

**Used by:** `selectLocation()` saves to localStorage, triggers `updateStoreIds()`.

---

### 3. `/store-ids` (line 1310)
**Purpose:** Get store-specific IDs for a location

**Request:**
```json
{ "lat": 28.47, "lng": 77.0, "pincode": "122006" }
```

**Response:**
```json
{
  "instamart": { "storeId": "1389005" },
  "dmart": { "storeId": "10711" },
  "zepto": { "storeId": "607dfe88-..." },
  "jiomart": { "pincode": "122006" }
}
```

**Used by:** `updateStoreIds()` populates `currentStoreIds` global.

---

### 4. `/aggregate` (line 1351) — **MAIN endpoint**
**Purpose:** Search products across all platforms

**Request:**
```json
{
  "query": "atta",
  "lat": 28.47,
  "lng": 77.0,
  "pincode": "122006",
  "storeId": "607dfe88-...",
  "instamartStoreId": "1389005",
  "dmartStoreId": "10711",
  "jiomart": { "pincode": "122006" }
}
```

**Response shape** (each platform key is optional):
```json
{
  "blinkit": {
    "products": [{ "name": "...", "brand": "...", "unit": "...", "price": 235, "image_url": "...", "inventory": 10, "product_id": "..." }]
  },
  "instamart": {
    "products": [{
      "display_name": "...", "brand": "...", "product_id": "...",
      "variations": [{ "quantity": "5 kg", "price": { "offer_price": 235, "mrp": 250 }, "images": ["image_id"], "inventory": { "in_stock": true } }]
    }]
  },
  "zepto": [{
    "product": { "name": "..." },
    "productVariant": { "id": "...", "formattedPacksize": "5 kg", "images": [{ "path": "..." }] },
    "sellingPrice": 23500,
    "superSaverSellingPrice": 22500,
    "outOfStock": false
  }],
  "bigbasket": {
    "products": [{ "name": "...", "brand": "...", "unit": "...", "price": 235, "mrp": 250, "image_url": "...", "out_of_stock": false, "url": "...", "variants": [...] }]
  },
  "flipkart-minutes": [{
    "name": "...", "brand": "...", "quantity": "5 kg", "price": { "offerPrice": 235, "mrp": 250 }, "imageUrl": "...", "out_of_stock": false, "url": "..."
  }],
  "jiomart": {
    "products": [{ "name": "...", "brand": "...", "unit": "...", "price": 235, "image_url": "...", "url": "...", "variants": [...] }]
  },
  "dmart": {
    "products": [{ "name": "...", "brand": "...", "unit": "...", "price": 235, "mrp": 250, "image_url": "...", "out_of_stock": false, "url": "...", "variants": [...] }]
  }
}
```

**Used by:** `displayResults()` → `groupProducts()` → `renderProductCards()`

---

## Data Flow

```
User types location → /autocomplete → showLocationSuggestions()
User selects location → /geocode → saveLocation() → /store-ids → updateStoreIds()
User searches product → /aggregate → displayResults()
                                    ↓
                          normalize each platform's data into uniform `allProducts[]`
                                    ↓
                          groupProducts() — groups by brand+product signature
                                    ↓
                          renderProductCards() — renders HTML cards grouped by unit size
```

---

## Key State Variables (Global JS, lines 1164-1173)

| Variable | Type | Default | Source |
|---|---|---|---|
| `API_BASE` | string | `https://api.meetwillstudy.workers.dev` | Hardcoded |
| `currentLat` | number | `28.4792711` | localStorage / geocode |
| `currentLng` | number | `77.00450409999999` | localStorage / geocode |
| `currentPin` | number | `122006` | localStorage / geocode |
| `currentStoreIds` | object | `{ instamart: '1389005', dmart: '10711', zepto: null, jiomart: {} }` | /store-ids |
| `locationSelected` | bool | `false` | After geocode succeeds |

localStorage key: `quickcompare_location` (stores `{ name, lat, lng, pin, timestamp }`)

---

## Rendering Logic

**`displayResults(data)`** (line 1385):
- Extracts products from each platform key
- Normalizes into uniform `{ source, name, brand, unit, price, mrp, image_url, out_of_stock, url }`
- Calls `groupProducts()` then `renderProductCards()`

**`groupProducts(products)`** (line 1566):
- Groups by `extractProductSignature(brand, name)` → signature string
- Each product grouped under its signature
- Display name = longest name in the group

**`renderProductCards(groups)`** (line 1642):
- Sorts groups by number of sources (most platforms first)
- Within each group: sorts by unit size, then by price
- Marks cheapest variant with crown emoji 👑
- Generates full HTML template

---

## Platform-Specific URL & Image Patterns

| Platform | Product URL Pattern | Image URL Pattern |
|---|---|---|
| Blinkit | `https://blinkit.com/prn/x/prid/{product_id}` | Direct from API |
| Instamart | `https://www.swiggy.com/instamart/item/{product_id}` | `https://media-assets.swiggy.com/swiggy/image/upload/fl_lossy,f_auto,q_auto,w_252,h_272/{image_id}` |
| Zepto | `https://www.zepto.com/pn/x/pvid/{productVariant.id}` | `https://cdn.zeptonow.com/production/tr:w-400,ar-1000-1000,pr-true,f-auto,q-80/{path}` |
| BigBasket | From API response | From API response |
| Flipkart Minutes | From API response | From API response |
| JioMart | From API response | From API response |
| DMart | From API response | From API response |

---

## Files to Touch for API Replacement

| File | What's there | Why change |
|---|---|---|
| `templates/index.html` | All 4 API calls + rendering logic | Replace endpoint URL + possibly request/response shapes |
| `app.py` | Flask server (probably fine) | May need to add CORS or proxy if new API has restrictions |
| `shop_prices.csv` | 63 products, unused | May want to implement the merge feature |
| `README.md` | Documentation | Update API references |
| `CONTEXT.md` | This file | Keep updated |

---

## What Needs Minimal Change (if new API is similar)

1. **`API_BASE`** constant (line 1132) — change the URL
2. **Request bodies** (4 endpoints) — adjust field names if different
3. **Response parsing** in `displayResults()` (lines 1385-1560) — adjust if response shape differs
4. **Error handling** — test each endpoint

---

## Important Notes

- No auth/API keys needed (public Cloudflare Worker)
- No pagination in current API implementation
- Location persisted in localStorage
- CSV merge feature is documented but **not implemented**
- The `requirements.txt` includes pandas/numpy/requests but they are **not used** in current `app.py`

# Price Compare - Comparify Wrapper

A Flask web application that wraps Comparify.pro's backend API and allows you to add your own shop's prices to the comparison.

## Features

- 🔍 Search grocery items across multiple platforms (Blinkit, Instamart, Zepto, BigBasket, DMart, JioMart, etc.)
- 🏪 Add your own shop's prices to compete
- 💰 Real-time price comparison
- 📱 Beautiful, responsive UI
- 📊 Easy CSV-based price management

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Your Shop

Edit `app.py` to set your shop name:

```python
SHOP_NAME = "My Local Shop"  # Change this to your shop name
```

### 3. Add Your Product Prices

Edit `shop_prices.csv` with your product prices. The CSV format is:

```csv
product_name,price,unit,in_stock
Aashirvaad Atta 5kg,235,5 kg,True
Fortune Atta 5kg,210,5 kg,True
```

**Important Notes:**
- `product_name`: Name of the product (try to match Comparify's naming)
- `price`: Price in rupees (e.g., 235 for ₹235)
- `unit`: Unit like "5 kg", "1 kg", "500 g"
- `in_stock`: True or False

### 4. Run the Application

```bash
python app.py
```

The app will start at `http://localhost:5000`

## How It Works

1. **User searches** for a product (e.g., "atta")
2. **App fetches** data from Comparify API
3. **App merges** your shop's prices from CSV
4. **Results displayed** with all stores including yours
5. **Your shop appears first** with a special badge

## CSV Matching Logic

The app uses fuzzy matching to match your products with Comparify's results:
- If your CSV has "Aashirvaad Atta 5kg" 
- And Comparify returns "Aashirvaad Shudh Chakki Atta (5 kg)"
- The app will match them and show your price

## Customization

### Change Location

Edit these variables in `app.py`:

```python
DEFAULT_LOCATION = {"latitude": 28.4838282, "longitude": 77.00285219999999}
DEFAULT_PINCODE = "122006"
```

### Change Store IDs

The following IDs are location-specific (currently set for Gurugram 122006):

```python
DEFAULT_STORE_ID = "005dcc9a-d50c-442f-ae5e-f89f35d1a01a"  # Blinkit
DEFAULT_INSTAMART_STORE_ID = "1389005"  # Swiggy Instamart
DEFAULT_DMART_STORE_ID = "10711"  # DMart
```

To get store IDs for your location:
1. Go to comparify.pro
2. Set your location
3. Open browser DevTools > Network tab
4. Search for a product
5. Look at the API request parameters

## Tips for Better Results

1. **Product Naming**: Use common product names in your CSV
   - ✅ "Aashirvaad Atta 5kg"
   - ✅ "Fortune Rice 5kg"
   - ❌ "AA-ATT-5" (too cryptic)

2. **Keep Prices Updated**: Update your CSV regularly to stay competitive

3. **Mark Out of Stock**: Set `in_stock` to `False` when products are unavailable

4. **Units Matter**: Match the unit format (5 kg, 1 L, 500 g)

## API Endpoint

The app exposes a `/search` endpoint:

```
GET /search?query=atta
```

Returns JSON with all stores and products.

## Tech Stack

- **Backend**: Flask (Python)
- **Frontend**: HTML, TailwindCSS, Vanilla JavaScript
- **Data**: Pandas for CSV handling
- **API**: Comparify.pro backend

## Folder Structure

```
fina-comparify/
├── app.py              # Flask application
├── shop_prices.csv     # Your shop's prices
├── requirements.txt    # Python dependencies
├── README.md          # This file
└── templates/
    └── index.html     # Frontend UI
```

## Troubleshooting

### Products Not Matching?
- Check product names in CSV match Comparify's naming
- Use broader names (e.g., "Atta" instead of specific brand variants)

### API Errors?
- Check your internet connection
- Verify Comparify API is accessible
- Try different search terms

### No Results?
- Make sure CSV file exists and is properly formatted
- Check CSV for typos in product names
- Verify prices are numbers without currency symbols

## Future Enhancements

- [ ] Admin panel to edit prices
- [ ] Database instead of CSV
- [ ] Image upload for products
- [ ] Multi-location support
- [ ] Price history tracking
- [ ] Email alerts for price drops

## License

Free to use for personal and commercial purposes.

## Support

For issues or questions, check the console logs:
- Browser console for frontend errors
- Terminal/CMD for backend errors

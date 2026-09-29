import os
import sqlite3
import secrets
from functools import wraps
from datetime import datetime
import urllib.parse
import urllib.request
import json
from dotenv import load_dotenv

load_dotenv()

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, g
)
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db, init_db, sync_admin_credentials

app = Flask(__name__)
# Generate secure secret key from environment or cryptographically secure token
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_hex(32)

# Ensure database schema is initialized safely on startup without destroying existing data
init_db(force_reset=False)

INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
    "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
    "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Delhi", "Jammu and Kashmir", "Ladakh"
]

INDIAN_AGRI_CITIES = {
    "ludhiana": {"name": "Ludhiana (Punjab)", "lat": 30.9010, "lon": 75.8573, "region": "North Cereal Belt"},
    "karnal": {"name": "Karnal (Haryana)", "lat": 29.6857, "lon": 76.9905, "region": "Wheat-Paddy Belt"},
    "nashik": {"name": "Nashik (Maharashtra)", "lat": 19.9975, "lon": 73.7898, "region": "Onion & Grape Hub"},
    "varanasi": {"name": "Varanasi (Uttar Pradesh)", "lat": 25.3176, "lon": 82.9739, "region": "Gangetic Alluvial Basin"},
    "indore": {"name": "Indore (Madhya Pradesh)", "lat": 22.7196, "lon": 75.8577, "region": "Soybean & Wheat Plateau"},
    "guntur": {"name": "Guntur (Andhra Pradesh)", "lat": 16.3067, "lon": 80.4365, "region": "Chilli & Cotton Belt"},
    "surat": {"name": "Surat (Gujarat)", "lat": 21.1702, "lon": 72.8311, "region": "Sugarcane & Horticulture"},
    "coimbatore": {"name": "Coimbatore (Tamil Nadu)", "lat": 11.0168, "lon": 76.9558, "region": "South Cotton & Coconut"},
    "patna": {"name": "Patna (Bihar)", "lat": 25.5941, "lon": 85.1376, "region": "Maize & Paddy Zone"},
    "bardhaman": {"name": "Bardhaman (West Bengal)", "lat": 23.2324, "lon": 87.8615, "region": "Rice Bowl of Bengal"},
    "kota": {"name": "Kota (Rajasthan)", "lat": 25.2138, "lon": 75.8648, "region": "Mustard & Soybean Zone"},
    "shimla": {"name": "Shimla (Himachal Pradesh)", "lat": 31.1048, "lon": 77.1734, "region": "Apple & Temperate Fruits"}
}

SAMPLE_MANDI_PRICES = [
    {"crop": "Wheat (Sharbati)", "mandi": "Khanna Mandi, Punjab", "price": 2425, "unit": "₹ / Quintal", "trend": "up", "change": "+₹35"},
    {"crop": "Paddy (Basmati 1121)", "mandi": "Karnal Mandi, Haryana", "price": 3850, "unit": "₹ / Quintal", "trend": "up", "change": "+₹60"},
    {"crop": "Mustard (Sarson)", "mandi": "Kota APMC, Rajasthan", "price": 5650, "unit": "₹ / Quintal", "trend": "down", "change": "-₹25"},
    {"crop": "Cotton (Medium Staple)", "mandi": "Rajkot APMC, Gujarat", "price": 7120, "unit": "₹ / Quintal", "trend": "up", "change": "+₹90"},
    {"crop": "Soybean (Yellow)", "mandi": "Indore Mandi, MP", "price": 4680, "unit": "₹ / Quintal", "trend": "stable", "change": "₹0"},
    {"crop": "Tomato (Hybrid)", "mandi": "Nashik Mandi, Maharashtra", "price": 1850, "unit": "₹ / Quintal", "trend": "down", "change": "-₹70"},
    {"crop": "Potato (Jyoti)", "mandi": "Agra APMC, Uttar Pradesh", "price": 1340, "unit": "₹ / Quintal", "trend": "up", "change": "+₹40"},
    {"crop": "Red Chilli (Teja)", "mandi": "Guntur Yard, Andhra Pradesh", "price": 18500, "unit": "₹ / Quintal", "trend": "up", "change": "+₹250"},
    {"crop": "Gram / Chana", "mandi": "Latur APMC, Maharashtra", "price": 5980, "unit": "₹ / Quintal", "trend": "stable", "change": "+₹10"}
]

DATA_GOV_MANDI_API = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"


def get_mandi_prices(limit=10, state=None):
    """
    Fetch daily mandi prices from the Government of India's
    data.gov.in API.
    """

    api_key = os.environ.get("DATA_GOV_API_KEY")

    if not api_key:
        return (
            SAMPLE_MANDI_PRICES,
            False,
            "Government mandi API key is not configured. Showing demonstration data."
        )

    try:
        params = {
            "api-key": api_key,
            "format": "json",
            "limit": limit,
            "offset": 0
        }

        if state:
            params["filters[state.keyword]"] = state

        url = DATA_GOV_MANDI_API + "?" + urllib.parse.urlencode(params)

        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "Shram-setuu/1.0"
            }
        )

        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))

        records = data.get("records", [])

        if not records:
            return (
                SAMPLE_MANDI_PRICES,
                False,
                "No mandi records found for the selected state."
            )

        prices = []

        for record in records:
            prices.append({
                "crop": record.get("commodity", "Unknown Commodity"),
                "variety": record.get("variety", ""),
                "mandi": record.get("market", "Unknown Market"),
                "state": record.get("state", ""),
                "district": record.get("district", ""),
                "grade": record.get("grade", ""),
                "arrival_date": record.get("arrival_date", ""),
                "min_price": record.get("min_price", 0),
                "max_price": record.get("max_price", 0),
                "price": record.get("modal_price", 0),
                "unit": "₹ / Quintal"
            })

        return (
            prices,
            True,
            "Government of India mandi data"
        )

    except Exception as e:
        print(f"Mandi API error: {e}")

        return (
            SAMPLE_MANDI_PRICES,
            False,
            "Government mandi API temporarily unavailable. Showing demonstration data."
        )
def is_safe_url(target):
    """Validates that a redirect URL is local and safe against open redirect vulnerabilities."""
    if not target:
        return False
    ref_url = urllib.parse.urlparse(request.host_url)
    test_url = urllib.parse.urlparse(urllib.parse.urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc and target.startswith('/') and not target.startswith('//')

@app.before_request
def setup_security_and_user():
    # 1. Ensure CSRF session token exists
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)

    # 2. Check CSRF on mutating requests
    if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
        if not app.config.get('TESTING') and not app.config.get('CSRF_DISABLED'):
            submitted_token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
            if not submitted_token and request.is_json:
                submitted_token = (request.get_json(silent=True) or {}).get('csrf_token')
            
            if not submitted_token or submitted_token != session.get('csrf_token'):
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
                    return jsonify({'status': 'error', 'message': 'CSRF validation failed. Please refresh the page.'}), 400
                flash('Security check failed. Please submit the form again.', 'danger')
                return redirect(request.referrer or url_for('index'))

    # 3. Load logged-in user into flask.g
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
        g.user = user

@app.context_processor
def inject_global_vars():
    user_id = session.get('user_id')
    bookmarked_ids = set()
    if user_id:
        conn = get_db()
        b_rows = conn.execute("SELECT resource_id FROM bookmarks WHERE user_id = ?", (user_id,)).fetchall()
        bookmarked_ids = {row['resource_id'] for row in b_rows}
        conn.close()

    return {
        'current_user': g.user,
        'bookmarked_ids': bookmarked_ids,
        'indian_states': INDIAN_STATES,
        'now_year': datetime.now().year,
        'csrf_token': session.get('csrf_token', '')
    }

@app.template_filter('format_date')
def format_date_filter(value):
    """Formats date/datetime strings to a readable format like '31 Aug 2026'."""
    if not value:
        return ''
    try:
        val_str = str(value).strip()
        if 'T' in val_str:
            dt = datetime.fromisoformat(val_str.replace('Z', '+00:00'))
        elif len(val_str) >= 19:
            dt = datetime.strptime(val_str[:19], "%Y-%m-%d %H:%M:%S")
        elif len(val_str) >= 10:
            dt = datetime.strptime(val_str[:10], "%Y-%m-%d")
        else:
            return val_str
        return dt.strftime("%d %b %Y")
    except Exception:
        return str(value)[:10]

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user is None:
            flash('Please log in to access this feature.', 'warning')
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user is None:
            flash('Please log in with administrator privileges.', 'warning')
            return redirect(url_for('login', next=request.path))
        if g.user['role'] != 'admin':
            flash('Access denied. Administrator privileges required.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def get_resource_ratings(conn):
    ratings_query = conn.execute("""
    SELECT resource_id, AVG(rating) as avg_rating, COUNT(id) as total_ratings
    FROM feedback
    GROUP BY resource_id
    """).fetchall()
    return {row['resource_id']: {'avg': round(row['avg_rating'], 1), 'count': row['total_ratings']} for row in ratings_query}

# --- ERROR HANDLERS ---

@app.errorhandler(400)
def handle_bad_request(e):
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'status': 'error', 'message': 'Bad Request / Invalid Parameters'}), 400
    flash('Bad Request. Please check your input parameters.', 'warning')
    return redirect(url_for('index'))

@app.errorhandler(404)
def handle_not_found(e):
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'status': 'error', 'message': 'Requested item not found'}), 404
    flash('The requested page or resource could not be found.', 'warning')
    return redirect(url_for('index'))

@app.errorhandler(500)
def handle_server_error(e):
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'status': 'error', 'message': 'Internal Server Error'}), 500
    flash('An unexpected error occurred. Please try again.', 'danger')
    return redirect(url_for('index'))

# --- PUBLIC ROUTES ---

@app.route('/')
def index():
    conn = get_db()
    stats = {
        'resources': conn.execute("SELECT COUNT(*) FROM resources").fetchone()[0],
        'schemes': conn.execute("SELECT COUNT(*) FROM resources WHERE resource_type = 'scheme'").fetchone()[0],
        'crops': conn.execute("SELECT COUNT(*) FROM resources WHERE resource_type = 'crop'").fetchone()[0],
        'tools': conn.execute("SELECT COUNT(*) FROM resources WHERE resource_type = 'tool'").fetchone()[0],
        'guides': conn.execute("SELECT COUNT(*) FROM resources WHERE resource_type = 'guide'").fetchone()[0],
        'categories': conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0],
        'farmers': conn.execute("SELECT COUNT(*) FROM users WHERE role = 'user'").fetchone()[0]
    }

    featured_schemes = conn.execute("""
    SELECT * FROM resources WHERE resource_type = 'scheme' ORDER BY views_count DESC LIMIT 3
    """).fetchall()

    featured_crops = conn.execute("""
    SELECT * FROM resources WHERE resource_type = 'crop' ORDER BY views_count DESC LIMIT 4
    """).fetchall()

    featured_guides = conn.execute("""
    SELECT * FROM resources WHERE resource_type = 'guide' ORDER BY views_count DESC LIMIT 3
    """).fetchall()

    ratings_map = get_resource_ratings(conn)
    conn.close()

    return render_template(
        'index.html',
        stats=stats,
        featured_schemes=featured_schemes,
        featured_crops=featured_crops,
        featured_guides=featured_guides,
        ratings_map=ratings_map
    )

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    user_id = g.user['id']
    user_cat = g.user['preferred_category'] or 'General'

    counts = {
        'saved': conn.execute("SELECT COUNT(*) FROM bookmarks WHERE user_id = ?", (user_id,)).fetchone()[0],
        'schemes': conn.execute("SELECT COUNT(*) FROM resources WHERE resource_type = 'scheme'").fetchone()[0],
        'crops': conn.execute("SELECT COUNT(*) FROM resources WHERE resource_type = 'crop'").fetchone()[0],
        'guides': conn.execute("SELECT COUNT(*) FROM resources WHERE resource_type = 'guide'").fetchone()[0],
        'discussions': conn.execute("SELECT COUNT(*) FROM community_posts").fetchone()[0]
    }

    if user_cat and user_cat != 'General':
        recommended = conn.execute("""
        SELECT * FROM resources WHERE category_name LIKE ? OR resource_type LIKE ?
        ORDER BY views_count DESC LIMIT 6
        """, (f"%{user_cat}%", f"%{user_cat}%")).fetchall()
    else:
        recommended = conn.execute("""
        SELECT * FROM resources ORDER BY views_count DESC LIMIT 6
        """).fetchall()

    saved_items = conn.execute("""
    SELECT r.*, b.created_at as bookmarked_date
    FROM bookmarks b
    JOIN resources r ON b.resource_id = r.id
    WHERE b.user_id = ?
    ORDER BY b.created_at DESC LIMIT 4
    """, (user_id,)).fetchall()

    recent_posts = conn.execute("""
    SELECT p.*, u.full_name as author_name,
           (SELECT COUNT(*) FROM comments WHERE post_id = p.id) as comment_count
    FROM community_posts p
    JOIN users u ON p.user_id = u.id
    ORDER BY p.created_at DESC LIMIT 3
    """).fetchall()

    ratings_map = get_resource_ratings(conn)
    conn.close()

    return render_template(
        'dashboard.html',
        counts=counts,
        recommended=recommended,
        saved_items=saved_items,
        recent_posts=recent_posts,
        ratings_map=ratings_map
    )

@app.route('/crops')
def crops():
    category_filter = request.args.get('cat', 'All')
    search_query = request.args.get('q', '').strip()

    conn = get_db()
    query = "SELECT * FROM resources WHERE resource_type = 'crop'"
    params = []

    if category_filter and category_filter != 'All':
        query += " AND (category_name LIKE ? OR season_climate LIKE ?)"
        params.extend([f"%{category_filter}%", f"%{category_filter}%"])

    if search_query:
        query += " AND (title LIKE ? OR description LIKE ? OR season_climate LIKE ?)"
        params.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])

    query += " ORDER BY views_count DESC"
    crop_list = conn.execute(query, params).fetchall()
    ratings_map = get_resource_ratings(conn)
    conn.close()

    categories = ['All', 'Cereals', 'Pulses', 'Vegetables', 'Cash Crops', 'Oilseeds']

    return render_template(
        'crops.html',
        crops=crop_list,
        categories=categories,
        active_cat=category_filter,
        search_query=search_query,
        ratings_map=ratings_map
    )

@app.route('/tools')
def tools():
    category_filter = request.args.get('cat', 'All')
    search_query = request.args.get('q', '').strip()

    conn = get_db()
    query = "SELECT * FROM resources WHERE resource_type = 'tool'"
    params = []

    if category_filter and category_filter != 'All':
        query += " AND (category_name LIKE ? OR season_climate LIKE ?)"
        params.extend([f"%{category_filter}%", f"%{category_filter}%"])

    if search_query:
        query += " AND (title LIKE ? OR description LIKE ? OR provider LIKE ?)"
        params.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])

    query += " ORDER BY views_count DESC"
    tool_list = conn.execute(query, params).fetchall()
    ratings_map = get_resource_ratings(conn)
    conn.close()

    categories = ['All', 'Tractors & Machinery', 'Irrigation Equipment', 'Sprayers', 'Smart Farming Devices', 'Hand & Power Tools']

    return render_template(
        'tools.html',
        tools=tool_list,
        categories=categories,
        active_cat=category_filter,
        search_query=search_query,
        ratings_map=ratings_map
    )

@app.route('/schemes')
def schemes():
    category_filter = request.args.get('cat', 'All')
    search_query = request.args.get('q', '').strip()

    conn = get_db()
    query = "SELECT * FROM resources WHERE resource_type = 'scheme'"
    params = []

    if category_filter and category_filter != 'All':
        query += " AND (category_name LIKE ? OR description LIKE ?)"
        params.extend([f"%{category_filter}%", f"%{category_filter}%"])

    if search_query:
        query += " AND (title LIKE ? OR description LIKE ? OR benefits LIKE ? OR provider LIKE ?)"
        params.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])

    query += " ORDER BY views_count DESC"
    scheme_list = conn.execute(query, params).fetchall()
    ratings_map = get_resource_ratings(conn)
    conn.close()

    categories = ['All', 'Income Support', 'Crop Insurance', 'Irrigation', 'Agricultural Infrastructure', 'Farmer Welfare']

    return render_template(
        'schemes.html',
        schemes=scheme_list,
        categories=categories,
        active_cat=category_filter,
        search_query=search_query,
        ratings_map=ratings_map
    )

@app.route('/loans')
def loans():
    category_filter = request.args.get('cat', 'All')
    search_query = request.args.get('q', '').strip()

    conn = get_db()
    query = "SELECT * FROM resources WHERE resource_type = 'loan'"
    params = []

    if category_filter and category_filter != 'All':
        query += " AND (category_name LIKE ? OR description LIKE ?)"
        params.extend([f"%{category_filter}%", f"%{category_filter}%"])

    if search_query:
        query += " AND (title LIKE ? OR description LIKE ? OR benefits LIKE ? OR provider LIKE ?)"
        params.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])

    query += " ORDER BY views_count DESC"
    loan_list = conn.execute(query, params).fetchall()
    ratings_map = get_resource_ratings(conn)
    conn.close()

    categories = ['All', 'Credit Support', 'Subsidy', 'Agricultural Infrastructure']

    return render_template(
        'loans.html',
        loans=loan_list,
        categories=categories,
        active_cat=category_filter,
        search_query=search_query,
        ratings_map=ratings_map
    )

@app.route('/resources')
def resources():
    category_filter = request.args.get('cat', 'All')
    search_query = request.args.get('q', '').strip()

    conn = get_db()
    query = "SELECT * FROM resources WHERE resource_type = 'guide'"
    params = []

    if category_filter and category_filter != 'All':
        query += " AND (category_name LIKE ? OR season_climate LIKE ?)"
        params.extend([f"%{category_filter}%", f"%{category_filter}%"])

    if search_query:
        query += " AND (title LIKE ? OR description LIKE ? OR benefits LIKE ?)"
        params.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])

    query += " ORDER BY views_count DESC"
    guide_list = conn.execute(query, params).fetchall()
    ratings_map = get_resource_ratings(conn)
    conn.close()

    categories = ['All', 'Organic Farming', 'Soil Management', 'Pest Control', 'Irrigation', 'Crop Rotation']

    return render_template(
        'resources.html',
        guides=guide_list,
        categories=categories,
        active_cat=category_filter,
        search_query=search_query,
        ratings_map=ratings_map
    )

# --- WEATHER SERVICE & AGRI-ADVISORIES ---

@app.route('/weather')
def weather():
    city_key = request.args.get('city', 'ludhiana').lower()
    if city_key not in INDIAN_AGRI_CITIES:
        city_key = 'ludhiana'

    city_info = INDIAN_AGRI_CITIES[city_key]
    weather_data = get_weather_data(city_info)

    return render_template(
        'weather.html',
        cities=INDIAN_AGRI_CITIES,
        city_key=city_key,
        city_info=city_info,
        weather=weather_data
    )

def get_weather_data(city_info):
    lat = city_info['lat']
    lon = city_info['lon']
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,precipitation&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=Asia%2FKolkata"

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'ShramSetuu/2.0'})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            current = data.get('current', {})
            daily = data.get('daily', {})

            temp = round(current.get('temperature_2m', 29.5), 1)
            humidity = current.get('relative_humidity_2m', 62)
            wind = round(current.get('wind_speed_10m', 12.0), 1)
            code = current.get('weather_code', 1)
            precip = current.get('precipitation', 0.0)

            condition, icon = parse_wmo_code(code)

            forecast = []
            dates = daily.get('time', [])
            codes = daily.get('weather_code', [])
            max_temps = daily.get('temperature_2m_max', [])
            min_temps = daily.get('temperature_2m_min', [])
            rain_probs = daily.get('precipitation_probability_max', [])

            for i in range(min(5, len(dates))):
                d_date = dates[i]
                try:
                    dt = datetime.strptime(d_date, "%Y-%m-%d")
                    day_name = dt.strftime("%a, %d %b")
                except Exception:
                    day_name = f"Day {i+1}"

                d_cond, d_icon = parse_wmo_code(codes[i] if i < len(codes) else 0)
                forecast.append({
                    'day': day_name,
                    'max_temp': round(max_temps[i], 1) if i < len(max_temps) else 32,
                    'min_temp': round(min_temps[i], 1) if i < len(min_temps) else 22,
                    'rain_prob': rain_probs[i] if i < len(rain_probs) else 15,
                    'condition': d_cond,
                    'icon': d_icon
                })

            tips = generate_agri_tips(temp, humidity, wind, precip, forecast)

            return {
                'temp': temp,
                'condition': condition,
                'icon': icon,
                'humidity': humidity,
                'wind': wind,
                'rain_prob': forecast[0]['rain_prob'] if forecast else 20,
                'forecast': forecast,
                'tips': tips,
                'is_live': True
            }
    except Exception:
        # Fallback calibrated simulation
        return get_simulated_weather(city_info)

def parse_wmo_code(code):
    if code == 0:
        return 'Clear Sky / Sunny', 'fa-sun'
    elif code in (1, 2):
        return 'Partly Cloudy', 'fa-cloud-sun'
    elif code == 3:
        return 'Overcast Clouds', 'fa-cloud'
    elif code in (45, 48):
        return 'Fog / Mist', 'fa-smog'
    elif code in (51, 53, 55, 61, 63):
        return 'Moderate Rain / Showers', 'fa-cloud-rain'
    elif code in (65, 80, 81, 82):
        return 'Heavy Monsoon Rain', 'fa-cloud-showers-heavy'
    elif code in (95, 96, 99):
        return 'Thunderstorm & Lightning', 'fa-bolt'
    else:
        return 'Scattered Clouds', 'fa-cloud-sun'

def generate_agri_tips(temp, humidity, wind, precip, forecast):
    tips = []
    max_rain = max([f['rain_prob'] for f in forecast]) if forecast else 20

    if max_rain > 60 or precip > 2.0:
        tips.append({
            'type': 'warning',
            'icon': 'fa-triangle-exclamation',
            'title': 'Rain Alert — Delay Pesticide & Fertilizer Spray',
            'text': 'High probability of showers expected. Delay foliar chemical sprays, pesticide applications, and harvesting of mature pulses or vegetables to prevent wash-off.'
        })
    elif max_rain < 25 and temp > 32:
        tips.append({
            'type': 'info',
            'icon': 'fa-droplet',
            'title': 'Irrigation Scheduling Advisory',
            'text': 'Warm and dry conditions prevailing. Schedule light drip or furrow irrigation during early morning (6 AM – 9 AM) or evening to minimize evaporative water loss.'
        })

    if wind > 18:
        tips.append({
            'type': 'warning',
            'icon': 'fa-wind',
            'title': 'High Wind Warning — Support Tall Crops',
            'text': f'Gusty winds up to {wind} km/h detected. Provide staking/earthing up support for sugarcane, maize, and banana crops to prevent lodging.'
        })
    else:
        tips.append({
            'type': 'success',
            'icon': 'fa-spray-can-sparkles',
            'title': 'Optimal Weather Window for Field Operations',
            'text': 'Gentle wind speed and moderate humidity make this an optimal time for tractor weeding, intercultural hoeing, and seedbed preparation.'
        })

    if temp > 35:
        tips.append({
            'type': 'danger',
            'icon': 'fa-temperature-arrow-up',
            'title': 'Heat Stress Protection for Livestock & Crops',
            'text': 'High temperature window. Ensure clean drinking water in cattle sheds and maintain organic mulching across vegetable beds to conserve soil moisture.'
        })
    elif temp < 14:
        tips.append({
            'type': 'info',
            'icon': 'fa-snowflake',
            'title': 'Cold Weather Advisory — Monitor Sensitive Crops',
            'text': 'Cool weather prevailing. Keep field borders slightly moist in evening hours to protect young seedlings from cold drafts and blight infection.'
        })

    return tips

def get_simulated_weather(city_info):
    temp = 28.5
    humidity = 65
    wind = 11.2
    condition = 'Partly Cloudy'
    icon = 'fa-cloud-sun'
    forecast = [
        {'day': 'Today', 'max_temp': 31.0, 'min_temp': 22.0, 'rain_prob': 20, 'condition': 'Partly Cloudy', 'icon': 'fa-cloud-sun'},
        {'day': 'Tomorrow', 'max_temp': 32.5, 'min_temp': 21.5, 'rain_prob': 15, 'condition': 'Bright & Sunny', 'icon': 'fa-sun'},
        {'day': 'Day 3', 'max_temp': 30.0, 'min_temp': 23.0, 'rain_prob': 45, 'condition': 'Scattered Showers', 'icon': 'fa-cloud-rain'},
        {'day': 'Day 4', 'max_temp': 29.0, 'min_temp': 22.0, 'rain_prob': 60, 'condition': 'Passing Monsoon Rain', 'icon': 'fa-cloud-showers-heavy'},
        {'day': 'Day 5', 'max_temp': 31.5, 'min_temp': 21.0, 'rain_prob': 10, 'condition': 'Clear Sunny Sky', 'icon': 'fa-sun'}
    ]
    tips = generate_agri_tips(temp, humidity, wind, 0.0, forecast)
    return {
        'temp': temp,
        'condition': condition,
        'icon': icon,
        'humidity': humidity,
        'wind': wind,
        'rain_prob': 20,
        'forecast': forecast,
        'tips': tips,
        'is_live': False
    }

@app.route('/marketplace')
def marketplace():
    category_filter = request.args.get('cat', 'All')
    search_query = request.args.get('q', '').strip()
    mandi_state = request.args.get('mandi_state', '').strip()

    conn = get_db()
    query = "SELECT * FROM resources WHERE resource_type = 'marketplace'"
    params = []

    if category_filter and category_filter != 'All':
        query += " AND (category_name LIKE ? OR title LIKE ?)"
        params.extend([
            f"%{category_filter}%",
            f"%{category_filter}%"
        ])

    if search_query:
        query += " AND (title LIKE ? OR description LIKE ? OR provider LIKE ?)"
        params.extend([
            f"%{search_query}%",
            f"%{search_query}%",
            f"%{search_query}%"
        ])

    query += " ORDER BY views_count DESC"

    market_list = conn.execute(query, params).fetchall()
    ratings_map = get_resource_ratings(conn)
    conn.close()

    # Fetch government mandi prices
    mandi_prices, mandi_is_live, mandi_message = get_mandi_prices(
        limit=100,
        state=mandi_state
    )

    categories = [
        'All',
        'Sell Crops',
        'Buy Seeds',
        'Buy Farming Equipment',
        'Fertilizers',
        'Agricultural Market Prices',
        'Government Marketplaces'
    ]

    return render_template(
        'marketplace.html',
        marketplaces=market_list,
        categories=categories,
        active_cat=category_filter,
        search_query=search_query,
        mandi_prices=mandi_prices,
        mandi_is_live=mandi_is_live,
        mandi_message=mandi_message,
        ratings_map=ratings_map,
        mandi_state=mandi_state,
    )
    
@app.route('/community', methods=['GET', 'POST'])
def community():
    conn = get_db()

    if request.method == 'POST':
        if not g.user:
            flash('Please log in to post a question or discussion topic in the community.', 'warning')
            return redirect(url_for('login', next=url_for('community')))

        title = request.form.get('title', '').strip()
        category = request.form.get('category', 'General Discussion').strip()
        content = request.form.get('content', '').strip()

        if not title or not content:
            flash('Please enter both question title and content.', 'danger')
        else:
            conn.execute("""
            INSERT INTO community_posts (user_id, title, category, content)
            VALUES (?, ?, ?, ?)
            """, (g.user['id'], title, category, content))
            conn.commit()
            flash('Your question has been posted to the farmer community!', 'success')
            conn.close()
            return redirect(url_for('community'))

    institutions = conn.execute("""
    SELECT * FROM resources WHERE resource_type = 'community' ORDER BY views_count DESC
    """).fetchall()

    posts = conn.execute("""
    SELECT p.*, u.full_name as author_name, u.state as author_state,
           (SELECT COUNT(*) FROM comments WHERE post_id = p.id) as comment_count,
           (SELECT COUNT(*) FROM likes WHERE post_id = p.id) as like_count
    FROM community_posts p
    JOIN users u ON p.user_id = u.id
    ORDER BY p.created_at DESC
    """).fetchall()

    comments_raw = conn.execute("""
    SELECT c.*, u.full_name as comment_author, u.state as comment_state
    FROM comments c
    JOIN users u ON c.user_id = u.id
    ORDER BY c.created_at ASC
    """).fetchall()

    comments_by_post = {}
    for c in comments_raw:
        comments_by_post.setdefault(c['post_id'], []).append(c)

    user_liked_posts = set()
    if g.user:
        likes_data = conn.execute("SELECT post_id FROM likes WHERE user_id = ?", (g.user['id'],)).fetchall()
        user_liked_posts = {row['post_id'] for row in likes_data}

    ratings_map = get_resource_ratings(conn)
    conn.close()

    return render_template(
        'community.html',
        institutions=institutions,
        posts=posts,
        comments_by_post=comments_by_post,
        user_liked_posts=user_liked_posts,
        ratings_map=ratings_map
    )

@app.route('/community/comment/<int:post_id>', methods=['POST'])
@login_required
def add_comment(post_id):
    comment_text = request.form.get('comment', '').strip()
    if not comment_text:
        flash('Comment cannot be empty.', 'warning')
        return redirect(url_for('community'))

    conn = get_db()
    post = conn.execute("SELECT id FROM community_posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        conn.close()
        flash('Discussion post not found.', 'danger')
        return redirect(url_for('community'))

    conn.execute("""
    INSERT INTO comments (post_id, user_id, comment)
    VALUES (?, ?, ?)
    """, (post_id, g.user['id'], comment_text))
    conn.commit()
    conn.close()

    flash('Your comment was added!', 'success')
    return redirect(url_for('community'))

@app.route('/api/community/like/<int:post_id>', methods=['POST'])
@login_required
def toggle_like(post_id):
    user_id = g.user['id']
    conn = get_db()
    post = conn.execute("SELECT id FROM community_posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Post not found'}), 404

    existing = conn.execute("SELECT id FROM likes WHERE post_id = ? AND user_id = ?", (post_id, user_id)).fetchone()

    if existing:
        conn.execute("DELETE FROM likes WHERE post_id = ? AND user_id = ?", (post_id, user_id))
        conn.commit()
        action = 'unliked'
    else:
        conn.execute("INSERT INTO likes (post_id, user_id) VALUES (?, ?)", (post_id, user_id))
        conn.commit()
        action = 'liked'

    total_likes = conn.execute("SELECT COUNT(*) FROM likes WHERE post_id = ?", (post_id,)).fetchone()[0]
    conn.close()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return jsonify({'status': 'success', 'action': action, 'total_likes': total_likes})

    return redirect(url_for('community'))

@app.route('/community/delete-post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    conn = get_db()
    post = conn.execute("SELECT * FROM community_posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        flash('Post not found.', 'danger')
        conn.close()
        return redirect(url_for('community'))

    if post['user_id'] != g.user['id'] and g.user['role'] != 'admin':
        flash('You do not have permission to delete this post.', 'danger')
        conn.close()
        return redirect(url_for('community'))

    conn.execute("DELETE FROM community_posts WHERE id = ?", (post_id,))
    conn.commit()
    conn.close()

    flash('Post deleted successfully.', 'info')
    return redirect(url_for('community'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    conn = get_db()
    user_id = g.user['id']

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        state = request.form.get('state', 'General')
        preferred_category = request.form.get('preferred_category', 'General')
        new_password = request.form.get('new_password', '').strip()

        if not full_name or not email:
            flash('Name and Email cannot be empty.', 'danger')
        else:
            existing = conn.execute("SELECT id FROM users WHERE email = ? AND id != ?", (email, user_id)).fetchone()
            if existing:
                flash('This email is already in use by another account.', 'warning')
            else:
                if new_password:
                    if len(new_password) < 6:
                        flash('New password must be at least 6 characters.', 'danger')
                        conn.close()
                        return redirect(url_for('profile'))
                    p_hash = generate_password_hash(new_password)
                    conn.execute("""
                    UPDATE users SET full_name = ?, email = ?, state = ?, preferred_category = ?, password_hash = ?
                    WHERE id = ?
                    """, (full_name, email, state, preferred_category, p_hash, user_id))
                else:
                    conn.execute("""
                    UPDATE users SET full_name = ?, email = ?, state = ?, preferred_category = ?
                    WHERE id = ?
                    """, (full_name, email, state, preferred_category, user_id))

                conn.commit()
                flash('Profile updated successfully!', 'success')
                conn.close()
                return redirect(url_for('profile'))

    user_info = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    bookmarks_count = conn.execute("SELECT COUNT(*) FROM bookmarks WHERE user_id = ?", (user_id,)).fetchone()[0]
    posts_count = conn.execute("SELECT COUNT(*) FROM community_posts WHERE user_id = ?", (user_id,)).fetchone()[0]
    feedback_count = conn.execute("SELECT COUNT(*) FROM feedback WHERE user_id = ?", (user_id,)).fetchone()[0]
    conn.close()

    return render_template(
        'profile.html',
        user=user_info,
        bookmarks_count=bookmarks_count,
        posts_count=posts_count,
        feedback_count=feedback_count
    )

@app.route('/bookmarks')
@login_required
def bookmarks():
    user_id = g.user['id']
    cat_filter = request.args.get('type', 'All')

    conn = get_db()
    query = """
    SELECT r.*, b.created_at as bookmarked_date
    FROM bookmarks b
    JOIN resources r ON b.resource_id = r.id
    WHERE b.user_id = ?
    """
    params = [user_id]

    if cat_filter and cat_filter != 'All':
        query += " AND r.resource_type = ?"
        params.append(cat_filter)

    query += " ORDER BY b.created_at DESC"
    saved_resources = conn.execute(query, params).fetchall()
    ratings_map = get_resource_ratings(conn)
    conn.close()

    types = [
        ('All', 'All Items'),
        ('scheme', 'Government Schemes'),
        ('crop', 'Seeds & Crops'),
        ('tool', 'Farming Tools'),
        ('loan', 'Loans & Subsidies'),
        ('guide', 'Farming Guides'),
        ('marketplace', 'Marketplaces')
    ]

    return render_template(
        'bookmarks.html',
        saved_resources=saved_resources,
        types=types,
        active_type=cat_filter,
        ratings_map=ratings_map
    )

# --- AUTHENTICATION ROUTES ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if g.user:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        username = request.form.get('username', '').strip().lower()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        state = request.form.get('state', 'General')
        preferred_category = request.form.get('preferred_category', 'General')

        if not full_name or not username or not email or not password:
            flash('All required fields must be filled.', 'danger')
            return render_template('register.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return render_template('register.html')

        if password != confirm_password:
            flash('Passwords do not match. Please try again.', 'danger')
            return render_template('register.html')

        conn = get_db()
        existing_user = conn.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username, email)).fetchone()

        if existing_user:
            flash('Username or Email already registered. Please log in.', 'warning')
            conn.close()
            return redirect(url_for('login'))

        p_hash = generate_password_hash(password)
        conn.execute("""
        INSERT INTO users (full_name, username, email, password_hash, state, preferred_category, role)
        VALUES (?, ?, ?, ?, ?, ?, 'user')
        """, (full_name, username, email, p_hash, state, preferred_category))
        conn.commit()

        # Log in newly registered user
        new_user = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        session['user_id'] = new_user['id']
        conn.close()

        flash(f'Welcome to Shram setuu, {full_name}! Your account is ready.', 'success')
        return redirect(url_for('dashboard'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if g.user:
        return redirect(url_for('dashboard'))

    next_param = request.args.get('next') or request.form.get('next')

    if request.method == 'POST':
        username_or_email = request.form.get('username_or_email', '').strip().lower()
        password = request.form.get('password', '')

        if not username_or_email or not password:
            flash('Please enter both credentials.', 'danger')
            return render_template('login.html')

        # Check if environment-based admin login is configured
        env_admin_user = os.environ.get('ADMIN_USERNAME', '').strip().lower()
        env_admin_pass = os.environ.get('ADMIN_PASSWORD', '').strip()

        conn = get_db()
        # If matching environment admin credentials, ensure admin user is synced
        if env_admin_user and env_admin_pass:
            if (username_or_email == env_admin_user or username_or_email == f"{env_admin_user}@kisansahayak.in") and password == env_admin_pass:
                sync_admin_credentials(conn)

        user = conn.execute("""
        SELECT * FROM users WHERE LOWER(username) = ? OR LOWER(email) = ?
        """, (username_or_email, username_or_email)).fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            flash(f'Welcome back, {user["full_name"]}!', 'success')

            # Validate open redirect safety
            if next_param and is_safe_url(next_param):
                return redirect(next_param)

            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username/email or password.', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been signed out safely.', 'info')
    return redirect(url_for('index'))

# --- API ENDPOINTS ---

@app.route('/api/bookmark/toggle', methods=['POST'])
def api_toggle_bookmark():
    if not g.user:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'status': 'error', 'message': 'Please login to save resources.', 'redirect': url_for('login')}), 401
        flash('Please login to save resources.', 'warning')
        return redirect(url_for('login'))

    raw_res_id = request.form.get('resource_id') or ((request.get_json(silent=True) or {}).get('resource_id') if request.is_json else None)
    if not raw_res_id:
        return jsonify({'status': 'error', 'message': 'Resource ID required.'}), 400

    try:
        resource_id = int(raw_res_id)
    except (ValueError, TypeError):
        return jsonify({'status': 'error', 'message': 'Invalid Resource ID format.'}), 400

    conn = get_db()
    resource = conn.execute("SELECT id FROM resources WHERE id = ?", (resource_id,)).fetchone()
    if not resource:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Resource not found.'}), 404

    user_id = g.user['id']
    existing = conn.execute("SELECT id FROM bookmarks WHERE user_id = ? AND resource_id = ?", (user_id, resource_id)).fetchone()

    if existing:
        conn.execute("DELETE FROM bookmarks WHERE user_id = ? AND resource_id = ?", (user_id, resource_id))
        conn.commit()
        action = 'removed'
        msg = 'Resource removed from your saved list.'
    else:
        conn.execute("INSERT INTO bookmarks (user_id, resource_id) VALUES (?, ?)", (user_id, resource_id))
        conn.commit()
        action = 'saved'
        msg = 'Resource bookmarked to your Farmer Dashboard!'

    total_saved = conn.execute("SELECT COUNT(*) FROM bookmarks WHERE user_id = ?", (user_id,)).fetchone()[0]
    conn.close()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return jsonify({'status': 'success', 'action': action, 'message': msg, 'total_saved': total_saved})

    flash(msg, 'success')
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/api/rate-feedback', methods=['POST'])
@login_required
def api_rate_feedback():
    raw_res_id = request.form.get('resource_id')
    raw_rating = request.form.get('rating')
    comment = request.form.get('comment', '').strip()

    if not raw_res_id or not raw_rating:
        flash('Please provide both a resource and rating (1-5 stars).', 'danger')
        return redirect(request.referrer or url_for('index'))

    try:
        resource_id = int(raw_res_id)
        rating = int(raw_rating)
        if rating < 1 or rating > 5:
            raise ValueError()
    except (ValueError, TypeError):
        flash('Invalid rating value.', 'danger')
        return redirect(request.referrer or url_for('index'))

    conn = get_db()
    resource = conn.execute("SELECT id FROM resources WHERE id = ?", (resource_id,)).fetchone()
    if not resource:
        conn.close()
        flash('Resource not found.', 'danger')
        return redirect(request.referrer or url_for('index'))

    user_id = g.user['id']
    existing = conn.execute("SELECT id FROM feedback WHERE user_id = ? AND resource_id = ?", (user_id, resource_id)).fetchone()

    if existing:
        conn.execute("""
        UPDATE feedback SET rating = ?, comment = ?, created_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """, (rating, comment, existing['id']))
    else:
        conn.execute("""
        INSERT INTO feedback (user_id, resource_id, rating, comment)
        VALUES (?, ?, ?, ?)
        """, (user_id, resource_id, rating, comment))

    conn.commit()
    conn.close()

    flash('Thank you for rating and reviewing this resource!', 'success')
    return redirect(request.referrer or url_for('index'))

@app.route('/api/resource/<int:res_id>')
def api_get_resource(res_id):
    conn = get_db()
    resource = conn.execute("SELECT * FROM resources WHERE id = ?", (res_id,)).fetchone()
    if not resource:
        conn.close()
        return jsonify({'error': 'Resource not found'}), 404

    conn.execute("UPDATE resources SET views_count = views_count + 1 WHERE id = ?", (res_id,))
    conn.commit()

    feedback_list = conn.execute("""
    SELECT f.*, u.full_name as user_name
    FROM feedback f
    JOIN users u ON f.user_id = u.id
    WHERE f.resource_id = ?
    ORDER BY f.created_at DESC
    """, (res_id,)).fetchall()

    conn.close()

    return jsonify({
        'id': resource['id'],
        'title': resource['title'],
        'description': resource['description'],
        'category_name': resource['category_name'],
        'resource_type': resource['resource_type'],
        'external_url': resource['external_url'],
        'image_url': resource['image_url'],
        'season_climate': resource['season_climate'],
        'eligibility': resource['eligibility'],
        'benefits': resource['benefits'],
        'provider': resource['provider'],
        'views_count': resource['views_count'],
        'feedback': [{'user': f['user_name'], 'rating': f['rating'], 'comment': f['comment']} for f in feedback_list]
    })

# --- ADMIN DASHBOARD & CRUD ---

@app.route('/admin')
@admin_required
def admin_dashboard():
    conn = get_db()

    stats = {
        'total_users': conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        'total_resources': conn.execute("SELECT COUNT(*) FROM resources").fetchone()[0],
        'total_categories': conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0],
        'total_feedback': conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0],
        'total_bookmarks': conn.execute("SELECT COUNT(*) FROM bookmarks").fetchone()[0],
        'total_posts': conn.execute("SELECT COUNT(*) FROM community_posts").fetchone()[0],
        'avg_rating': round(conn.execute("SELECT COALESCE(AVG(rating), 0) FROM feedback").fetchone()[0], 1)
    }

    resources_list = conn.execute("""
    SELECT r.*, 
           (SELECT COUNT(*) FROM bookmarks WHERE resource_id = r.id) as bookmark_count,
           (SELECT COALESCE(AVG(rating), 0) FROM feedback WHERE resource_id = r.id) as avg_rating
    FROM resources r
    ORDER BY r.id DESC
    """).fetchall()

    users_list = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    categories_list = conn.execute("SELECT * FROM categories ORDER BY name ASC").fetchall()

    feedback_list = conn.execute("""
    SELECT f.*, u.full_name, u.username, r.title as resource_title
    FROM feedback f
    JOIN users u ON f.user_id = u.id
    JOIN resources r ON f.resource_id = r.id
    ORDER BY f.created_at DESC
    """).fetchall()

    posts_list = conn.execute("""
    SELECT p.*, u.full_name, u.username,
           (SELECT COUNT(*) FROM comments WHERE post_id = p.id) as comment_count,
           (SELECT COUNT(*) FROM likes WHERE post_id = p.id) as like_count
    FROM community_posts p
    JOIN users u ON p.user_id = u.id
    ORDER BY p.created_at DESC
    """).fetchall()

    conn.close()

    return render_template(
        'admin.html',
        stats=stats,
        resources=resources_list,
        users=users_list,
        categories=categories_list,
        feedback_list=feedback_list,
        posts=posts_list
    )

@app.route('/admin/resource/add', methods=['POST'])
@admin_required
def admin_add_resource():
    title = request.form.get('title', '').strip()
    resource_type = request.form.get('resource_type', 'scheme').strip()
    category_name = request.form.get('category_name', '').strip()
    description = request.form.get('description', '').strip()
    external_url = request.form.get('external_url', '').strip()
    image_url = request.form.get('image_url', '').strip()
    season_climate = request.form.get('season_climate', '').strip()
    eligibility = request.form.get('eligibility', '').strip()
    benefits = request.form.get('benefits', '').strip()
    provider = request.form.get('provider', '').strip()

    if not title or not description or not resource_type:
        flash('Title, Description and Resource Type are mandatory.', 'danger')
        return redirect(url_for('admin_dashboard'))

    conn = get_db()
    # Check duplicate prevention
    existing = conn.execute("SELECT id FROM resources WHERE LOWER(title) = ?", (title.lower(),)).fetchone()
    if existing:
        flash(f'A resource with title "{title}" already exists.', 'warning')
        conn.close()
        return redirect(url_for('admin_dashboard'))

    conn.execute("""
    INSERT INTO resources (
        title, description, category_name, resource_type,
        external_url, image_url, season_climate, eligibility, benefits, provider
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (title, description, category_name, resource_type, external_url, image_url, season_climate, eligibility, benefits, provider))
    conn.commit()
    conn.close()

    flash(f'Resource "{title}" created successfully.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/resource/edit/<int:res_id>', methods=['POST'])
@admin_required
def admin_edit_resource(res_id):
    title = request.form.get('title', '').strip()
    resource_type = request.form.get('resource_type', '').strip()
    category_name = request.form.get('category_name', '').strip()
    description = request.form.get('description', '').strip()
    external_url = request.form.get('external_url', '').strip()
    image_url = request.form.get('image_url', '').strip()
    season_climate = request.form.get('season_climate', '').strip()
    eligibility = request.form.get('eligibility', '').strip()
    benefits = request.form.get('benefits', '').strip()
    provider = request.form.get('provider', '').strip()

    if not title or not description:
        flash('Title and Description are mandatory.', 'danger')
        return redirect(url_for('admin_dashboard'))

    conn = get_db()
    existing = conn.execute("SELECT id FROM resources WHERE id = ?", (res_id,)).fetchone()
    if not existing:
        flash('Resource record not found.', 'danger')
        conn.close()
        return redirect(url_for('admin_dashboard'))

    conn.execute("""
    UPDATE resources SET
        title = ?, description = ?, category_name = ?, resource_type = ?,
        external_url = ?, image_url = ?, season_climate = ?, eligibility = ?,
        benefits = ?, provider = ?
    WHERE id = ?
    """, (title, description, category_name, resource_type, external_url, image_url, season_climate, eligibility, benefits, provider, res_id))
    conn.commit()
    conn.close()

    flash(f'Resource #{res_id} "{title}" updated successfully.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/resource/delete/<int:res_id>', methods=['POST'])
@admin_required
def admin_delete_resource(res_id):
    conn = get_db()
    conn.execute("DELETE FROM resources WHERE id = ?", (res_id,))
    conn.commit()
    conn.close()

    flash(f'Resource #{res_id} deleted permanently.', 'info')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/user/toggle-role/<int:u_id>', methods=['POST'])
@admin_required
def admin_toggle_user_role(u_id):
    if u_id == g.user['id']:
        flash('Cannot change your own role.', 'warning')
        return redirect(url_for('admin_dashboard'))

    conn = get_db()
    user = conn.execute("SELECT role FROM users WHERE id = ?", (u_id,)).fetchone()
    if user:
        new_role = 'user' if user['role'] == 'admin' else 'admin'
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, u_id))
        conn.commit()
        flash(f'User role changed to {new_role}.', 'success')
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/user/delete/<int:u_id>', methods=['POST'])
@admin_required
def admin_delete_user(u_id):
    if u_id == g.user['id']:
        flash('Cannot delete your own admin account.', 'danger')
        return redirect(url_for('admin_dashboard'))

    conn = get_db()
    conn.execute("DELETE FROM users WHERE id = ?", (u_id,))
    conn.commit()
    conn.close()

    flash('User and all associated data deleted.', 'info')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/feedback/delete/<int:f_id>', methods=['POST'])
@admin_required
def admin_delete_feedback(f_id):
    conn = get_db()
    conn.execute("DELETE FROM feedback WHERE id = ?", (f_id,))
    conn.commit()
    conn.close()

    flash('Feedback entry removed.', 'info')
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    is_debug = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    print(f"Starting Shram setuu on http://127.0.0.1:5000 (debug={is_debug})")
    app.run(debug=is_debug, host='127.0.0.1', port=5000)

import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

DB_FOLDER = os.path.join(os.path.dirname(__file__), 'database')
DB_PATH = os.path.join(DB_FOLDER, 'database.db')

def get_db(db_path=None):
    if db_path is None:
        db_path = os.environ.get('KISAN_DB_PATH', DB_PATH)
    folder = os.path.dirname(db_path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def is_database_empty(conn):
    """Checks if the database is genuinely empty across all data tables."""
    cursor = conn.cursor()
    tables = ['users', 'categories', 'resources', 'bookmarks', 'feedback', 'community_posts', 'comments', 'likes']
    total_count = 0
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            total_count += cursor.fetchone()[0]
        except Exception:
            pass
    return total_count == 0

def sync_admin_credentials(conn=None):
    """
    Synchronizes the admin account from ADMIN_USERNAME and ADMIN_PASSWORD environment variables.
    Ensures that default hardcoded 'admin / admin123' credentials never work.
    """
    admin_user = os.environ.get('ADMIN_USERNAME', '').strip().lower()
    admin_pass = os.environ.get('ADMIN_PASSWORD', '').strip()

    close_after = False
    if conn is None:
        conn = get_db()
        close_after = True

    cursor = conn.cursor()

    # Invalidate/delete legacy hardcoded 'admin' user with 'admin123' if present
    legacy_admin = cursor.execute("SELECT id, password_hash FROM users WHERE username = 'admin'").fetchone()
    if legacy_admin:
        try:
            if check_password_hash(legacy_admin['password_hash'], 'admin123'):
                if not (admin_user == 'admin' and admin_pass and admin_pass != 'admin123'):
                    cursor.execute("DELETE FROM users WHERE id = ?", (legacy_admin['id'],))
                    conn.commit()
        except Exception:
            pass

    # If ADMIN_USERNAME and ADMIN_PASSWORD are provided, create or update the admin account
    if admin_user and admin_pass:
        p_hash = generate_password_hash(admin_pass)
        existing = cursor.execute("SELECT id FROM users WHERE LOWER(username) = ? OR LOWER(email) = ?",
                                  (admin_user, f"{admin_user}@kisansahayak.in")).fetchone()
        if existing:
            cursor.execute("""
            UPDATE users SET
                username = ?,
                password_hash = ?,
                role = 'admin',
                full_name = 'Admin Officer'
            WHERE id = ?
            """, (admin_user, p_hash, existing['id']))
        else:
            cursor.execute("""
            INSERT INTO users (full_name, username, email, password_hash, state, preferred_category, role)
            VALUES (?, ?, ?, ?, 'New Delhi', 'Government Schemes', 'admin')
            """, ('Admin Officer', admin_user, f"{admin_user}@kisansahayak.in", p_hash))
        conn.commit()

    if close_after:
        conn.close()

def init_db(force_reset=False):
    """Initializes the database schema and seeds initial data only if genuinely empty or force_reset=True."""
    conn = get_db()
    cursor = conn.cursor()

    # Create Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        state TEXT DEFAULT 'General',
        preferred_category TEXT DEFAULT 'General',
        role TEXT DEFAULT 'user',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Create Categories table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        description TEXT,
        icon TEXT
    )
    """)

    # Create Resources table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        category_id INTEGER,
        category_name TEXT,
        resource_type TEXT NOT NULL,
        external_url TEXT,
        image_url TEXT,
        season_climate TEXT,
        eligibility TEXT,
        benefits TEXT,
        provider TEXT,
        views_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Create Bookmarks table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bookmarks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        resource_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, resource_id),
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(resource_id) REFERENCES resources(id) ON DELETE CASCADE
    )
    """)

    # Create Feedback table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        resource_id INTEGER NOT NULL,
        rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
        comment TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(resource_id) REFERENCES resources(id) ON DELETE CASCADE
    )
    """)

    # Create Community Posts table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS community_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        category TEXT DEFAULT 'General Discussion',
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # Create Comments table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        comment TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(post_id) REFERENCES community_posts(id) ON DELETE CASCADE,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # Create Likes table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS likes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        UNIQUE(post_id, user_id),
        FOREIGN KEY(post_id) REFERENCES community_posts(id) ON DELETE CASCADE,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    conn.commit()

    if force_reset:
        seed_data(conn, force_reset=True)
    else:
        # Only seed if database is genuinely empty (total records across all tables == 0)
        if is_database_empty(conn):
            seed_data(conn, force_reset=False)

    # Always ensure admin credentials are synchronized from environment variables
    sync_admin_credentials(conn)

    conn.close()

def seed_data(conn, force_reset=False):
    """Populates database with initial realistic Indian agricultural data safely and idempotently."""
    cursor = conn.cursor()

    if force_reset:
        # Clear child tables first to respect foreign keys
        cursor.execute("DELETE FROM likes")
        cursor.execute("DELETE FROM comments")
        cursor.execute("DELETE FROM community_posts")
        cursor.execute("DELETE FROM feedback")
        cursor.execute("DELETE FROM bookmarks")
        cursor.execute("DELETE FROM resources")
        cursor.execute("DELETE FROM categories")
        cursor.execute("DELETE FROM users")
        try:
            cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('users', 'categories', 'resources', 'bookmarks', 'feedback', 'community_posts', 'comments', 'likes')")
        except Exception:
            pass

    # 1. Seed Demo Farmer Users (No hardcoded admin credentials)
    users_data = [
        ('Demo Farmer One', 'demo_farmer_1', 'demo.farmer1@example.com', generate_password_hash('DemoFarmer2026!'), 'Punjab', 'Seeds & Crops', 'user'),
        ('Demo Farmer Two', 'demo_farmer_2', 'demo.farmer2@example.com', generate_password_hash('DemoFarmer2026!'), 'Madhya Pradesh', 'Organic Farming', 'user'),
        ('Demo Farmer Three', 'demo_farmer_3', 'demo.farmer3@example.com', generate_password_hash('DemoFarmer2026!'), 'Haryana', 'Farming Tools', 'user')
    ]   
    for u in users_data:
        existing = cursor.execute("SELECT id FROM users WHERE username = ?", (u[1],)).fetchone()
        if not existing:
            cursor.execute("""
            INSERT INTO users (full_name, username, email, password_hash, state, preferred_category, role)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, u)

    # 2. Seed Categories
    categories_data = [
        ('Cereals & Grains', 'cereals', 'Staple crops including rice, wheat, and millets.', 'fa-wheat-awn'),
        ('Pulses & Legumes', 'pulses', 'High-protein crops such as gram, lentils, and soybean.', 'fa-seedling'),
        ('Vegetables & Spices', 'vegetables', 'Short-duration horticultural cash crops.', 'fa-carrot'),
        ('Commercial & Cash Crops', 'cash-crops', 'High-value crops like cotton, sugarcane, and mustard.', 'fa-sack-dollar'),
        ('Hand & Power Tools', 'hand-tools', 'Essential handheld equipment and power implements.', 'fa-screwdriver-wrench'),
        ('Irrigation Equipment', 'irrigation-tools', 'Modern micro-irrigation, drip kits, and solar pumps.', 'fa-droplet'),
        ('Tractors & Machinery', 'machinery', 'Heavy agricultural mechanization and harvesters.', 'fa-tractor'),
        ('Income Support Schemes', 'income-support', 'Direct benefit transfer and income assistance programs.', 'fa-hand-holding-dollar'),
        ('Crop Insurance', 'crop-insurance', 'Risk mitigation against climate and weather hazards.', 'fa-shield-halved'),
        ('Credit & Loans', 'credit-loans', 'Institutional finance, KCC cards, and interest subvention.', 'fa-landmark'),
        ('Organic & Soil Management', 'organic-farming', 'Natural farming, bio-fertilizers, and soil rejuvenation.', 'fa-leaf'),
        ('Mandi & Marketplace', 'marketplace', 'e-NAM portals, market yard pricing, and seed/fertilizer outlets.', 'fa-store')
    ]
    for c in categories_data:
        existing = cursor.execute("SELECT id FROM categories WHERE slug = ?", (c[1],)).fetchone()
        if not existing:
            cursor.execute("""
            INSERT INTO categories (name, slug, description, icon)
            VALUES (?, ?, ?, ?)
            """, c)

    # 3. Seed Resources (39 Unique Authentic Indian Agricultural Entries)
    resources_data = [
        # --- CROPS ---
        (
            'Rice (Paddy / धान)',
            'Staple food grain cultivated widely across Kharif season. High water-retentive clayey loam soil preferred. Requires hot and humid climate with abundant irrigation.',
            1, 'Cereals', 'crop',
            'https://icar.org.in/',
            'https://images.unsplash.com/photo-1536304993881-ff6e9eefa2a6?auto=format&fit=crop&w=600&q=80',
            'Season: Kharif (June–Nov) | Temp: 20°C–35°C | Rainfall: 100–150 cm | Soil: Clayey / Loam',
            'Suitable for all states with assured irrigation or high monsoon rainfall.',
            'High domestic and export demand. Minimum Support Price (MSP) guaranteed procurement.',
            'ICAR - Indian Institute of Rice Research (IIRR)', 142
        ),
        (
            'Wheat (गेहूं)',
            'Major Rabi cereal crop requiring cool growing period and bright sunny harvest weather. Prefers well-drained loamy and clayey loam soils.',
            1, 'Cereals', 'crop',
            'https://icar.org.in/',
            'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?auto=format&fit=crop&w=600&q=80',
            'Season: Rabi (Oct–April) | Temp: 10°C–25°C | Rainfall: 50–75 cm | Soil: Well-drained Loam',
            'North, Central & Western India (Punjab, Haryana, UP, MP, Rajasthan).',
            'Assured government procurement at MSP, high market liquidity and stable yield.',
            'ICAR - Indian Institute of Wheat and Barley Research (IIWBR)', 198
        ),
        (
            'Maize (मक्का / Corn)',
            'Versatile cereal grown for food, fodder, and industrial starch. Grows best under semi-arid conditions in well-drained red or black soils.',
            1, 'Cereals', 'crop',
            'https://icar.org.in/',
            'https://images.unsplash.com/photo-1551754655-cd27e38d2076?auto=format&fit=crop&w=600&q=80',
            'Season: Kharif & Spring | Temp: 21°C–27°C | Rainfall: 50–100 cm | Soil: Deep Loam',
            'Widely adaptable in Karnataka, MP, Bihar, Maharashtra, and Rajasthan.',
            'High industrial demand for poultry feed, ethanol production, and corn flour.',
            'ICAR - Indian Institute of Maize Research (IIMR)', 88
        ),
        (
            'Cotton (कपास / White Gold)',
            'Premier commercial fiber crop of India. Requires a warm climate, frost-free days, plenty of sunshine, and fertile black cotton (regur) soil.',
            4, 'Cash Crops', 'crop',
            'https://cotcorp.org.in/',
            'https://images.unsplash.com/photo-1594488518000-752179b00788?auto=format&fit=crop&w=600&q=80',
            'Season: Kharif (May–Nov) | Temp: 21°C–30°C | Rainfall: 50–100 cm | Soil: Deep Black Soil',
            'Majorly grown in Gujarat, Maharashtra, Telangana, and Andhra Pradesh.',
            'High remunerative cash returns and direct procurement by Cotton Corporation of India (CCI).',
            'ICAR - Central Institute for Cotton Research (CICR)', 115
        ),
        (
            'Sugarcane (गन्ना)',
            'Long-duration commercial cash crop. Needs tropical/subtropical climate with high humidity and well-drained fertile alluvial soil.',
            4, 'Cash Crops', 'crop',
            'https://iisr.icar.gov.in/',
            'https://images.unsplash.com/photo-1589135233689-d56121405e32?auto=format&fit=crop&w=600&q=80',
            'Season: Annual (10–14 months) | Temp: 20°C–35°C | Rainfall: 75–120 cm | Soil: Rich Alluvial',
            'Cultivated in Uttar Pradesh, Maharashtra, Karnataka, and Tamil Nadu.',
            'Assured mill gate procurement with Statutory Fair and Remunerative Price (FRP).',
            'ICAR - Indian Institute of Sugarcane Research', 94
        ),
        (
            'Tomato (टमाटर)',
            'High-yielding vegetable crop suitable for round-the-year cultivation under open-field and protected polyhouse conditions.',
            3, 'Vegetables', 'crop',
            'https://iihr.res.in/',
            'https://images.unsplash.com/photo-1592924357228-91a4daadcfea?auto=format&fit=crop&w=600&q=80',
            'Season: Year-round (Kharif/Rabi/Zaid) | Temp: 18°C–27°C | Soil: Well-drained Sandy Loam',
            'Suitable for all agro-climatic zones with drip irrigation.',
            'Quick turnaround (60–90 days), high daily market turnover in wholesale mandis.',
            'ICAR - Indian Institute of Horticultural Research (IIHR)', 132
        ),
        (
            'Potato (आलू)',
            'Most important tuber crop of India. Requires cool night temperatures during tuberization and light sandy loam rich in organic matter.',
            3, 'Vegetables', 'crop',
            'https://cpri.icar.gov.in/',
            'https://images.unsplash.com/photo-1518977676601-b53f82aba655?auto=format&fit=crop&w=600&q=80',
            'Season: Rabi (Oct–Feb) | Temp: 15°C–20°C | Soil: Loose Friable Loam (pH 5.2–6.4)',
            'Dominant in UP, West Bengal, Bihar, Gujarat, and Punjab.',
            'High yield per acre, excellent cold-storage marketability and processing demand.',
            'ICAR - Central Potato Research Institute (CPRI)', 110
        ),
        (
            'Mustard & Rapeseed (सरसों)',
            'Key oilseed crop of Rabi season. Tolerant to dry conditions and frost, grows well in light to heavy loam soils.',
            4, 'Oilseeds', 'crop',
            'https://drmr.icar.gov.in/',
            'https://images.unsplash.com/photo-1528183429752-a97d0bf99b5a?auto=format&fit=crop&w=600&q=80',
            'Season: Rabi (Oct–March) | Temp: 15°C–25°C | Rainfall: 25–40 cm | Soil: Light to Heavy Loam',
            'Rajasthan, Haryana, Madhya Pradesh, UP, and West Bengal.',
            'High oil recovery percentage (38-42%), strong market prices and low water requirement.',
            'ICAR - Directorate of Rapeseed-Mustard Research (DRMR)', 102
        ),
        (
            'Soybean (सोयाबीन)',
            'Wonder legume crop rich in protein and edible oil. Fixes atmospheric nitrogen to enrich soil fertility for succeeding crops.',
            2, 'Pulses & Oilseeds', 'crop',
            'https://iisrindore.icar.gov.in/',
            'https://images.unsplash.com/photo-1599488615731-7e5c2823ff28?auto=format&fit=crop&w=600&q=80',
            'Season: Kharif (June–Oct) | Temp: 20°C–32°C | Rainfall: 60–80 cm | Soil: Well-drained Black/Loam',
            'Central and Western India (Madhya Pradesh, Maharashtra, Rajasthan).',
            'Dual revenue from oil and protein meal (DOC) exports; excellent soil fertility enhancer.',
            'ICAR - Indian Institute of Soybean Research', 76
        ),
        (
            'Chickpea / Gram (चना)',
            'Major pulse crop in India representing over 40% of total pulse production. Highly resilient in drought-prone rainfed areas.',
            2, 'Pulses', 'crop',
            'https://iipr.icar.gov.in/',
            'https://images.unsplash.com/photo-1546833999-b9f581a1996d?auto=format&fit=crop&w=600&q=80',
            'Season: Rabi (Oct–March) | Temp: 15°C–25°C | Rainfall: 30–50 cm | Soil: Deep Silt Loam',
            'Madhya Pradesh, Maharashtra, Rajasthan, Karnataka, and UP.',
            'High domestic pulse demand, stable MSP, and minimal chemical fertilizer needs.',
            'ICAR - Indian Institute of Pulses Research (IIPR)', 84
        ),

        # --- FARMING TOOLS ---
        (
            'Tractor Mounted Rotavator (रोटावेटर)',
            'Rotary tiller implement driven by tractor PTO. Crushes clods, cuts crop residues, and produces fine seedbed in a single pass.',
            7, 'Tractors & Machinery', 'tool',
            'https://agrimachinery.nic.in/',
            'https://images.unsplash.com/photo-1589820296156-2454bb8a6ad1?auto=format&fit=crop&w=600&q=80',
            'Category: Tractor Implement | Power: 35–60 HP | Operation: PTO Driven 540 RPM',
            'Available for all farmers owning or hiring a 35+ HP tractor.',
            'Saves up to 40% fuel and preparation time compared to conventional multi-disc ploughing.',
            'Department of Agriculture & Farmers Welfare (SMAM)', 140
        ),
        (
            'Solar Powered Drip Irrigation Kit',
            'Complete micro-irrigation unit integrated with a DC solar submersible/surface pump and automatic filtration system.',
            6, 'Irrigation Equipment', 'tool',
            'https://pmkusum.mnre.gov.in/',
            'https://images.unsplash.com/photo-1563514227147-6d2ff665a6a0?auto=format&fit=crop&w=600&q=80',
            'Category: Smart Micro-Irrigation | Solar Capacity: 3–7.5 HP | Discharge: Uniform Drip',
            'Small, marginal and commercial farmers with available borewell or pond source.',
            'Up to 90% water saving, zero electricity bills, and eligible for 60% PM-KUSUM subsidy.',
            'Ministry of New & Renewable Energy (MNRE)', 210
        ),
        (
            'Agricultural Drone Sprayer (कृषि ड्रोन)',
            '10L to 16L precision drone system equipped with centrifugal nozzles for ultra-low volume foliar spraying and crop health mapping.',
            5, 'Smart Farming Devices', 'tool',
            'https://agrimachinery.nic.in/',
            'https://images.unsplash.com/photo-1508614589041-895b88991e3e?auto=format&fit=crop&w=600&q=80',
            'Category: Smart Agri-Tech | Payload: 10–16 Litres | Coverage: 1 Acre in 7 minutes',
            'Progressive farmers, FPOs, Custom Hiring Centres, and Agriculture Graduates.',
            'Eliminates chemical exposure for laborers, reduces pesticide consumption by up to 30%.',
            'Sub-Mission on Agricultural Mechanization (SMAM)', 320
        ),
        (
            'Power Tiller / Mini Cultivator (पावर टिलर)',
            'Compact, two-wheeled walk-behind tractor ideal for inter-cultivation, weeding in orchards, and puddling in small paddy fields.',
            7, 'Tractors & Machinery', 'tool',
            'https://farmech.dac.gov.in/',
            'https://images.unsplash.com/photo-1500937386664-56d1dfef3854?auto=format&fit=crop&w=600&q=80',
            'Category: Compact Machinery | Power: 8–15 HP Diesel | Weight: 120–250 kg',
            'Highly suited for smallholders, hilly terrains, vegetable growers, and orchard owners.',
            'Low purchase cost, highly maneuverable in tight rows where full tractors cannot enter.',
            'Ministry of Agriculture & Farmers Welfare', 165
        ),
        (
            'Laser Land Leveler (लेजर लैंड लेवलर)',
            'Precision laser-guided bucket scraper ensuring accurate topographic leveling across the entire cultivation field.',
            7, 'Tractors & Machinery', 'tool',
            'https://agrimachinery.nic.in/',
            'https://images.unsplash.com/photo-1592982537447-7440770cbfc9?auto=format&fit=crop&w=600&q=80',
            'Category: Precision Grading | Laser Range: 300–400m | Power Requirement: 50+ HP Tractor',
            'Custom Hiring Centers (CHCs), farmer groups, and large-scale cultivators.',
            'Reduces irrigation water usage by 25-30%, enhances fertilizer efficiency and uniformity.',
            'ICAR / SMAM Custom Hiring Center Portal', 95
        ),
        (
            'Multi-Crop Happy Seeder / Super Seeder',
            'Tractor implement designed to sow wheat and seeds directly into standing paddy stubble without burning crop residue.',
            7, 'Tractors & Machinery', 'tool',
            'https://agrimachinery.nic.in/',
            'https://images.unsplash.com/photo-1625246333195-78d9c38ad449?auto=format&fit=crop&w=600&q=80',
            'Category: Zero-Till Seeding | Tractor: 50–65 HP | Action: Stubble Shredding + Seed Drilling',
            'Farmers in paddy-wheat cropping zones (Punjab, Haryana, UP, MP).',
            'Zero stubble burning, preserves soil moisture, adds organic mulch, earns carbon credits.',
            'Central Crop Residue Management Scheme (CRM)', 180
        ),
        (
            'Battery Powered Knapsack Sprayer',
            '16-liter ergonomic backpack sprayer with 12V lithium-ion battery and dual pressure regulators for uniform field application.',
            5, 'Sprayers', 'tool',
            'https://agricoop.nic.in/',
            'https://images.unsplash.com/photo-1586771107445-d3ca888129ff?auto=format&fit=crop&w=600&q=80',
            'Category: Hand & Power Sprayers | Tank: 16–20 Litres | Battery: 12V 8Ah / 12Ah',
            'All small and marginal farmers.',
            'Zero manual pumping fatigue, 5 hours continuous spray per charge, adjustable brass nozzles.',
            'National Food Security Mission (NFSM)', 240
        ),

        # --- GOVERNMENT SCHEMES ---
        (
            'PM-KISAN (Pradhan Mantri Kisan Samman Nidhi)',
            'Central sector scheme providing income support to all landholding farmer families across India to supplement their agricultural financial needs.',
            8, 'Income Support', 'scheme',
            'https://pmkisan.gov.in/',
            'https://images.unsplash.com/photo-1560493676-04071c5f467b?auto=format&fit=crop&w=600&q=80',
            'Sector: Central Government | Mode: Direct Benefit Transfer (DBT) via Aadhaar',
            'All landholding farmer families with cultivable land in their names (subject to official exclusion criteria).',
            'Rs. 6,000 per year paid in three equal 4-monthly installments of Rs. 2,000 directly into verified bank accounts.',
            'Ministry of Agriculture & Farmers Welfare', 510
        ),
        (
            'PMFBY (Pradhan Mantri Fasal Bima Yojana)',
            'Comprehensive crop insurance scheme protecting farmers against non-preventable natural risks from pre-sowing to post-harvest stages.',
            9, 'Crop Insurance', 'scheme',
            'https://pmfby.gov.in/',
            'https://images.unsplash.com/photo-1500382017468-9049fed747ef?auto=format&fit=crop&w=600&q=80',
            'Sector: National Crop Insurance | Premium: 2% Kharif, 1.5% Rabi, 5% Commercial',
            'All farmers growing notified crops in notified areas (both loanee and non-loanee farmers).',
            'Comprehensive financial compensation for yield loss, localized calamities, post-harvest losses, and unseasonal rains.',
            'Department of Agriculture & Farmers Welfare', 430
        ),
        (
            'PMKSY (Pradhan Mantri Krishi Sinchayee Yojana)',
            'Flagship irrigation initiative with the motto "Har Khet Ko Pani" and "Per Drop More Crop" promoting precision micro-irrigation systems.',
            6, 'Irrigation', 'scheme',
            'https://pmksy.gov.in/',
            'https://images.unsplash.com/photo-1563514227147-6d2ff665a6a0?auto=format&fit=crop&w=600&q=80',
            'Sector: Water Infrastructure & Efficiency | Coverage: Pan-India',
            'Individual farmers, self-help groups, cooperative societies, and water user associations.',
            'Up to 45% to 55% capital subsidy on installation of Drip & Sprinkler irrigation systems as per state guidelines.',
            'Ministry of Jal Shakti & Ministry of Agriculture', 315
        ),
        (
            'Paramparagat Krishi Vikas Yojana (PKVY)',
            'Dedicated sub-component of National Mission on Sustainable Agriculture promoting certified organic farming through cluster approach.',
            11, 'Farmer Welfare', 'scheme',
            'https://pgsindia-ncof.gov.in/',
            'https://images.unsplash.com/photo-1592982537447-7440770cbfc9?auto=format&fit=crop&w=600&q=80',
            'Sector: Sustainable Agriculture | Certification: PGS-India Certified Organic',
            'Farmer clusters forming groups of 20 or more farmers holding contiguous land.',
            'Financial assistance of Rs. 50,000 per hectare over 3 years for inputs, bio-fertilizers, and organic certification.',
            'National Centre of Organic and Natural Farming (NCONF)', 270
        ),
        (
            'Soil Health Card Scheme (मृदा स्वास्थ्य कार्ड)',
            'Government program issuing comprehensive soil test reports detailing 12 critical macro and micro nutrient parameters with crop-specific fertilizer recommendations.',
            11, 'Farmer Welfare', 'scheme',
            'https://soilhealth.dac.gov.in/',
            'https://images.unsplash.com/photo-1464226184884-fa280b87c399?auto=format&fit=crop&w=600&q=80',
            'Sector: Soil Nutrient Governance | Cycle: Every 2 Years Soil Testing',
            'All farmers across all agricultural blocks in India.',
            'Free soil nutrient testing, reduction in excessive chemical fertilizer costs, and optimized crop productivity.',
            'Department of Agriculture & Farmers Welfare', 290
        ),
        (
            'Sub-Mission on Agricultural Mechanization (SMAM)',
            'Scheme aimed at increasing farm power availability and establishing Custom Hiring Centres (CHCs) for modern farm machinery.',
            7, 'Agricultural Infrastructure', 'scheme',
            'https://agrimachinery.nic.in/',
            'https://images.unsplash.com/photo-1589820296156-2454bb8a6ad1?auto=format&fit=crop&w=600&q=80',
            'Sector: Mechanization & Technology | Subsidy: 40% to 50% on Implements',
            'Individual farmers, SC/ST, women farmers, cooperative societies, and rural entrepreneurs.',
            'Substantial subsidy on tractors, rotavators, power weeders, harvesters, and up to 80% for custom hiring hubs.',
            'Ministry of Agriculture & Farmers Welfare', 345
        ),

        # --- LOANS & SUBSIDIES ---
        (
            'Kisan Credit Card (KCC / किसान क्रेडिट कार्ड)',
            'Provides adequate and timely institutional credit to farmers under single window for cultivation expenses, post-harvest needs, and working capital.',
            10, 'Credit Support', 'loan',
            'https://www.myscheme.gov.in/schemes/kcc',
            'https://images.unsplash.com/photo-1559526324-4b87b5e36e44?auto=format&fit=crop&w=600&q=80',
            'Type: Concessional Working Capital Credit | Limit: Based on Cropping Pattern',
            'All individual/joint cultivators, tenant farmers, oral lessees, sharecroppers, and SHGs.',
            'Short-term credit up to Rs. 3 Lakh at effective interest rate of 4% per annum (with prompt repayment subvention as per RBI norms).',
            'Reserve Bank of India (RBI) & NABARD', 620
        ),
        (
            'Agriculture Infrastructure Fund (AIF)',
            'Medium to long term debt financing facility for investment in viable post-harvest management infrastructure and community farming assets.',
            10, 'Agricultural Infrastructure', 'loan',
            'https://agriinfra.dac.gov.in/',
            'https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?auto=format&fit=crop&w=600&q=80',
            'Type: Long Term Debt Facility | Fund Size: Rs. 1 Lakh Crore',
            'Primary Agricultural Credit Societies (PACS), FPOs, Agri-entrepreneurs, and Startups.',
            '3% interest subvention per annum for loans up to Rs. 2 Crore for a maximum period of 7 years, plus CGTMSE credit guarantee.',
            'Ministry of Agriculture & NABARD', 185
        ),
        (
            'Micro Irrigation Capital Subsidy',
            'State & Central combined subsidy scheme providing upfront assistance for installing drip, micro-sprinklers, and portable sprinkler sets.',
            6, 'Subsidy', 'loan',
            'https://pmksy.gov.in/',
            'https://images.unsplash.com/photo-1563514227147-6d2ff665a6a0?auto=format&fit=crop&w=600&q=80',
            'Type: Capital Subsidy | Share: 55% for Small/Marginal, 45% for Other Farmers',
            'Cultivators having verified land ownership with available irrigation water source.',
            'Direct release of subsidy to certified manufacturer vendors; drastic reduction in farmer out-of-pocket setup cost.',
            'State Horticulture & Agriculture Departments', 230
        ),
        (
            'PM-KUSUM Solar Pump Subsidy Scheme',
            'Solarization scheme enabling farmers to replace diesel irrigation pumps with standalone off-grid solar pumps and grid-connected solar power systems.',
            6, 'Subsidy', 'loan',
            'https://pmkusum.mnre.gov.in/',
            'https://images.unsplash.com/photo-1509391365360-2e959784a276?auto=format&fit=crop&w=600&q=80',
            'Type: 60% Total Government Subsidy (30% Central + 30% State)',
            'Individual farmers, groups, cooperatives, and water user associations with water source.',
            'Get 3 HP to 10 HP solar pumps with only 10% farmer contribution (up to 30% available via bank loan).',
            'Ministry of New & Renewable Energy (MNRE)', 410
        ),

        # --- FARMING KNOWLEDGE RESOURCES & GUIDES ---
        (
            'Complete Guide to Zero Budget Natural Farming (ZBNF)',
            'Comprehensive manual on chemical-free agriculture utilizing indigenous cow dung-urine formulations like Jeevamrit, Beejamrit, Mulching, and Waaphasa.',
            11, 'Organic Farming', 'guide',
            'https://icar.org.in/',
            'https://images.unsplash.com/photo-1592982537447-7440770cbfc9?auto=format&fit=crop&w=600&q=80',
            'Category: Natural & Organic Farming | Topic: Microbial Bio-Formulations',
            'Applicable to all agro-ecological zones and cropping systems.',
            'Cuts cultivation costs, improves soil biology, and produces residue-free organic crops.',
            'National Centre of Organic and Natural Farming', 380
        ),
        (
            'Soil Health Management & Organic Vermicomposting',
            'Practical step-by-step techniques to test soil texture, balance pH, and build on-farm vermicompost units using Eisenia fetida earthworms.',
            11, 'Soil Management', 'guide',
            'https://soilhealth.dac.gov.in/',
            'https://images.unsplash.com/photo-1464226184884-fa280b87c399?auto=format&fit=crop&w=600&q=80',
            'Category: Soil Science | Topic: Organic Humus & Earthworm Composting',
            'Useful for all farmers wanting to convert agricultural waste into organic manure.',
            'Increases water holding capacity, replenishes organic carbon, and reduces chemical fertilizer requirement.',
            'ICAR - Indian Institute of Soil Science (IISS)', 295
        ),
        (
            'Integrated Pest Management (IPM) in Vegetable Crops',
            'Modern holistic pest control combining yellow sticky traps, pheromone lures, trichoderma bio-agents, and neem-based botanical sprays.',
            11, 'Pest Control', 'guide',
            'https://ncipm.icar.gov.in/',
            'https://images.unsplash.com/photo-1592924357228-91a4daadcfea?auto=format&fit=crop&w=600&q=80',
            'Category: Crop Protection | Topic: Biological & Cultural Pest Control',
            'Targeted for tomato, brinjal, chilli, okra, and cucurbit vegetable growers.',
            'Prevents pest resistance, keeps harvest safe from excessive pesticide residues, and safeguards beneficial pollinators.',
            'ICAR - National Research Centre for Integrated Pest Management (NCIPM)', 210
        ),
        (
            'Drip Fertigation & Precision Water Scheduling',
            'Scientific guidelines on calculating crop water requirements (Etc), injecting water-soluble fertilizers directly through drip lines, and venturi operation.',
            6, 'Irrigation', 'guide',
            'https://iihr.res.in/',
            'https://images.unsplash.com/photo-1563514227147-6d2ff665a6a0?auto=format&fit=crop&w=600&q=80',
            'Category: Precision Irrigation | Topic: Water-Soluble Fertigation',
            'Orchards, sugarcane, cotton, and high-value horticultural crops.',
            'Significantly reduces fertilizer wastage, prevents nutrient leaching, and increases crop yields by 25-35%.',
            'Precision Farming Development Centres (PFDC)', 175
        ),
        (
            'Scientific Crop Rotation & Green Manuring Strategies',
            'Methods for alternating deep-rooted tap crops with fibrous cereals and cultivating Dhaincha / Sunnhemp as green manure to fix nitrogen.',
            11, 'Crop Rotation', 'guide',
            'https://icar.org.in/',
            'https://images.unsplash.com/photo-1500382017468-9049fed747ef?auto=format&fit=crop&w=600&q=80',
            'Category: Agronomy | Topic: Legume Incorporation & Soil Rejuvenation',
            'Farmers practicing monoculture or intensive cereal rotations.',
            'Breaks pest-weed cycles, enhances soil organic nitrogen naturally.',
            'ICAR - Indian Agricultural Research Institute (IARI Pusa)', 160
        ),

        # --- MARKETPLACES & COMMODITY PLATFORMS ---
        (
            'e-NAM (National Agriculture Market)',
            'Pan-India electronic trading portal networking the existing APMC mandis to create a unified national market for agricultural commodities.',
            12, 'Mandi & Marketplace', 'marketplace',
            'https://www.enam.gov.in/',
            'https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=600&q=80',
            'Platform Type: National Electronic Mandi Auction | Commodities: 200+ Agri Goods',
            'All registered farmers, traders, FPOs, and commission agents.',
            'Transparent online bidding, real-time price discovery, assaying quality reports, and direct bank settlement.',
            'Small Farmers Agribusiness Consortium (SFAC)', 580
        ),
        (
            'Agmarknet Portal (Mandi Price Tracker)',
            'Official agricultural marketing information network providing daily arrival volumes and wholesale commodity prices across 3,000+ Indian mandis.',
            12, 'Agricultural Market Prices', 'marketplace',
            'https://agmarknet.gov.in/',
            'https://images.unsplash.com/photo-1488459716781-31db52582fe9?auto=format&fit=crop&w=600&q=80',
            'Platform Type: Daily Wholesale Market Rates Information System',
            'All farmers tracking mandi price trends before selling produce.',
            'Accurate daily spot prices for cereals, pulses, fruits, and vegetables by district and market yard.',
            'Directorate of Marketing & Inspection (DMI)', 470
        ),
        (
            'IFFCO Kisan E-Bazar (IFFCO E-Bazar)',
            'Direct online delivery platform by India’s premier cooperative for certified bio-fertilizers, nano urea, seeds, cattle feed, and farm implements.',
            12, 'Buy Seeds & Fertilizers', 'marketplace',
            'https://www.iffcobazar.in/',
            'https://images.unsplash.com/photo-1595974482597-4b8da8879bc5?auto=format&fit=crop&w=600&q=80',
            'Platform Type: Official Cooperative Agri-Input E-Store',
            'Farmers across all postal pin codes in India.',
            'Guaranteed genuine certified inputs, free home delivery, and subsidized cooperative pricing.',
            'Indian Farmers Fertiliser Cooperative Limited (IFFCO)', 390
        ),
        (
            'AgroStar / BigHaat Agri Retail Store',
            'Leading digital agtech platforms providing door-step delivery of branded hybrid seeds, agrochemicals, knapsack sprayers, and tarpaulins.',
            12, 'Buy Equipment & Seeds', 'marketplace',
            'https://www.bighaat.com/',
            'https://images.unsplash.com/photo-1586771107445-d3ca888129ff?auto=format&fit=crop&w=600&q=80',
            'Platform Type: Agri-Tech Direct-to-Farmer Commerce',
            'Farmers seeking door delivery of agricultural inputs with cash-on-delivery options.',
            'Large catalog of reputable seed companies, crop advisory support, and equipment accessories.',
            'Agro-Retail Tech Network', 290
        ),

        # --- COMMUNITY & HELPLINES ---
        (
            'Kisan Call Centre (Toll-Free Helpline: 1800-180-1551)',
            'Round-the-clock telephone advisory service answering farmer queries in 22 local Indian languages by agricultural subject matter specialists.',
            8, 'Agricultural Helplines', 'community',
            'https://dackkms.gov.in/',
            'https://images.unsplash.com/photo-1577563908411-5077b6dc7624?auto=format&fit=crop&w=600&q=80',
            'Service Type: 24x7 Toll-Free Voice Advisory | Languages: 22 Regional Languages',
            'Any farmer across India calling from mobile or landline.',
            'Instant expert advice on disease outbreaks, pest alerts, weather contingencies, and scheme documentation.',
            'Ministry of Agriculture & Farmers Welfare', 650
        ),
        (
            'Krishi Vigyan Kendra (KVK) National Network',
            '730+ district-level agricultural science centers conducting on-farm trials, frontline demonstrations, and skill training for local farmers.',
            11, 'Krishi Vigyan Kendras', 'community',
            'https://kvk.icar.gov.in/',
            'https://images.unsplash.com/photo-1531482615713-2afd69097998?auto=format&fit=crop&w=600&q=80',
            'Institution: ICAR District Agricultural Extension Centres',
            'Local rural youth, farm women, progressive growers, and SHGs.',
            'Free training workshops, supply of quality breeder seeds/saplings, and diagnostic farm visits.',
            'Indian Council of Agricultural Research (ICAR)', 420
        ),
        (
            'ICAR Central Agricultural Research Institutes',
            'Network of premier apex agricultural research institutes developing high-yielding climate-resilient crop varieties and technology packages.',
            1, 'Agricultural Universities', 'community',
            'https://icar.org.in/',
            'https://images.unsplash.com/photo-1523240795612-9a054b0db644?auto=format&fit=crop&w=600&q=80',
            'Apex Body: Indian Council of Agricultural Research (ICAR)',
            'Researchers, farmers, students, and agricultural policy makers.',
            'Access to published research bulletins, variety release notifications, and national seed portals.',
            'ICAR Headquarters, Krishi Bhawan, New Delhi', 310
        )
    ]

    for r in resources_data:
        existing = cursor.execute("SELECT id FROM resources WHERE title = ?", (r[0],)).fetchone()
        if not existing:
            cursor.execute("""
            INSERT INTO resources (
                title, description, category_id, category_name, resource_type,
                external_url, image_url, season_climate, eligibility, benefits,
                provider, views_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, r)

    # Map usernames to user IDs for reliable foreign key seeding
    user_id_map = {}
    for row in cursor.execute("SELECT id, username FROM users").fetchall():
        user_id_map[row['username']] = row['id']

    ramesh_id = user_id_map.get('ramesh_kumar', 1)
    sunita_id = user_id_map.get('sunita_devi', 2)
    balwinder_id = user_id_map.get('balwinder_singh', 3)

    # 4. Seed Bookmarks
    bookmarks_data = [
        (ramesh_id, 1), # Ramesh saved Rice
        (ramesh_id, 2), # Ramesh saved Wheat
        (ramesh_id, 18), # Ramesh saved PM-KISAN
        (ramesh_id, 24), # Ramesh saved KCC
        (sunita_id, 28), # Sunita saved ZBNF
        (sunita_id, 29), # Sunita saved Soil Health
        (balwinder_id, 11), # Balwinder saved Rotavator
    ]
    for b in bookmarks_data:
        existing = cursor.execute("SELECT id FROM bookmarks WHERE user_id = ? AND resource_id = ?", b).fetchone()
        if not existing:
            try:
                cursor.execute("INSERT INTO bookmarks (user_id, resource_id) VALUES (?, ?)", b)
            except Exception:
                pass

    # 5. Seed Feedback & Ratings
    feedback_data = [
        (ramesh_id, 18, 5, 'PM-KISAN DBT installment was credited directly on time. Very helpful summary of documentation criteria!'),
        (sunita_id, 28, 5, 'Jeevamrit preparation steps are explained clearly. Practicing natural farming in our 3-acre orchard.'),
        (balwinder_id, 11, 4, 'Rotavator implement specifications helped me choose the right HP tractor attachment.'),
        (ramesh_id, 24, 5, 'Applied for Kisan Credit Card renewal with subvention benefit through our local gramin bank.')
    ]
    for fb in feedback_data:
        existing = cursor.execute("SELECT id FROM feedback WHERE user_id = ? AND resource_id = ?", (fb[0], fb[1])).fetchone()
        if not existing:
            try:
                cursor.execute("INSERT INTO feedback (user_id, resource_id, rating, comment) VALUES (?, ?, ?, ?)", fb)
            except Exception:
                pass

    # 6. Seed Community Posts
    posts_data = [
        (ramesh_id, 'Best organic pest control for leaf curl in tomato?', 'Pest Control', 'Hello fellow farmers, I am noticing yellow leaf curl virus and whiteflies on my 2-month-old tomato plants in Punjab. Has anyone tried yellow sticky traps or neem oil emulsion (10,000 ppm) with success? Would love your recommendations on dosage.'),
        (sunita_id, 'Drip irrigation subsidy application procedure through PMKSY', 'Irrigation & Subsidies', 'We recently got our 4-acre guava orchard surveyed for drip installation under PM Krishi Sinchayee Yojana. For those who completed the subsidy process: how long did the physical inspection take after submitting the online 7/12 land extract?'),
        (balwinder_id, 'Wheat variety recommendation for timely sown irrigated conditions in Rabi', 'Seeds & Crops', 'Looking for high-yield, yellow rust-resistant wheat varieties for the upcoming Rabi season in Haryana. Considering HD-2967 vs HD-3086 or DBW-187 (Karan Vandana). What has been your average yield per acre?')
    ]
    for p in posts_data:
        existing = cursor.execute("SELECT id FROM community_posts WHERE title = ?", (p[1],)).fetchone()
        if not existing:
            try:
                cursor.execute("INSERT INTO community_posts (user_id, title, category, content) VALUES (?, ?, ?, ?)", p)
            except Exception:
                pass

    # 7. Seed Comments
    comments_data = [
        (1, sunita_id, 'Neem oil spray (5ml per litre with mild soap surfactant) sprayed every 7 days along with 10 yellow sticky traps per acre worked very well for my tomato plot!'),
        (1, balwinder_id, 'Also make sure to destroy any weed hosts around the field borders where whitefly colonies shelter.'),
        (2, ramesh_id, 'In our district, the horticulture officer conducted site inspection within 14 working days. Keep your water source electricity connection certificate ready.'),
        (3, sunita_id, 'DBW-187 (Karan Vandana) gave us 24 quintals per acre last season with proper two split doses of urea and timely terminal irrigation.')
    ]
    for c in comments_data:
        existing = cursor.execute("SELECT id FROM comments WHERE post_id = ? AND user_id = ? AND comment = ?", c).fetchone()
        if not existing:
            try:
                cursor.execute("INSERT INTO comments (post_id, user_id, comment) VALUES (?, ?, ?)", c)
            except Exception:
                pass

    # 8. Seed Likes
    likes_data = [
        (1, ramesh_id),
        (1, sunita_id),
        (1, balwinder_id),
        (2, sunita_id),
        (2, balwinder_id),
        (3, ramesh_id),
        (3, sunita_id)
    ]
    for l in likes_data:
        existing = cursor.execute("SELECT id FROM likes WHERE post_id = ? AND user_id = ?", l).fetchone()
        if not existing:
            try:
                cursor.execute("INSERT INTO likes (post_id, user_id) VALUES (?, ?)", l)
            except Exception:
                pass

    conn.commit()

if __name__ == '__main__':
    import sys
    force = '--reset' in sys.argv or '-r' in sys.argv
    init_db(force_reset=force)

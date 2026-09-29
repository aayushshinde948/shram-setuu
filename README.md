# Shram setuu (किसान सहायक)
> **“Smart Resources. Better Farming. Stronger Farmers.”**

A modern, responsive web application and agriculture resource platform designed specifically for Indian farmers. Shram setuu acts as a centralized digital portal connecting cultivators with verified government schemes, high-yield crop guides, modern farming machinery, regional weather advisories, trusted agricultural marketplaces, and an active farmer community forum.

---

## 🌟 Key Features

### 1. 🌾 Seeds & Crops Directory
* Comprehensive cultivation guides for staple cereals, pulses, vegetables, oilseeds, and cash crops (Rice, Wheat, Maize, Cotton, Sugarcane, Tomato, Potato, Mustard, Soybean, Chickpea, etc.).
* Agro-climatic data: temperature range, rainfall requirement, soil suitability, and season markers (Kharif / Rabi / Zaid).
* Direct links to ICAR (Indian Council of Agricultural Research) apex institutes.

### 2. 🚜 Modern Farming Tools & Equipment
* Implements directory covering Tractor Rotavators, Solar Drip Irrigation Units, Precision Agricultural Drone Sprayers, Power Tillers, Laser Land Levelers, and Super Seeders.
* Specifications, horsepower requirements, and Sub-Mission on Agricultural Mechanization (SMAM) subsidy details.

### 3. 🏛️ Government Schemes & Welfare Portal
* Verified information on flagship programs: **PM-KISAN**, **PMFBY** (Crop Insurance), **PMKSY** (Per Drop More Crop), **Paramparagat Krishi Vikas Yojana (PKVY)**, and **Soil Health Card Scheme**.
* Clear eligibility criteria, financial benefits breakdown, and direct buttons to official central/state portals (`.gov.in` / `.nic.in`).

### 4. 💳 Loans & Financial Subsidies
* Concessional **Kisan Credit Card (KCC)** interest subvention rules.
* **Agriculture Infrastructure Fund (AIF)**, NABARD long-term credit facilities, and **PM-KUSUM** solar pump support information.

### 5. 📖 Farming Knowledge Hub
* Step-by-step agronomic manuals on Zero Budget Natural Farming (ZBNF), Integrated Pest Management (IPM), Vermicomposting, Drip Fertigation, and Scientific Crop Rotation.

### 6. 🌦️ Interactive Weather & Agro-Advisories
* Regional weather forecast covering major Indian agricultural belts.
* Live weather integration via Open-Meteo API + calibrated seasonal fallback.
* **Automated Agricultural Advisories**: Actionable alerts on pesticide wash-off risks, irrigation scheduling, and high wind crop protection.

### 7. 🏪 Marketplace & Mandi Price Tracker
* Directory of verified agricultural buying and selling platforms: **e-NAM**, **Agmarknet**, **IFFCO Kisan E-Bazar**, **AgroStar**, **BigHaat**.
* **Daily APMC Mandi Spot Rate Indicator** showing current modal market rates for key commodities across Indian states.

### 8. 👥 Farmer Community & Helplines
* 24x7 National Kisan Call Center Toll-Free Helpline: `1800-180-1551`.
* Network of Krishi Vigyan Kendras (KVKs).
* **Interactive Discussion Forum**: Logged-in farmers can post agricultural doubts, reply in comment threads, and like posts in real time.

### 9. 📊 Farmer Dashboard & Personal Bookmarks
* Personalized welcome banner with state & farming preference indicator.
* Saved Resources page isolating bookmarks per user.
* Quick access tiles to all major features.

### 10. 🛡️ Administrator Control Center
* Full CRUD management of agricultural resources, government schemes, tools, and crop guides.
* User management and role switching (`user` / `admin`).
* Community post moderation and user feedback review.
* Real-time platform KPI metrics.

---

## 🛠️ Technology Stack

* **Backend**: Python 3, Flask, Werkzeug (PBKDF2 SHA-256 secure password hashing)
* **Database**: SQLite3 with normalized tables and foreign key constraints
* **Frontend**: Responsive HTML5, Custom Agri-Themed CSS Grid & Flexbox, Vanilla JS
* **Typography & Icons**: Google Fonts (Plus Jakarta Sans), Font Awesome 6
* **APIs**: Open-Meteo Agro-Meteorology API

---

## 🚀 Getting Started & Installation

### 1. Prerequisites
* Python 3.8+ installed on your system.

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Initialize the SQLite Database
```bash
python init_db.py
```

The application creates a local database automatically. **The database file is intentionally excluded from Git because it may contain user-generated data.**

### 4. Run the Flask Web Application
```bash
python app.py
```

Open your browser and navigate to:
```text
http://127.0.0.1:5000
```

---

## 🔒 Administrator & Environment Configuration

Admin access is controlled through environment variables rather than hardcoded production credentials:

| Variable | Required | Description |
| :--- | :--- | :--- |
| `ADMIN_USERNAME` | Yes (for admin access) | Administrator username |
| `ADMIN_PASSWORD` | Yes (for admin access) | Strong administrator password |
| `SECRET_KEY` | Recommended in production | Secret key for session security and CSRF protection |
| `FLASK_DEBUG` | Optional | Set to `True` for local debugging only |

Create a local `.env` or environment configuration as appropriate for your deployment. **Never commit real credentials or `.env` files.**

### 🌾 Demo Accounts
No production/demo account passwords are published in this repository. Register a new farmer account locally, or configure a test-only demo account through environment variables when running the automated test suite.

---

## 🧪 Running Automated Tests
```bash
python test_app.py
```

The test suite uses an isolated temporary SQLite database and environment-based admin authentication.

---

## ⚖️ Disclaimer
Information displayed on Shram setuu is compiled for educational and informational purposes. Shram setuu redirects farmers toward authorized official government websites and services. Users should verify official scheme guidelines, eligibility rules, and documentation requirements from the respective official department portals.

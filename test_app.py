"""
Automated Test Suite for Shram setuu Web Application
Isolated Test Database Environment with Secure Environment-based Admin Authentication
"""

import os
import shutil
import tempfile
import unittest
import json
import uuid

# Configure isolated test database environment and admin environment variables
TEMP_TEST_DIR = tempfile.mkdtemp()
TEST_DB_PATH = os.path.join(TEMP_TEST_DIR, 'test_kisan.db')
os.environ['KISAN_DB_PATH'] = TEST_DB_PATH
os.environ['ADMIN_USERNAME'] = 'custom_admin'
os.environ['ADMIN_PASSWORD'] = 'SecureAdminPass2026!'

from app import app
from database import init_db

class ShramSetuuTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        init_db(force_reset=True)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEMP_TEST_DIR):
            shutil.rmtree(TEMP_TEST_DIR, ignore_errors=True)

    def setUp(self):
        self.client = app.test_client()

    def test_01_database_and_homepage(self):
        """Test homepage rendering and dynamic statistics."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Shram setuu', response.data)
        self.assertIn(b'Empowering Farmers with the', response.data)
        self.assertIn(b'Right Resources', response.data)
        self.assertIn(b'Everything a Farmer Needs', response.data)
        self.assertIn(b'PM-KISAN', response.data)

    def test_02_public_pages(self):
        """Test all public resource directory pages."""
        pages = ['/crops', '/tools', '/schemes', '/loans', '/resources', '/weather', '/marketplace', '/community']
        for page in pages:
            with self.subTest(page=page):
                res = self.client.get(page)
                self.assertEqual(res.status_code, 200, f"Failed on page {page}")

    def test_03_search_and_filters(self):
        """Test search and category filtering on crops and schemes."""
        res = self.client.get('/crops?q=Wheat')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Wheat', res.data)

        res = self.client.get('/schemes?cat=Income+Support')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'PM-KISAN', res.data)

    def test_04_authentication_flow(self):
        """Test user registration and login."""
        uid = uuid.uuid4().hex[:6]
        username = f'farmer_{uid}'
        email = f'farmer_{uid}@testagri.in'

        # Register new farmer
        reg_res = self.client.post('/register', data={
            'full_name': 'Gurpreet Singh',
            'username': username,
            'email': email,
            'password': 'secretfarmer123',
            'confirm_password': 'secretfarmer123',
            'state': 'Punjab',
            'preferred_category': 'Crops'
        }, follow_redirects=True)
        self.assertEqual(reg_res.status_code, 200)
        self.assertIn(b'Gurpreet Singh', reg_res.data)

        # Logout
        logout_res = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(logout_res.status_code, 200)
        self.assertIn(b'signed out safely', logout_res.data)

        # Login back
        login_res = self.client.post('/login', data={
            'username_or_email': username,
            'password': 'secretfarmer123'
        }, follow_redirects=True)
        self.assertEqual(login_res.status_code, 200)
        self.assertIn(b'Gurpreet Singh', login_res.data)

    def test_05_farmer_dashboard_and_bookmarks(self):
        """Test bookmarking flow and user-specific dashboard."""
        self.client.post('/login', data={'username_or_email': 'demo_farmer_1', 'password': 'DemoFarmer2026!'})

        dash_res = self.client.get('/dashboard')
        self.assertEqual(dash_res.status_code, 200)
        self.assertIn(b'Welcome back, Demo Farmer One!', dash_res.data)

        bm_res = self.client.post('/api/bookmark/toggle', 
                                  data=json.dumps({'resource_id': 3}), 
                                  content_type='application/json',
                                  headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(bm_res.status_code, 200)
        data = json.loads(bm_res.data)
        self.assertEqual(data['status'], 'success')

        b_page = self.client.get('/bookmarks')
        self.assertEqual(b_page.status_code, 200)
        self.assertIn(b'Saved Agriculture Resources', b_page.data)

    def test_06_community_post_and_comment(self):
        """Test community Q&A, comments, and likes."""
        self.client.post('/login', data={'username_or_email': 'demo_farmer_1', 'password': 'DemoFarmer2026!'})

        post_res = self.client.post('/community', data={
            'title': 'How to control fall armyworm in maize?',
            'category': 'Pest Control & Diseases',
            'content': 'Looking for biological control methods using Trichogramma egg parasitoids.'
        }, follow_redirects=True)
        self.assertEqual(post_res.status_code, 200)
        self.assertIn(b'fall armyworm in maize', post_res.data)

        like_res = self.client.post('/api/community/like/1', headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(like_res.status_code, 200)
        like_data = json.loads(like_res.data)
        self.assertEqual(like_data['status'], 'success')

    def test_07_rating_and_feedback(self):
        """Test star rating and feedback submission."""
        self.client.post('/login', data={'username_or_email': 'demo_farmer_1', 'password': 'DemoFarmer2026!'})
        
        fb_res = self.client.post('/api/rate-feedback', data={
            'resource_id': '1',
            'rating': '5',
            'comment': 'Detailed rice cultivation parameters helped plan Kharif nursery.'
        }, follow_redirects=True)
        self.assertEqual(fb_res.status_code, 200)
        self.assertIn(b'Thank you for rating and reviewing', fb_res.data)

    def test_08_admin_authorization_and_crud(self):
        """Test admin dashboard access, security against old credentials, and environment-based admin login."""
        # Non-admin farmer tries to access admin -> Denied
        self.client.post('/login', data={'username_or_email': 'demo_farmer_1', 'password': 'DemoFarmer2026!'})
        admin_deny = self.client.get('/admin', follow_redirects=True)
        self.assertIn(b'Access denied', admin_deny.data)

        self.client.get('/logout')

        # Test that old hardcoded admin / admin123 credentials FAIL
        legacy_res = self.client.post('/login', data={'username_or_email': 'admin', 'password': 'admin123'}, follow_redirects=True)
        self.assertIn(b'Invalid username/email or password', legacy_res.data)

        # Test that environment-based admin credentials SUCCEED
        admin_login = self.client.post('/login', data={'username_or_email': 'custom_admin', 'password': 'SecureAdminPass2026!'}, follow_redirects=True)
        self.assertEqual(admin_login.status_code, 200)
        self.assertIn(b'Admin Control Center', admin_login.data)

        # Add new resource via authenticated admin
        add_res = self.client.post('/admin/resource/add', data={
            'title': 'National Honey Mission Initiative',
            'resource_type': 'scheme',
            'category_name': 'Farmer Welfare',
            'description': 'Central sector scheme for promotion of scientific beekeeping.',
            'external_url': 'https://nbhm.gov.in',
            'image_url': 'https://images.unsplash.com/photo-1587049352846-4a222e784d38',
            'provider': 'National Bee Board',
            'eligibility': 'Farmers, beekeepers, SHGs, and cooperatives',
            'benefits': 'Up to 80% financial assistance for beekeeping kits'
        }, follow_redirects=True)
        self.assertEqual(add_res.status_code, 200)
        self.assertIn(b'National Honey Mission Initiative', add_res.data)
        self.assertIn(b'created successfully', add_res.data)

    def test_09_weather_endpoint(self):
        """Test regional weather forecasts for different Indian agricultural hubs."""
        for city in ['ludhiana', 'nashik', 'guntur', 'patna']:
            res = self.client.get(f'/weather?city={city}')
            self.assertEqual(res.status_code, 200)
            self.assertIn(b'5-Day Farm Weather Forecast', res.data)
            self.assertIn(b'Farming Weather Tips', res.data)

    def test_10_open_redirect_defense(self):
        """Verify login next parameter rejects external open redirects."""
        res = self.client.post('/login?next=https://evil.com', data={
            'username_or_email': 'demo_farmer_1',
            'password': 'DemoFarmer2026!'
        })
        self.assertNotEqual(res.location, 'https://evil.com')

    def test_11_error_handling_no_500(self):
        """Verify invalid IDs and endpoints return 400 or 404 cleanly without 500 error."""
        # Non-existent resource API
        res404 = self.client.get('/api/resource/999999')
        self.assertEqual(res404.status_code, 404)

        # Login as farmer
        self.client.post('/login', data={'username_or_email': 'demo_farmer_1', 'password': 'DemoFarmer2026!'})

        # Invalid resource ID format
        res400 = self.client.post('/api/bookmark/toggle',
                                  data=json.dumps({'resource_id': 'invalid_string'}),
                                  content_type='application/json',
                                  headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(res400.status_code, 400)

if __name__ == '__main__':
    unittest.main()

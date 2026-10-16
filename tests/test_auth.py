import pytest

def test_unauthenticated_access(client):
    """Test that protected routes redirect to login when unauthenticated."""
    protected_routes = ['/dashboard/', '/documents/']
    
    for route in protected_routes:
        response = client.get(route)
        # Flask-Login defaults to 302 redirect for unauthorized access
        assert response.status_code == 302
        assert '/auth/login' in response.location

def test_login_success(client, user_a):
    """Test successful login with correct credentials."""
    response = client.post('/auth/login', data={
        'email': 'usera@example.com',
        'password': 'password123'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    # Should be redirected to dashboard or contain some success indicator
    assert b'Logout' in response.data or b'Dashboard' in response.data

def test_login_failure(client, user_a):
    """Test login with incorrect password."""
    response = client.post('/auth/login', data={
        'email': 'usera@example.com',
        'password': 'wrongpassword'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    # Usually flashes a message or keeps user on login page
    assert b'Invalid email address or password' in response.data or b'Sign In' in response.data

def test_duplicate_email_registration(client, user_a):
    """Test that a user cannot register with an existing email."""
    response = client.post('/auth/register', data={
        'username': 'newuser',
        'email': 'usera@example.com',
        'password': 'password123',
        'confirm_password': 'password123'
    }, follow_redirects=True)
    
    # Should stay on registration page with error
    assert b'Email is already registered' in response.data or b'already exists' in response.data

def test_logout(client, user_a):
    """Test that logout successfully clears session and redirects to login."""
    # Login first
    client.post('/auth/login', data={
        'email': 'usera@example.com',
        'password': 'password123'
    })
    
    # Logout
    response = client.post('/auth/logout', follow_redirects=True)
    assert response.status_code == 200
    assert b'You have been logged out.' in response.data
    
    # Ensure protected route redirects to login
    protected_response = client.get('/dashboard/')
    assert protected_response.status_code == 302
    assert '/auth/login' in protected_response.location


def test_logout_with_remember_me_cookie(client, user_a):
    """Verify that logout invalidates session and clears remember-me cookie so user is not bounced back to dashboard."""
    # 1. Login with remember=True
    login_resp = client.post('/auth/login', data={
        'email': 'usera@example.com',
        'password': 'password123',
        'remember_me': 'y'
    })
    assert any('remember_token' in h for h in login_resp.headers.getlist('Set-Cookie'))

    # 2. Logout via POST
    logout_resp = client.post('/auth/logout')
    assert logout_resp.status_code == 302
    assert logout_resp.location.endswith('/auth/login') or logout_resp.location == '/auth/login'
    
    # Verify remember-me cookie is explicitly expired/cleared
    logout_cookies = logout_resp.headers.getlist('Set-Cookie')
    assert any('remember_token=;' in h for h in logout_cookies), "remember_token cookie was not cleared in logout response!"

    # 3. Following redirect to /auth/login must return HTTP 200, NOT redirect back to /dashboard/
    login_page_resp = client.get(logout_resp.location)
    assert login_page_resp.status_code == 200
    assert b'You have been logged out.' in login_page_resp.data
    assert b'Sign In' in login_page_resp.data

    # 4. Attempting to access dashboard must require authentication
    dash_resp = client.get('/dashboard/')
    assert dash_resp.status_code == 302
    assert '/auth/login' in dash_resp.location


def test_logout_get_method_rejected(client, user_a):
    """Verify GET /auth/logout is rejected with 405 Method Not Allowed and preserves authentication."""
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})

    # GET must fail with 405
    get_res = client.get('/auth/logout')
    assert get_res.status_code == 405

    # User remains authenticated
    dash_res = client.get('/dashboard/')
    assert dash_res.status_code == 200


def test_login_again_after_logout(client, user_a):
    """Verify that logging in again after logging out works normally."""
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})
    client.post('/auth/logout', follow_redirects=True)

    # Re-login
    relogin_resp = client.post('/auth/login', data={
        'email': 'usera@example.com',
        'password': 'password123'
    }, follow_redirects=True)
    assert relogin_resp.status_code == 200
    assert b'Dashboard' in relogin_resp.data or b'WORKSPACE' in relogin_resp.data


def test_logout_form_markup_in_sidebar(client, user_a):
    """Verify the sidebar contains a secure POST form with CSRF token and submit button."""
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})

    resp = client.get('/dashboard/')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')

    assert 'action="/auth/logout"' in html
    assert 'method="POST"' in html or 'method="post"' in html
    assert 'name="csrf_token"' in html
    assert 'logout-btn' in html
    assert 'Sign Out' in html


def test_cache_control_headers_protection(client, user_a):
    """Verify sensitive pages have no-cache headers while static assets remain cacheable."""
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})

    # Authenticated page must prohibit caching
    dash_resp = client.get('/dashboard/')
    assert 'no-store' in dash_resp.headers.get('Cache-Control', '')
    assert 'no-cache' in dash_resp.headers.get('Cache-Control', '')

    # Static file should not have no-store
    static_resp = client.get('/static/css/style.css')
    assert static_resp.status_code == 200
    assert 'no-store' not in static_resp.headers.get('Cache-Control', '')


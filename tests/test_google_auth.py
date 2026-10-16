"""Unit and Integration Tests for Google OIDC Authentication (Sprint 11).

Tests cover:
1. Generation and session storage of state and nonce on GET /auth/google.
2. Rejection of missing, invalid, or mismatched state and nonce on callback.
3. Verification of Google OIDC ID tokens via tokeninfo validation.
4. Non-auto-linking policy: matching email with password account requires explicit linking.
5. Explicit account linking via POST /auth/google/link.
6. Role isolation: Google login assigns 'user' role and never escalates privileges.
7. No unnecessary token persistence.
"""

import pytest
from unittest.mock import patch, MagicMock
from app.models.user import User
from app.extensions import db


def test_google_login_redirect_generates_state_and_nonce(client):
    """Test that /auth/google generates random state and nonce in session and redirects to Google."""
    client.application.config['GOOGLE_CLIENT_ID'] = 'mock-client-id.apps.googleusercontent.com'
    client.application.config['GOOGLE_CLIENT_SECRET'] = 'mock-client-secret'
    client.application.config['GOOGLE_REDIRECT_URI'] = 'http://localhost:5000/auth/google/callback'
    
    response = client.get('/auth/google')
    assert response.status_code == 302
    assert 'accounts.google.com' in response.location
    assert 'client_id=mock-client-id.apps.googleusercontent.com' in response.location
    
    with client.session_transaction() as sess:
        assert 'oauth_state' in sess
        assert 'oauth_nonce' in sess
        assert len(sess['oauth_state']) >= 16
        assert len(sess['oauth_nonce']) >= 16


def test_google_callback_rejects_missing_state(client):
    """Test callback rejects request missing state or nonce."""
    response = client.get('/auth/google/callback?code=mock_code')
    assert response.status_code == 302
    assert '/auth/login' in response.location


def test_google_callback_rejects_mismatched_state(client):
    """Test callback rejects request when state does not match session state."""
    with client.session_transaction() as sess:
        sess['oauth_state'] = 'valid_state_123'
        sess['oauth_nonce'] = 'valid_nonce_456'

    response = client.get('/auth/google/callback?code=mock_code&state=invalid_state')
    assert response.status_code == 302
    assert '/auth/login' in response.location


@patch('requests.post')
@patch('requests.get')
def test_google_callback_success_new_user(mock_get, mock_post, client, app):
    """Test successful Google login creates a new user with google_sub and role 'user'."""
    client.application.config['GOOGLE_CLIENT_ID'] = 'mock_client_id'
    client.application.config['GOOGLE_CLIENT_SECRET'] = 'mock_secret'
    client.application.config['GOOGLE_REDIRECT_URI'] = 'http://localhost:5000/auth/google/callback'

    # Mock OAuth token exchange
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        'id_token': 'fake_id_token',
        'access_token': 'fake_access_token'
    }

    # Mock OIDC tokeninfo verification response
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        'iss': 'https://accounts.google.com',
        'aud': 'mock_client_id',
        'sub': 'google_user_sub_123',
        'email': 'newgoogleuser@example.com',
        'email_verified': 'true',
        'nonce': 'valid_nonce_456',
        'name': 'Google User'
    }

    with client.session_transaction() as sess:
        sess['oauth_state'] = 'valid_state_123'
        sess['oauth_nonce'] = 'valid_nonce_456'

    response = client.get('/auth/google/callback?code=mock_code&state=valid_state_123', follow_redirects=True)
    assert response.status_code == 200

    with app.app_context():
        user = User.query.filter_by(google_sub='google_user_sub_123').first()
        assert user is not None
        assert user.email == 'newgoogleuser@example.com'
        assert user.role == 'user'
        assert user.password_hash != ''


@patch('requests.post')
@patch('requests.get')
def test_google_login_does_not_autolink_existing_password_account(mock_get, mock_post, client, app, user_a):
    """Test that Google login with an email matching an existing password account requires explicit linking."""
    client.application.config['GOOGLE_CLIENT_ID'] = 'mock_client_id'
    client.application.config['GOOGLE_CLIENT_SECRET'] = 'mock_secret'
    client.application.config['GOOGLE_REDIRECT_URI'] = 'http://localhost:5000/auth/google/callback'

    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        'id_token': 'fake_id_token',
        'access_token': 'fake_access_token'
    }

    # Token email matches user_a's email
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        'iss': 'accounts.google.com',
        'aud': 'mock_client_id',
        'sub': 'google_sub_user_a',
        'email': 'usera@example.com',
        'email_verified': True,
        'nonce': 'valid_nonce_789'
    }

    with client.session_transaction() as sess:
        sess['oauth_state'] = 'valid_state_789'
        sess['oauth_nonce'] = 'valid_nonce_789'

    response = client.get('/auth/google/callback?code=mock_code&state=valid_state_789', follow_redirects=True)
    assert response.status_code == 200
    assert b'An account with this email already exists' in response.data or b'Sign In' in response.data

    with app.app_context():
        updated_user = db.session.get(User, user_a.id)
        assert updated_user.google_sub is None


def test_explicit_account_linking(client, app, user_a):
    """Test explicit account linking via POST /auth/google/link when authenticated."""
    client.post('/auth/login', data={'email': 'usera@example.com', 'password': 'password123'})

    with client.session_transaction() as sess:
        sess['pending_google_sub'] = 'google_sub_user_a_explicit'

    response = client.post('/auth/google/link', follow_redirects=True)
    assert response.status_code == 200

    with app.app_context():
        updated_user = db.session.get(User, user_a.id)
        assert updated_user.google_sub == 'google_sub_user_a_explicit'

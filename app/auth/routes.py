"""Authentication routes and blueprint registration."""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user
from urllib.parse import urlsplit

from app.forms.auth_forms import LoginForm, RegistrationForm
from app.services import auth_service
from app.extensions import limiter

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per hour", methods=["POST"])
def register():
    """User registration route."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
        
    form = RegistrationForm()
    if form.validate_on_submit():
        success, message, user = auth_service.register_user(
            username=form.username.data,
            email=form.email.data,
            password=form.password.data,
            full_name=form.full_name.data
        )
        if success:
            flash(message, 'success')
            return redirect(url_for('auth.login'))
        else:
            flash(message, 'danger')
            
    return render_template('auth/register.html', title='Register', form=form)

@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=["POST"])
def login():
    """User login route."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
        
    form = LoginForm()
    if form.validate_on_submit():
        success, message = auth_service.login_user(
            email=form.email.data,
            password=form.password.data,
            remember=form.remember_me.data
        )
        
        if success:
            flash(message, 'success')
            next_page = request.args.get('next')
            # Protect against open redirect attacks
            if not next_page or urlsplit(next_page).netloc != '':
                next_page = url_for('dashboard.index')
            return redirect(next_page)
        else:
            flash(message, 'danger')
            
    return render_template('auth/login.html', title='Sign In', form=form)

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """User logout route requiring POST method and CSRF validation."""
    from flask import current_app
    auth_service.logout_user()
    flash('You have been logged out.', 'info')
    
    response = redirect(url_for('auth.login'))
    
    # Explicitly clear remember-me cookie on the response as defense-in-depth
    cookie_name = current_app.config.get("REMEMBER_COOKIE_NAME", "remember_token")
    domain = current_app.config.get("REMEMBER_COOKIE_DOMAIN")
    path = current_app.config.get("REMEMBER_COOKIE_PATH", "/")
    response.delete_cookie(cookie_name, domain=domain, path=path)
    
    # Ensure cache-control headers on logout response
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    return response


@auth_bp.route('/google', methods=['GET'])
def google_login():
    """Initiates server-side Google OAuth 2.0 / OIDC authorization code flow."""
    import secrets
    from urllib.parse import urlencode
    from flask import current_app, session

    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    client_id = current_app.config.get('GOOGLE_CLIENT_ID')
    redirect_uri = current_app.config.get('GOOGLE_REDIRECT_URI')

    if not client_id or not client_id.strip():
        flash("Google authentication is not configured for this server environment.", "warning")
        return redirect(url_for('auth.login'))

    # Generate cryptographically random state & nonce for CSRF & replay protection
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)

    session['oauth_state'] = state
    session['oauth_nonce'] = nonce

    params = {
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': 'openid email profile',
        'state': state,
        'nonce': nonce,
        'prompt': 'select_account'
    }

    google_auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return redirect(google_auth_url)


@auth_bp.route('/google/callback', methods=['GET'])
def google_callback():
    """Handles Google OAuth callback, verifies OIDC ID token, and logs in user."""
    import secrets
    import logging
    import requests
    from flask import current_app, session

    logger = logging.getLogger(__name__)

    # Retrieve & consume session state & nonce
    expected_state = session.pop('oauth_state', None)
    expected_nonce = session.pop('oauth_nonce', None)

    # 1. Check for user cancellation or provider error
    if request.args.get('error'):
        flash("Google authentication was cancelled or declined.", "warning")
        return redirect(url_for('auth.login'))

    # 2. Validate state token (CSRF defense)
    state_param = request.args.get('state')
    if not expected_state or not state_param or not secrets.compare_digest(expected_state, state_param):
        flash("Authentication failed due to invalid or expired state session token.", "danger")
        return redirect(url_for('auth.login'))

    # 3. Validate nonce parameter
    if not expected_nonce:
        flash("Authentication failed due to missing request nonce.", "danger")
        return redirect(url_for('auth.login'))

    code = request.args.get('code')
    if not code:
        flash("Authorization code was missing from callback response.", "danger")
        return redirect(url_for('auth.login'))

    client_id = current_app.config.get('GOOGLE_CLIENT_ID')
    client_secret = current_app.config.get('GOOGLE_CLIENT_SECRET')
    redirect_uri = current_app.config.get('GOOGLE_REDIRECT_URI')

    # 4. Exchange authorization code for tokens via HTTPS POST
    token_url = "https://oauth2.googleapis.com/token"
    token_payload = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri,
        'client_id': client_id,
        'client_secret': client_secret
    }

    try:
        token_resp = requests.post(token_url, data=token_payload, timeout=10)
        if token_resp.status_code != 200:
            logger.error(f"Google token endpoint failed with status {token_resp.status_code}")
            flash("Failed to obtain OAuth tokens from Google.", "danger")
            return redirect(url_for('auth.login'))

        token_data = token_resp.json()
        id_token_str = token_data.get('id_token')
        if not id_token_str:
            flash("Google response did not contain a valid ID token.", "danger")
            return redirect(url_for('auth.login'))

        # 5. OIDC ID Token Verification via Google TokenInfo Endpoint
        tokeninfo_resp = requests.get(
            f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token_str}",
            timeout=10
        )
        if tokeninfo_resp.status_code != 200:
            flash("Failed to verify Google identity token payload.", "danger")
            return redirect(url_for('auth.login'))

        claims = tokeninfo_resp.json()

        # Validate issuer, audience, nonce, sub, email verification
        iss = claims.get('iss')
        aud = claims.get('aud')
        token_nonce = claims.get('nonce')
        google_sub = claims.get('sub')
        email = claims.get('email')
        email_verified = claims.get('email_verified')

        if iss not in ["https://accounts.google.com", "accounts.google.com"]:
            flash("Invalid ID token issuer.", "danger")
            return redirect(url_for('auth.login'))

        if aud != client_id:
            flash("Invalid ID token audience.", "danger")
            return redirect(url_for('auth.login'))

        if token_nonce != expected_nonce:
            flash("ID token nonce validation mismatch.", "danger")
            return redirect(url_for('auth.login'))

        if str(email_verified).lower() != "true":
            flash("Google account email is not verified.", "danger")
            return redirect(url_for('auth.login'))

        if not google_sub or not email:
            flash("Incomplete identity claims received from Google.", "danger")
            return redirect(url_for('auth.login'))

        full_name = claims.get('name')

        # 6. Resolve or create user account according to strict account-linking policy
        success, message, user, action = auth_service.handle_google_login(
            google_sub=google_sub,
            email=email,
            name=full_name
        )

        if action == "link_required":
            session['pending_google_sub'] = google_sub
            flash(message, "info")
            return redirect(url_for('auth.login'))

        if success:
            flash(message, "success")
            return redirect(url_for('dashboard.index'))
        else:
            flash(message, "danger")
            return redirect(url_for('auth.login'))

    except requests.RequestException as e:
        logger.error(f"Network error during Google OAuth callback: {e}")
        flash("Network error communicating with Google authentication servers.", "danger")
        return redirect(url_for('auth.login'))


@auth_bp.route('/google/link', methods=['POST'])
def link_google():
    """Explicitly links pending or provided Google identity to current authenticated account."""
    from flask import session
    from flask_login import login_required, current_user

    if not current_user.is_authenticated:
        flash("Please sign in to link your Google account.", "warning")
        return redirect(url_for('auth.login'))

    google_sub = session.pop('pending_google_sub', None) or request.form.get('google_sub')
    if not google_sub:
        flash("No Google account identity specified for linking.", "warning")
        return redirect(url_for('dashboard.index'))

    success, message = auth_service.link_google_account(current_user.id, google_sub)
    if success:
        flash(message, "success")
    else:
        flash(message, "danger")
    return redirect(url_for('dashboard.index'))


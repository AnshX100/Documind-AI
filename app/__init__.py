"""Flask Application Factory."""

import os
from flask import Flask, render_template, redirect, url_for, jsonify, request
from app.config import config_by_name
from app.extensions import db, migrate, login_manager, csrf, limiter

def create_app(config_name: str | None = None) -> Flask:
    """Create and configure the Flask application instance."""
    app = Flask(__name__)
    
    # Configure app
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')
    
    app.config.from_object(config_by_name[config_name])
    
    # Dynamically evaluate SQLALCHEMY_DATABASE_URI from environment for non-testing configs
    if not app.config.get('TESTING'):
        app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', '')

    # Enforce DATABASE_URL presence for non-testing environment
    if not app.config.get('TESTING') and not app.config.get('SQLALCHEMY_DATABASE_URI'):
        raise ValueError("DATABASE_URL environment variable is not set. Please set DATABASE_URL in environment or .env file.")
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    
    # Register 429 Rate Limit error handler
    @app.errorhandler(429)
    def ratelimit_handler(e):
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                "status": "error",
                "message": "Rate limit exceeded. Please wait before retrying.",
                "error": str(e.description) if hasattr(e, "description") else "Too many requests"
            }), 429
        return render_template('landing.html'), 429
    
    # Login view configuration
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'
    
    # User loader callback for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        from app.models.user import User
        return User.query.get(int(user_id))
    
    # Register blueprints
    from app.auth import auth_bp
    from app.dashboard import dashboard_bp
    from app.documents import documents_bp
    from app.dashboard.routes import placeholders_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(placeholders_bp)
    
    # Root route redirects to dashboard if authenticated, else renders public landing page
    @app.route('/')
    def index():
        from flask_login import current_user
        if current_user.is_authenticated:
            return redirect(url_for('dashboard.index'))
        return render_template('landing.html')
        
    @app.after_request
    def set_cache_control_headers(response):
        """Ensure no sensitive cached data is served on browser back/forward navigation."""
        if not request.path.startswith('/static/'):
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response

    return app

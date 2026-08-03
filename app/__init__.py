"""Flask Application Factory."""

import os
from flask import Flask, redirect, url_for
from app.config import config_by_name
from app.extensions import db, migrate, login_manager

def create_app(config_name: str | None = None) -> Flask:
    """Create and configure the Flask application instance."""
    app = Flask(__name__)
    
    # Configure app
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')
    
    app.config.from_object(config_by_name[config_name])
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    
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
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    
    # Root route redirects to dashboard if authenticated, else login
    @app.route('/')
    def index():
        from flask_login import current_user
        if current_user.is_authenticated:
            return redirect(url_for('dashboard.index'))
        return redirect(url_for('auth.login'))
        
    return app

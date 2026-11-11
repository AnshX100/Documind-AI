"""Flask Application Factory."""

import os
from flask import Flask, render_template, redirect, url_for, jsonify, request
from app.config import config_by_name
from app.extensions import db, migrate, login_manager, csrf, limiter


def create_app(config_name: str | None = None) -> Flask:
    """Create and configure the Flask application instance."""
    app = Flask(__name__)

    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    config_class = config_by_name.get(config_name)
    if config_class is None:
        raise ValueError(f"Unknown application configuration: {config_name!r}")

    app.config.from_object(config_class)

    # Production must never inherit development secrets or process-local
    # rate-limit storage. Read these at app creation time so deployment
    # environment changes are validated rather than relying on import-time values.
    if config_name == "production":
        secret_key = os.getenv("SECRET_KEY", "")
        if len(secret_key) < 32 or secret_key == "default-dev-secret-key-must-be-changed":
            raise ValueError(
                "Production requires SECRET_KEY to be set to a random value "
                "containing at least 32 characters."
            )
        app.config["SECRET_KEY"] = secret_key

        rate_limit_storage = os.getenv("RATELIMIT_STORAGE_URI", "").strip()
        if not rate_limit_storage.startswith(("redis://", "rediss://")):
            raise ValueError(
                "Production requires RATELIMIT_STORAGE_URI to use Redis "
                "(redis:// or rediss://); memory:// is not safe across workers."
            )
        app.config["RATELIMIT_STORAGE_URI"] = rate_limit_storage

    # Evaluate DATABASE_URL at app creation time for non-testing environments.
    if not app.config.get("TESTING"):
        app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "")

    if not app.config.get("TESTING") and not app.config.get("SQLALCHEMY_DATABASE_URI"):
        raise ValueError(
            "DATABASE_URL environment variable is not set. "
            "Please set DATABASE_URL in environment or .env file."
        )

    # Initialize extensions only after configuration has been validated.
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    @app.errorhandler(429)
    def ratelimit_handler(e):
        if request.is_json or request.path.startswith("/api/"):
            return jsonify({
                "status": "error",
                "message": "Rate limit exceeded. Please wait before retrying.",
                "error": str(e.description) if hasattr(e, "description") else "Too many requests",
            }), 429
        return render_template("landing.html"), 429

    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id):
        from app.models.user import User
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    from app.auth import auth_bp
    from app.dashboard import dashboard_bp
    from app.documents import documents_bp
    from app.dashboard.routes import placeholders_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(placeholders_bp)

    @app.route("/")
    def index():
        from flask_login import current_user
        if current_user.is_authenticated:
            return redirect(url_for("dashboard.index"))
        return render_template("landing.html")

    @app.after_request
    def set_cache_control_headers(response):
        """Prevent sensitive pages from being cached by browsers."""
        if not request.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    return app

# routes/__init__.py
from .auth_routes      import bp as auth_bp
from .amazon_routes    import bp as amazon_bp
from .admin_routes     import bp as admin_bp
from .dashboard_routes import bp as dashboard_bp
from .automation       import automation_bp

__all__ = [
    "auth_bp",
    "amazon_bp",
    "admin_bp",
    "dashboard_bp",
    "automation_bp",
]

def init_app(app):
    app.register_blueprint(auth_bp,      url_prefix="/auth")
    app.register_blueprint(amazon_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
    app.register_blueprint(automation_bp, url_prefix="/automation")

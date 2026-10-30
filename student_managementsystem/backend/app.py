from pathlib import Path
import os

from flask import Flask, jsonify, send_from_directory
from flask import g, request
from flask_cors import CORS
from sqlalchemy import event

from backend.config import Config
from backend.extensions import db
from backend.migrations import migrate_existing_schema
from backend.routes.api import api
from backend.routes.auth import auth
from backend.routes.erp import erp
from backend.security import load_token

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"


def create_app(test_config=None):
    app = Flask(
        __name__,
        static_folder=str(FRONTEND_DIR),
        static_url_path="/frontend",
    )
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    if os.environ.get("VERCEL"):
        missing = [
            name for name in ("SECRET_KEY", "DATABASE_URL")
            if not os.environ.get(name)
        ]
        if missing:
            raise RuntimeError(
                "Set the required Vercel environment variable(s): "
                + ", ".join(missing)
            )
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    db.init_app(app)
    app.register_blueprint(api)
    app.register_blueprint(auth)
    app.register_blueprint(erp)

    @app.before_request
    def authenticate_api_request():
        if (
            not request.path.startswith("/api/")
            or request.method == "OPTIONS"
            or request.endpoint in {
                "api.health", "auth.login", "auth.bootstrap"
            }
        ):
            return None
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            g.current_user = None
            return None
        g.current_user = load_token(token)
        if not g.current_user:
            return jsonify({"error": "The access token is invalid or expired."}), 401
        return None

    @app.get("/")
    def index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"error": "The requested resource was not found."}), 404

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return jsonify({"error": "This method is not allowed for the requested resource."}), 405

    @app.errorhandler(500)
    def internal_error(_error):
        db.session.rollback()
        return jsonify({"error": "An unexpected server error occurred."}), 500

    with app.app_context():
        if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:"):
            @event.listens_for(db.engine, "connect")
            def enable_sqlite_foreign_keys(connection, _record):
                cursor = connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        db.create_all()
        migrate_existing_schema()

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

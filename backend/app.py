import logging
import os

from dotenv import load_dotenv
from flask import Flask, g, jsonify, request
from flask_cors import CORS

load_dotenv()

from analyze_routes import analyze_bp
from auth import auth_bp
from database import seed_demo_user
from extensions import db, limiter, migrate
from routes import data_bp
from utils import SECRET_KEY

FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SQLITE_URL = "sqlite:///" + os.path.join(BASE_DIR, "users.db")
DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_SQLITE_URL)


def configure_logging(app):
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    @app.before_request
    def log_request():
        g.request_id = os.urandom(4).hex()
        app.logger.info("--> %s %s [%s]", request.method, request.path, g.request_id)

    @app.after_request
    def log_response(response):
        request_id = getattr(g, "request_id", "-")
        app.logger.info("<-- %s %s %s [%s]", request.method, request.path, response.status_code, request_id)
        return response


def create_app(test_config=None):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 MB upload limit
    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}

    if test_config:
        app.config.update(test_config)

    configure_logging(app)

    CORS(
        app,
        resources={r"/api/*": {"origins": FRONTEND_ORIGIN}},
        supports_credentials=True,
    )

    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)

    with app.app_context():
        if app.config.get("TESTING"):
            # Tests run against a throwaway DB with no migration history.
            db.create_all()
        seed_demo_user()

    app.register_blueprint(auth_bp)
    app.register_blueprint(data_bp)
    app.register_blueprint(analyze_bp)

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"message": "Resource not found"}), 404

    @app.errorhandler(413)
    def too_large(_error):
        return jsonify({"message": "File is too large (max 20MB)"}), 413

    @app.errorhandler(429)
    def rate_limited(_error):
        return jsonify({"message": "Too many requests, please slow down"}), 429

    @app.errorhandler(500)
    def server_error(error):
        app.logger.exception("Unhandled server error: %s", error)
        return jsonify({"message": "Internal server error"}), 500

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true")

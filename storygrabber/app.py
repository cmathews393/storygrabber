"""Setup app factory etc."""

import os
import sys

import dotenv
from flask import Flask
from loguru import logger

from .api import api_bp

# Local imports
from .routes import main_bp

dotenv.load_dotenv()


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__, instance_relative_config=True)

    # Default minimal configuration
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev"),
    )

    _configure_logging()
    _register_blueprints(app)
    _register_error_handlers(app)

    return app


def _configure_logging() -> None:
    """Configure a simple stderr stream logging handler for the Flask app."""
    level = os.environ.get("FLASK_LOG_LEVEL", "INFO").upper()
    logger.remove()
    logger.add(sys.stderr, level=level, format="{time} | {level} | {message}")
    logger.add("storygrabber.log", level=level, format="{time} | {level} | {message}")


def _register_blueprints(app: Flask) -> None:
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)


def _register_error_handlers(app: Flask) -> None:
    from flask import jsonify

    @app.errorhandler(404)
    def _not_found(error: str) -> tuple:
        logger.error(f"404 error: {error}")
        return jsonify({"error": "not found"}), 404

    @app.errorhandler(500)
    def _server_error(error: str) -> tuple:
        logger.error(f"500 error: {error}")
        return jsonify({"error": "internal server error"}), 500

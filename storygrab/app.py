import os
import logging
from typing import Optional, Mapping

from flask import Flask

# Local imports
from .routes import main_bp
from .backend import api_bp


def create_app(config: Optional[Mapping] | str | None = None) -> Flask:
    """Create and configure the Flask application.

    Args:
        config: Optional configuration mapping or import string to load with
                ``app.config.from_object``. If None a minimal default config
                will be used.

    Returns:
        A configured Flask application instance.
    """

    app = Flask(__name__, instance_relative_config=True)

    # Default minimal configuration
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev"),
    )

    # Allow passing a dict-like config or an import string for complex configs
    if config is None:
        pass
    elif isinstance(config, Mapping):
        app.config.update(config)
    elif isinstance(config, str):
        app.config.from_object(config)
    else:
        # Try generic object-based config
        try:
            app.config.from_object(config)
        except Exception:  # pragma: no cover - defensive
            pass

    _configure_logging(app)
    _register_blueprints(app)
    _register_error_handlers(app)

    return app


def _configure_logging(app: Flask) -> None:
    """Configure a simple stderr stream logging handler for the Flask app."""
    level = os.environ.get("FLASK_LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))

    # Avoid attaching duplicate handlers during factory reuse
    if not any(isinstance(h, logging.StreamHandler) for h in app.logger.handlers):
        app.logger.addHandler(handler)
    app.logger.setLevel(level)


def _register_blueprints(app: Flask) -> None:
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)


def _register_error_handlers(app: Flask) -> None:
    from flask import jsonify

    @app.errorhandler(404)
    def _not_found(error):
        return jsonify({"error": "not found"}), 404

    @app.errorhandler(500)
    def _server_error(error):
        # Do not leak details in production; Flask will log the exception
        return jsonify({"error": "internal server error"}), 500

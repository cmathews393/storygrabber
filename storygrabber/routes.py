"""Frontend routes."""

from flask import Blueprint, render_template

main_bp = Blueprint("main", __name__)


@main_bp.route("/", methods=["GET"])
def index() -> str:
    """Home page."""
    return render_template("home.html.j2")


@main_bp.route("/dashboard", methods=["GET"])
def dashboard() -> str:
    """Dashboard page."""
    return render_template("dashboard.html.j2")


@main_bp.route("/settings", methods=["GET"])
def settings() -> str:
    """Settings page."""
    return render_template("settings.html.j2")

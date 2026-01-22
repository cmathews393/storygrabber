from flask import Blueprint, jsonify, render_template

main_bp = Blueprint("main", __name__)


@main_bp.route("/", methods=["GET"])
def index():
    return render_template("home.html.j2")


@main_bp.route("/dashboard", methods=["GET"])
def dashboard():
    return render_template("dashboard.html.j2")


@main_bp.route("/settings", methods=["GET"])
def settings():
    return render_template("settings.html.j2")


@main_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"})

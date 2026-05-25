import os

from flask import Flask, jsonify, render_template, request

from api.scan import scan_bp
from api.batch import batch_bp
from api.circuit import circuit_bp
import models.loader as loader
import database.db as db

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB upload cap
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key-change-before-any-deployment")

# ---------------------------------------------------------------------------
# Blueprints
# ---------------------------------------------------------------------------
app.register_blueprint(scan_bp)
app.register_blueprint(batch_bp)
app.register_blueprint(circuit_bp)

# ---------------------------------------------------------------------------
# CORS — allow only the browser extension and localhost dev origins.
# Wildcard "*" is intentionally avoided on data-modifying endpoints.
# ---------------------------------------------------------------------------
_ALLOWED_ORIGINS = {"http://localhost:5000", "http://127.0.0.1:5000"}


@app.after_request
def add_headers(response):
    origin = request.headers.get("Origin", "")
    if (
        origin.startswith("chrome-extension://")
        or origin.startswith("moz-extension://")
        or origin in _ALLOWED_ORIGINS
    ):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"

    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://cdn.jsdelivr.net; "
        "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self';"
    )
    return response


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------
@app.errorhandler(413)
def request_too_large(e):
    return jsonify({"error": "File too large — maximum 5 MB allowed"}), 413


@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/batch")
def batch():
    return render_template("batch.html")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/visualizer")
def visualizer():
    return render_template("visualizer.html")


# ---------------------------------------------------------------------------
# Entry point — initialization runs only when actually serving, not on import.
# debug=False and host=127.0.0.1 prevent Werkzeug debugger exposure on LAN.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    with app.app_context():
        loader.initialize()
        db.init_db()
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        threaded=True,
    )

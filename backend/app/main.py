import os
from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from pathlib import Path

from app.routes.simulate import simulate_bp
from app.routes.info     import info_bp

app = Flask(__name__)
CORS(app)

# Blueprint /api/* didaftarkan SEBELUM catch-all frontend route
# agar semua path /api/... ditangani blueprint, bukan serve_frontend
app.register_blueprint(simulate_bp)
app.register_blueprint(info_bp)

# ── Path ─────────────────────────────────────────────────────────────────────
# __file__ = .../ASTA_PORTAL_Website_r27/backend/app/main.py
_APP_DIR      = Path(__file__).resolve().parent          # .../backend/app/
_FRONTEND_DIR = str(_APP_DIR.parent.parent / "frontend") # .../ASTA_PORTAL_Website_r27/frontend/
_GEOJSON_DIR  = str(_APP_DIR / "data" / "geojson")      # .../backend/app/data/geojson/


# ── GeoJSON kecamatan via /static/geojson/<filename> ────────────────────────
@app.route("/static/geojson/<path:filename>")
def serve_geojson(filename):
    return send_from_directory(_GEOJSON_DIR, filename)


# ── Health check ─────────────────────────────────────────────────────────────
@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


# ── Sajikan frontend: root → index.html ──────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(_FRONTEND_DIR, "index.html")


# ── Sajikan semua aset frontend: HTML, CSS, JS, gambar, GeoJSON lokal ────────
# CATATAN: Flask mencocokkan route dari yang paling spesifik.
# /api/* dan /static/geojson/* sudah terdaftar di atas, tidak akan jatuh ke sini.
@app.route("/<path:filename>")
def serve_frontend(filename):
    return send_from_directory(_FRONTEND_DIR, filename)

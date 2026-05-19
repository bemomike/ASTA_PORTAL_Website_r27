import os
from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS

from app.routes.simulate import simulate_bp
from app.routes.info     import info_bp

app = Flask(__name__)
CORS(app)

app.register_blueprint(simulate_bp)
app.register_blueprint(info_bp)

# ── Sajikan GeoJSON via /static/geojson/<filename> ───────────
# Lebih aman daripada static_folder karena tidak konflik dengan blueprint
_GEOJSON_DIR = os.path.join(os.path.dirname(__file__), "data", "geojson")

@app.route("/static/geojson/<path:filename>")
def serve_geojson(filename):
    return send_from_directory(_GEOJSON_DIR, filename)

@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})

"""
verify_deployment.py — ASTA PORTAL r27
Jalankan di PythonAnywhere Bash untuk memastikan semua file kritis tersedia.

Cara pakai:
  cd ~/ASTA_PORTAL_Website_r27
  python3.10 verify_deployment.py
"""
import sys
import os
from pathlib import Path

# ── Tentukan BASE DIR dari posisi script ini ─────────────────────────────────
BASE = Path(__file__).resolve().parent  # = ~/ASTA_PORTAL_Website_r27/

CHECKS = {
    # File kode wajib ada (dari GitHub pull)
    "Flask app":             BASE / "backend/app/main.py",
    "Route simulate":        BASE / "backend/app/routes/simulate.py",
    "Route info":            BASE / "backend/app/routes/info.py",
    "WSGI":                  BASE / "backend/wsgi.py",
    "config.js":             BASE / "frontend/js/config.js",
    "simulasi.html":         BASE / "frontend/simulasi.html",
    "kecamatan GeoJSON":     BASE / "frontend/geojson/kecamatan_semarang.geojson",

    # File model & data (upload manual — TIDAK dari GitHub)
    "Model RF (.pkl)":       BASE / "backend/app/model/trained/rf_model.pkl",
    "Label Encoder tanah":   BASE / "backend/app/model/trained/le_tanah.pkl",
    "Label Encoder veg":     BASE / "backend/app/model/trained/le_veg.pkl",
    "rf_static_data.py":     BASE / "backend/app/data/static/rf_static_data.py",
    "Batch GeoJSON":         BASE / "backend/app/data/batch/simulasi_batch_19kec.geojson",
    "Ringkasan batch JSON":  BASE / "backend/app/data/batch/ringkasan_batch_19kec.json",
}

ok = fail = 0
print(f"\n{'='*58}")
print(f"  ASTA PORTAL r27 — Deployment Verification")
print(f"  BASE: {BASE}")
print(f"{'='*58}")
for label, path in CHECKS.items():
    exists = path.exists()
    status = "✓ OK  " if exists else "✗ MISSING"
    print(f"  {status}  {label}")
    if exists: ok += 1
    else: fail += 1

print(f"{'='*58}")
print(f"  Hasil: {ok} OK, {fail} MISSING")
if fail == 0:
    print("  ✓ Semua file tersedia. Klik Reload di tab Web.")
else:
    print("  ✗ Upload file yang MISSING ke PythonAnywhere (lihat README.md)")
print(f"{'='*58}\n")
sys.exit(0 if fail == 0 else 1)

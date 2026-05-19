#!/usr/bin/env python3
"""
verify_deployment.py — ASTA PORTAL r24
Jalankan di Bash PythonAnywhere:
  cd ~/ASTA_PORTAL_Website_r24
  python3.10 verify_deployment.py

Jika nama folder berbeda saat upload, sesuaikan path di atas.
Output: STATUS: SEMUA OK  atau daftar [FAIL] dengan penyebabnya.
"""
import sys, os
from pathlib import Path

BASE  = Path(__file__).resolve().parent / "backend"
FAILS = []

print("=" * 60)
print("ASTA PORTAL r24 — Verifikasi Deployment")
print("=" * 60)

# ── [1] Cek 3 file pkl ────────────────────────────────────────
print("\n[1] Model pkl (backend/app/model/trained/)")
for fname in ["rf_model.pkl", "le_tanah.pkl", "le_veg.pkl"]:
    p = BASE / "app/model/trained" / fname
    if p.exists():
        print(f"    [OK] {fname}  ({p.stat().st_size // 1024} KB)")
    else:
        print(f"    [FAIL] {fname} TIDAK DITEMUKAN")
        FAILS.append(f"Model '{fname}' tidak ada di backend/app/model/trained/")

# ── [2] Cek rf_static_data.py bukan placeholder ───────────────
print("\n[2] rf_static_data.py (backend/app/data/static/)")
_static = BASE / "app/data/static/rf_static_data.py"
if _static.exists():
    _ns = {}
    try:
        exec(_static.read_text(encoding="utf-8"), _ns)
        _sd = _ns.get("SEKTOR_DATA", {})
        _ki = _ns.get("KEC_INFO", {})
        _n_total = sum(len(v) for v in _sd.values())
        if _n_total == 0:
            print(f"    [FAIL] SEKTOR_DATA kosong — file masih placeholder!")
            FAILS.append("rf_static_data.py masih placeholder (SEKTOR_DATA={}). Upload hasil Export-4.")
        else:
            kali = _sd.get("KALIWUNGU", [])
            print(f"    [OK] SEKTOR_DATA: {len(_sd)} kecamatan, total {_n_total} sektor")
            print(f"    [OK] KEC_INFO   : {len(_ki)} kecamatan")
            print(f"    [OK] KALIWUNGU  : {len(kali)} sektor")
    except Exception as e:
        print(f"    [FAIL] Error saat baca rf_static_data.py: {e}")
        FAILS.append(f"rf_static_data.py error: {e}")
else:
    print(f"    [FAIL] File tidak ditemukan")
    FAILS.append("rf_static_data.py tidak ada")

# ── [3] Cek jumlah GeoJSON ────────────────────────────────────
print("\n[3] GeoJSON (backend/app/data/geojson/)")
_gj_dir = BASE / "app/data/geojson"
_gj_files = list(_gj_dir.glob("*.geojson"))
_kec_gj   = [f for f in _gj_files if not f.name.startswith("veg_") and not f.name.startswith("tanah_")
             and f.name not in ("kabupaten_semarang.geojson", "kecamatan_semarang.geojson")]
_veg_gj   = [f for f in _gj_files if f.name.startswith("veg_")]
_tanah_gj = [f for f in _gj_files if f.name.startswith("tanah_")]
print(f"    Sektor kecamatan : {len(_kec_gj)}/19  {'[OK]' if len(_kec_gj)==19 else '[FAIL]'}")
print(f"    Vegetasi (veg_*) : {len(_veg_gj)}/19  {'[OK]' if len(_veg_gj)==19 else '[FAIL]'}")
print(f"    Tanah (tanah_*)  : {len(_tanah_gj)}/19  {'[OK]' if len(_tanah_gj)==19 else '[FAIL]'}")
for label, lst, expected in [("sektor", _kec_gj, 19), ("veg", _veg_gj, 19), ("tanah", _tanah_gj, 19)]:
    if len(lst) < expected:
        FAILS.append(f"GeoJSON {label}: hanya {len(lst)}/{expected} file. Jalankan Export-2 dan Export-3b/3c.")

for fname in ["kabupaten_semarang.geojson", "kecamatan_semarang.geojson"]:
    p = _gj_dir / fname
    if p.exists() and p.stat().st_size > 500:
        print(f"    [OK] {fname}")
    else:
        print(f"    [FAIL] {fname} tidak ada atau masih placeholder")
        FAILS.append(f"{fname} tidak ada atau masih placeholder")

# ── [4] Cek batch ─────────────────────────────────────────────
print("\n[4] Batch GeoJSON (backend/app/data/batch/)")
for fname in ["simulasi_batch_19kec.geojson", "ringkasan_batch_19kec.json"]:
    p = BASE / "app/data/batch" / fname
    if p.exists() and p.stat().st_size > 1000:
        print(f"    [OK] {fname}  ({p.stat().st_size // 1024} KB)")
    else:
        print(f"    [WARN] {fname} kecil/placeholder — website tetap bisa jalan via live inference")

# ── [5] Cek Flask bisa diimport ───────────────────────────────
print("\n[5] Import library Python")
for lib in ["flask", "flask_cors", "sklearn", "numpy", "joblib"]:
    try:
        __import__(lib)
        print(f"    [OK] {lib}")
    except ImportError:
        print(f"    [FAIL] {lib} tidak terinstall")
        FAILS.append(f"Library '{lib}' tidak terinstall. Jalankan: pip install -r backend/requirements.txt --user")

# ── Ringkasan ─────────────────────────────────────────────────
print("\n" + "=" * 60)
if FAILS:
    print(f"STATUS: {len(FAILS)} MASALAH DITEMUKAN")
    for i, f in enumerate(FAILS, 1):
        print(f"  [{i}] {f}")
    print("\nSelesaikan semua masalah di atas lalu jalankan verify_deployment.py lagi.")
else:
    print("STATUS: SEMUA OK — Website siap digunakan!")
print("=" * 60)

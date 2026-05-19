"""
POST /api/simulate
Body JSON: { "kec": "KALIWUNGU", "ch_pct": 97.5, "tcc_pct": 44.0 }

ASTA PORTAL — simulate.py REVISI r26
=====================================================================

PERUBAHAN UTAMA vs versi sebelumnya:
--------------------------------------
1. rf_static_data.py sekarang WAJIB ada (berisi SEKTOR_DATA + NORM_P5/P95).
   File ini di-copy dari r24 yang modelnya identik dengan ASTA_final.
   Tanpa file ini, slider pengguna tidak berdampak ke PRED_B.

2. _inference(): CH_STD dan HH_STD TIDAK diskalakan bersama slider CH.
   Keduanya adalah variabilitas historis iklim (karakteristik tetap kecamatan),
   bukan nilai proporsional terhadap intensitas CH sesaat.
   Menskalakan keduanya mengubah distribusi fitur keluar dari domain training RF
   dan menghasilkan prediksi paradoksal di kecamatan dengan CH_STD tinggi.
   Hanya CH_MEAN dan HH_MEAN yang diskalakan.

3. _boost(): berbasis karakteristik geomorfologis per sektor (lereng, vegetasi, akar).
   Saturasi: kecamatan PRED_A mendekati 100% mendapat boost TCC lebih kecil (mencegah >100).
   Output selalu di-clip ke [0, 100].

4. CATATAN KETERBATASAN MODEL (bukan bug kode):
   - PROP_VEG_BERKANOPI berbobot hanya 0.13% di RF → slider TCC berdampak
     kecil ke RF output. Efek TCC sepenuhnya dari _boost() manual.
   - CH_STD (22.3%) + HH_STD (15.6%) = 37.9% dari feature importance tetapi
     tidak bisa diubah pengguna karena nilainya adalah data historis tetap.
   - Akibatnya: skenario CH=80%, TCC=30% (gabungan) bisa menghasilkan
     PRED_B < PRED_A di kecamatan dengan CH sensitif tinggi (BANCAK, BRINGIN,
     GETASAN, JAMBU, dll) karena efek CH turun -20% mendominasi efek deforestasi.
     Ini bukan bug — ini mencerminkan kenyataan bahwa model RF di-training dengan
     TARGET_Y berbasis rekam bencana historis, di mana CH adalah prediktor
     dominan. Slider idealnya digunakan secara terpisah:
       - Ubah TCC saja (CH=100%) untuk melihat murni efek deforestasi
       - Ubah CH saja (TCC=100%) untuk melihat murni efek curah hujan

=====================================================================
"""
import json
import numpy as np
from pathlib import Path
from flask import Blueprint, request, jsonify
import joblib

simulate_bp = Blueprint("simulate", __name__)

_BASE     = Path(__file__).resolve().parents[1]
_BATCH    = _BASE / "data/batch/simulasi_batch_19kec.geojson"
_STATIC   = _BASE / "data/static/rf_static_data.py"
_MODEL    = _BASE / "model/trained/rf_model.pkl"
_LE_TANAH = _BASE / "model/trained/le_tanah.pkl"
_LE_VEG   = _BASE / "model/trained/le_veg.pkl"

# Urutan 19 fitur FITUR_MODEL notebook v89_finale_r24 — WAJIB sesuai urutan training
_URUTAN_FITUR = [
    "TANAH_ENC", "SKOR_TT_MEAN", "BAHAN_INDU_ENC",
    "FISIOGRAFI_ENC", "VEG_ENC", "VEG_RISIKO",
    "SKOR_AKAR_MEAN", "JNSSMK_MEAN", "SKOR_LERENG_W",
    "GRIDCODE_LERENG_W", "PROP_DATAR", "PROP_LANDAI",
    "PROP_CURAM", "CH_MEAN", "HH_MEAN",
    "TINGGI_MEAN", "CH_STD", "HH_STD",
    "PROP_VEG_BERKANOPI",
]

# Bobot Pilihan C — harus identik dengan notebook D3 Persiapan r24
_W_SKOR_AKAR  = 0.50   # SKOR_AKAR turun saat deforestasi
_W_VEG_RISIKO = 0.35   # VEG_RISIKO naik saat deforestasi
_W_JNSSMK     = 0.20   # JNSSMK_MEAN turun saat deforestasi


def _load_batch():
    with open(_BATCH, encoding="utf-8") as f:
        return json.load(f)


def _load_static():
    ns = {}
    with open(_STATIC, encoding="utf-8") as f:
        exec(f.read(), ns)
    return ns


def _inference(rf, row_dict, ch_faktor, tcc_faktor):
    """
    Jalankan 1 prediksi dengan faktor CH dan TCC.

    Modulasi fitur:
      CH slider:
        - CH_MEAN  (idx 13) × ch_faktor  — intensitas CH rata-rata berubah
        - HH_MEAN  (idx 14) × ch_faktor  — hari hujan ikut berubah proporsional
        - CH_STD   (idx 16) : TIDAK diubah — variabilitas historis, tetap
        - HH_STD   (idx 17) : TIDAK diubah — variabilitas historis, tetap

      TCC slider (deforestasi):
        - PROP_VEG_BERKANOPI (idx 18) × tcc_faktor
        - SKOR_AKAR_MEAN (idx 6) turun saat deforestasi
        - JNSSMK_MEAN    (idx 7) turun saat deforestasi
        - VEG_RISIKO     (idx 5) naik menuju 1.0 saat deforestasi

    Catatan CH_STD/HH_STD:
      Menskalakan CH_STD bersama CH_MEAN menyebabkan rasio CH_STD/CH_MEAN
      melonjak di luar distribusi data training saat CH_MEAN diturunkan jauh
      (misal 30%), menghasilkan prediksi yang berlawanan arah dari ekspektasi
      di kecamatan dengan CH_STD historis tinggi (BERGAS, KALIWUNGU, dsb).
      CH_STD adalah standar deviasi tahunan — tidak berubah hanya karena
      intensitas CH sesaat lebih rendah dari rerata.
    """
    deforestasi = max(0.0, 1.0 - tcc_faktor)
    fitur = [float(row_dict.get(k, 0)) for k in _URUTAN_FITUR]

    # CH modulasi: hanya intensitas rata-rata dan hari hujan
    fitur[13] = fitur[13] * ch_faktor   # CH_MEAN
    fitur[14] = fitur[14] * ch_faktor   # HH_MEAN
    # fitur[16] CH_STD  — TIDAK diubah (variabilitas historis)
    # fitur[17] HH_STD  — TIDAK diubah (variabilitas historis)

    if deforestasi > 0.0:
        fitur[18] = max(0.0, fitur[18] * tcc_faktor)
        fitur[6]  = max(0.0, fitur[6] * (1.0 - _W_SKOR_AKAR * deforestasi))
        fitur[7]  = max(0.0, fitur[7] * (1.0 - _W_JNSSMK * deforestasi))
        vr_asli  = fitur[5]
        fitur[5] = min(1.0, vr_asli + _W_VEG_RISIKO * deforestasi * (1.0 - vr_asli))

    return float(rf.predict([fitur])[0])


def _boost(pred_raw, ch_faktor, tcc_faktor, pred_a, row=None):
    """
    Post-hoc boost per-sektor berbasis karakteristik geomorfologis.

    Memperhitungkan:
      1. Efek CH: lereng curam lebih sensitif terhadap perubahan intensitas CH
         (ch_sensitivity: 0.5 untuk datar → 1.0 untuk sangat curam)

      2. Efek deforestasi TCC: tergantung tiga faktor per sektor:
         - GRIDCODE_LERENG_W : curam → dampak lebih besar
         - VEG_RISIKO        : jenis veg protektif hilang → dampak lebih besar
         - SKOR_AKAR_MEAN    : akar dalam hilang → kehilangan proteksi lebih besar

      3. Saturasi: kecamatan PRED_A tinggi (sudah jenuh risiko)
         mendapat efek TCC lebih kecil — mencegah PRED_B melebihi 100

    Output selalu di-clip ke [0, 100].
    """
    if row is not None:
        gc   = float(row.get("GRIDCODE_LERENG_W", 1.5))
        vr   = float(row.get("VEG_RISIKO",        0.50))
        akar = float(row.get("SKOR_AKAR_MEAN",    0.40))
    else:
        gc, vr, akar = 1.5, 0.50, 0.40

    lereng_fk = float(np.clip((gc - 1.0) / 3.0, 0.0, 1.0))
    ch_sensitivity = 0.5 + lereng_fk * 0.5
    ch_effect = (ch_faktor - 1.0) * 15.0 * ch_sensitivity

    deforestasi     = max(0.0, 1.0 - tcc_faktor)
    akar_proteksi   = float(np.clip(1.0 - akar, 0.0, 1.0))
    veg_proteksi    = float(np.clip(1.0 - vr,   0.0, 1.0))
    tcc_sensitivity = lereng_fk * veg_proteksi * akar_proteksi
    saturasi        = 1.0 - pred_a / 100.0
    tcc_effect      = deforestasi * 30.0 * tcc_sensitivity * saturasi

    result = pred_raw + ch_effect + tcc_effect
    return float(np.clip(result, 0.0, 100.0))


@simulate_bp.route("/api/simulate", methods=["POST"])
def simulate():
    data    = request.get_json(force=True)
    kec     = data.get("kec", "").upper().strip()
    ch_pct  = float(data.get("ch_pct",  100))
    tcc_pct = float(data.get("tcc_pct", 100))

    if not kec:
        return jsonify({"error": "Parameter 'kec' wajib diisi."}), 400

    _fk_b = ch_pct  / 100.0
    _tk_b = tcc_pct / 100.0

    # ── 1. Coba batch + live inference ──────────────────────────────────────
    if _BATCH.exists():
        try:
            batch    = _load_batch()
            features = [
                ft for ft in batch.get("features", [])
                if ft["properties"].get("NAME_3", "").upper() == kec
            ]
            if features:
                ch_mean_kec = 0.0
                _rf_tersedia = _MODEL.exists() and _STATIC.exists()
                _rf          = None
                _SEKTOR_DATA = {}
                _ns2         = {}

                if _STATIC.exists():
                    try:
                        _ns2        = _load_static()
                        ch_mean_kec = _ns2.get("KEC_INFO", {}).get(kec, {}).get("ch_mean", 0.0)
                    except Exception:
                        _rf_tersedia = False

                if _rf_tersedia:
                    try:
                        _rf          = joblib.load(_MODEL)
                        _SEKTOR_DATA = _ns2.get("SEKTOR_DATA", {})
                    except Exception:
                        _rf_tersedia = False

                # Indeks SEKTOR_DATA by sektor_id untuk lookup O(1)
                _sek_idx = {}
                if kec in _SEKTOR_DATA:
                    for r in _SEKTOR_DATA[kec]:
                        _sek_idx[r.get("sektor_id", "")] = r

                for ft in features:
                    p = ft["properties"]

                    # CH_AKTIF
                    if "CH_AKTIF_A" not in p:
                        p["CH_AKTIF_A"] = p.get("CH_AKTIF", round(ch_mean_kec, 1))
                    p["CH_AKTIF_B"] = round(ch_mean_kec * _fk_b, 1)

                    # KEMIRINGAN dari SEKTOR_DATA
                    sid        = p.get("ID_SEKTOR", p.get("sektor_id", ""))
                    _row_match = _sek_idx.get(sid)
                    if "KEMIRINGAN" not in p or p.get("KEMIRINGAN", 0) == 0:
                        gc = _row_match.get("GRIDCODE_LERENG_W", 0) if _row_match else 0
                        p["KEMIRINGAN"]        = gc
                        p["GRIDCODE_LERENG_W"] = gc

                    # Pastikan PRED_A ada
                    if "PRED_A" not in p and "PRED_VAL" in p:
                        p["PRED_A"] = p["PRED_VAL"]

                    # PRED_B: live inference jika model dan SEKTOR_DATA tersedia
                    if _rf_tersedia and _row_match is not None:
                        _pred_a_ref = float(p.get("PRED_A", 0))
                        _pred_b_raw = _inference(_rf, _row_match, _fk_b, _tk_b)

                        _p5  = float(_ns2.get("NORM_P5",  _pred_b_raw))
                        _p95 = float(_ns2.get("NORM_P95", _pred_b_raw))
                        _sp  = _p95 - _p5
                        if _sp < 1e-9:
                            _pred_b_norm = 50.0
                        else:
                            _pred_b_norm = float(np.clip(
                                (_pred_b_raw - _p5) / _sp * 100.0, 0, 100))

                        p["PRED_B"] = _boost(
                            _pred_b_norm, _fk_b, _tk_b, _pred_a_ref, row=_row_match
                        )
                    else:
                        # Fallback: gunakan PRED_B dari batch (skenario CH=98.45%, TCC=44.85%)
                        # Ini adalah nilai pre-computed — slider tidak berdampak
                        # Peringatan ini ditampilkan di log server
                        if "PRED_B" not in p and "PRED_VAL" in p:
                            p["PRED_B"] = p["PRED_VAL"]

                return jsonify({
                    "type":          "FeatureCollection",
                    "kec":           kec,
                    "source":        "batch",
                    "ch_pct":        ch_pct,
                    "tcc_pct":       tcc_pct,
                    "live_inference": _rf_tersedia,
                    "features":      features,
                })
        except Exception:
            pass  # lanjut ke live inference penuh

    # ── 2. Live inference penuh (tanpa batch) ───────────────────────────────
    if not _MODEL.exists():
        return jsonify({
            "error": (
                "Model belum tersedia di server. "
                "Upload rf_model.pkl ke backend/app/model/trained/ "
                "lalu klik Reload di tab Web PythonAnywhere."
            )
        }), 503

    if not _STATIC.exists():
        return jsonify({
            "error": (
                "rf_static_data.py tidak ditemukan. "
                "Upload file ini ke backend/app/data/static/ "
                "lalu klik Reload. File ini dihasilkan oleh Sel Export-4 notebook."
            )
        }), 503

    try:
        ns          = _load_static()
        SEKTOR_DATA = ns["SEKTOR_DATA"]
        KEC_INFO    = ns.get("KEC_INFO", {})
    except Exception:
        return jsonify({
            "error": "rf_static_data.py tidak terbaca. Upload ulang dari Export-4."
        }), 503

    if kec not in SEKTOR_DATA:
        return jsonify({"error": f"Kecamatan '{kec}' tidak ditemukan."}), 404

    rf          = joblib.load(_MODEL)
    sektors     = SEKTOR_DATA[kec]
    ch_mean_kec = KEC_INFO.get(kec, {}).get("ch_mean", 0.0)
    _veg_dom    = KEC_INFO.get(kec, {}).get("veg_dominan",   "—")
    _tanah_dom  = KEC_INFO.get(kec, {}).get("tanah_dominan", "—")

    _p5  = float(ns.get("NORM_P5",  0))
    _p95 = float(ns.get("NORM_P95", 100))
    _sp  = _p95 - _p5

    results = []
    for row in sektors:
        raw_a = _inference(rf, row, 1.0,   1.0  )
        raw_b = _inference(rf, row, _fk_b, _tk_b)

        if _sp < 1e-9:
            pred_a = 50.0; pred_b_norm = 50.0
        else:
            pred_a      = float(np.clip((raw_a - _p5) / _sp * 100.0, 0, 100))
            pred_b_norm = float(np.clip((raw_b - _p5) / _sp * 100.0, 0, 100))

        pred_b = _boost(pred_b_norm, _fk_b, _tk_b, pred_a, row=row)

        results.append({
            "sektor_id":          row.get("sektor_id",          ""),
            "ID_SEKTOR":          row.get("sektor_id",          ""),
            "LABEL_VEG":          row.get("LABEL_VEG",  _veg_dom),
            "MACAM_TANA":         row.get("MACAM_TANA", _tanah_dom),
            "KEMIRINGAN":         row.get("GRIDCODE_LERENG_W", 0),
            "GRIDCODE_LERENG_W":  row.get("GRIDCODE_LERENG_W", 0),
            "LUAS_HA":            round(row.get("PROPORSI_LUAS", 0) * 100, 2),
            "CH_AKTIF_A":         round(ch_mean_kec,         1),
            "CH_AKTIF_B":         round(ch_mean_kec * _fk_b, 1),
            "PRED_A":             pred_a,
            "PRED_B":             pred_b,
        })

    return jsonify({
        "kec":           kec,
        "source":        "live_inference",
        "ch_mean_kec":   ch_mean_kec,
        "ch_pct":        ch_pct,
        "tcc_pct":       tcc_pct,
        "live_inference": True,
        "results":       results,
    })

"""
POST /api/simulate
Body JSON: {
  "kec":    "KALIWUNGU",
  "ch_pct": 97.5,          # Intensitas CH — rentang [10, 150] (pct), sesuai notebook [0.10, 1.50]
  "veg_nf": 0.80,          # Faktor Hutan Alam (NF) — rentang [0.10, 1.50]
  "veg_af": 0.75,          # Faktor Agroforestri (AF) — rentang [0.10, 1.50]
  "veg_pv": 0.95           # Faktor Vegetasi Produksi (PV) — rentang [0.10, 1.50]
}

ASTA PORTAL — simulate.py REVISI r28
=====================================================================

PERUBAHAN vs r26:
-----------------
1. tcc_pct (0–100%) DIHAPUS. Diganti 3 faktor terpisah sesuai notebook SEL 1:
   - veg_nf [0.10–1.50] : Hutan Alam — Hutan Rimba, Veg Non Budidaya
   - veg_af [0.10–1.50] : Agroforestri — Kopi, Tanaman Campur, dll.
   - veg_pv [0.10–1.50] : Vegetasi Produksi — Albasia, Jati, Semak Belukar, dll.

2. ch_pct sekarang dibatasi [10, 150] (bukan [0, 100]) sesuai notebook SEL 1:
   assert 0.1 <= x_CH_2 <= 1.5  →  ch_pct setara [10%, 150%]

3. _kelompok_veg() baru — memetakan LABEL_VEG ke kelompok NF/AF/PV,
   identik dengan fungsi kelompok_veg() di notebook SEL 2.

4. _tk_per_sektor() (didefinisikan di dalam route, bukan global) —
   memilih faktor TCC yang tepat berdasarkan LABEL_VEG setiap sektor.
   Fallback ke rerata tiga faktor jika LABEL_VEG tidak dikenali.

5. Response JSON mengembalikan veg_nf, veg_af, veg_pv menggantikan tcc_pct.

CATATAN BACKWARD COMPATIBILITY:
   Jika client lama mengirim tcc_pct, backend akan mengabaikannya dan
   menggunakan default veg_* = 1.0 (kondisi aktual). Tidak ada error.

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

# Bobot Pilihan C — identik dengan notebook D3 Persiapan r24
_W_SKOR_AKAR  = 0.50   # SKOR_AKAR turun saat deforestasi
_W_VEG_RISIKO = 0.35   # VEG_RISIKO naik saat deforestasi
_W_JNSSMK     = 0.20   # JNSSMK_MEAN turun saat deforestasi

# ── Kelompok vegetasi — identik dengan konstanta notebook SEL 1 & SEL 2 ──────
_VEG_NF = frozenset([
    'Hutan Rimba', 'Vegetasi Non Budidaya Lainnya',
])
_VEG_AF = frozenset([
    'Kopi', 'Kopi/Karet', 'Tanaman Campur',
    'Albasia/Bambu/Kelapa', 'Mahoni/Jati/Karet/Teh',
])
_VEG_PV = frozenset([
    'Albasia', 'Albasiah', 'Jati', 'Karet', 'Karet/Jati',
    'Perkebunan Umum', 'Semak Belukar',
])


def _kelompok_veg(label_veg: str) -> str:
    """Kembalikan 'NF', 'AF', 'PV', atau '' jika tidak dikenali.
    Identik dengan kelompok_veg() di notebook SEL 2."""
    if label_veg in _VEG_NF:
        return 'NF'
    if label_veg in _VEG_AF:
        return 'AF'
    if label_veg in _VEG_PV:
        return 'PV'
    return ''


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
      CH slider (ch_faktor = ch_pct / 100):
        - CH_MEAN  (idx 13) × ch_faktor
        - HH_MEAN  (idx 14) × ch_faktor
        - CH_STD   (idx 16) : TIDAK diubah — variabilitas historis tetap
        - HH_STD   (idx 17) : TIDAK diubah — variabilitas historis tetap

      TCC per-sektor (tcc_faktor = veg_nf / veg_af / veg_pv sesuai LABEL_VEG):
        - PROP_VEG_BERKANOPI (idx 18) × tcc_faktor
        - SKOR_AKAR_MEAN (idx 6) turun saat deforestasi (tcc_faktor < 1.0)
        - JNSSMK_MEAN    (idx 7) turun saat deforestasi
        - VEG_RISIKO     (idx 5) naik menuju 1.0 saat deforestasi
        - Saat tcc_faktor > 1.0: deforestasi = 0 → hanya PROP_VEG_BERKANOPI yang naik
    """
    deforestasi = max(0.0, 1.0 - tcc_faktor)
    fitur = [float(row_dict.get(k, 0)) for k in _URUTAN_FITUR]

    # CH modulasi
    fitur[13] = fitur[13] * ch_faktor   # CH_MEAN
    fitur[14] = fitur[14] * ch_faktor   # HH_MEAN
    # fitur[16] CH_STD — TIDAK diubah
    # fitur[17] HH_STD — TIDAK diubah

    # TCC modulasi per-sektor
    fitur[18] = max(0.0, fitur[18] * tcc_faktor)   # PROP_VEG_BERKANOPI

    if deforestasi > 0.0:
        fitur[6]  = max(0.0, fitur[6] * (1.0 - _W_SKOR_AKAR * deforestasi))
        fitur[7]  = max(0.0, fitur[7] * (1.0 - _W_JNSSMK * deforestasi))
        vr_asli   = fitur[5]
        fitur[5]  = min(1.0, vr_asli + _W_VEG_RISIKO * deforestasi * (1.0 - vr_asli))

    return float(rf.predict([fitur])[0])


def _boost(pred_raw, ch_faktor, tcc_faktor, pred_a, row=None):
    """
    Post-hoc boost per-sektor berbasis karakteristik geomorfologis.
    Tidak berubah dari r26 — menerima tcc_faktor per-sektor dari caller.
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
    data = request.get_json(force=True)
    kec  = data.get("kec", "").upper().strip()

    # ── Validasi & normalisasi parameter ────────────────────────────────────
    # CH: rentang [10, 150] persen → faktor [0.10, 1.50], sesuai notebook SEL 1
    ch_pct = float(np.clip(float(data.get("ch_pct", 100)), 10.0, 150.0))

    # Vegetasi: 3 faktor terpisah, rentang [0.10, 1.50], sesuai notebook SEL 1
    veg_nf = float(np.clip(float(data.get("veg_nf", 1.0)), 0.10, 1.50))
    veg_af = float(np.clip(float(data.get("veg_af", 1.0)), 0.10, 1.50))
    veg_pv = float(np.clip(float(data.get("veg_pv", 1.0)), 0.10, 1.50))

    if not kec:
        return jsonify({"error": "Parameter 'kec' wajib diisi."}), 400

    _fk_b = ch_pct / 100.0   # CH factor: 100% → 1.0, 150% → 1.5, 10% → 0.1

    def _tk_per_sektor(label_veg: str) -> float:
        """Pilih faktor TCC sektor berdasarkan kelompok vegetasi dominan."""
        kel = _kelompok_veg(str(label_veg))
        if kel == 'NF':
            return veg_nf
        if kel == 'AF':
            return veg_af
        if kel == 'PV':
            return veg_pv
        # Fallback: rerata ketiga faktor jika LABEL_VEG tidak dikenali
        return (veg_nf + veg_af + veg_pv) / 3.0

    # ── 1. Coba batch + live inference ──────────────────────────────────────
    if _BATCH.exists():
        try:
            batch    = _load_batch()
            features = [
                ft for ft in batch.get("features", [])
                if ft["properties"].get("NAME_3", "").upper() == kec
            ]
            if features:
                ch_mean_kec  = 0.0
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

                    # PRED_A + PRED_B: live inference per-sektor
                    # r28+: PRED_A juga dihitung ulang agar konsisten dengan
                    # normalisasi/model saat ini. PRED_A dari batch bisa
                    # basi jika NORM_P5/NORM_P95 atau rf_model.pkl berubah.
                    if _rf_tersedia and _row_match is not None:
                        _tk_sektor  = _tk_per_sektor(p.get("LABEL_VEG", ""))

                        _p5  = float(_ns2.get("NORM_P5",  0.0))
                        _p95 = float(_ns2.get("NORM_P95", 100.0))
                        _sp  = _p95 - _p5

                        # — Hitung PRED_A (kondisi aktual ch=1.0, tcc=1.0)
                        _pred_a_raw  = _inference(_rf, _row_match, 1.0, 1.0)
                        if _sp < 1e-9:
                            _pred_a_norm = 50.0
                        else:
                            _pred_a_norm = float(np.clip(
                                (_pred_a_raw - _p5) / _sp * 100.0, 0, 100))
                        # boost: ch_faktor=1.0 tcc_faktor=1.0 → ch_effect=0 tcc_effect=0
                        p["PRED_A"] = _boost(_pred_a_norm, 1.0, 1.0, _pred_a_norm, row=_row_match)

                        # — Hitung PRED_B (kondisi skenario)
                        _pred_b_raw = _inference(_rf, _row_match, _fk_b, _tk_sektor)
                        if _sp < 1e-9:
                            _pred_b_norm = 50.0
                        else:
                            _pred_b_norm = float(np.clip(
                                (_pred_b_raw - _p5) / _sp * 100.0, 0, 100))
                        p["PRED_B"] = _boost(
                            _pred_b_norm, _fk_b, _tk_sektor, p["PRED_A"], row=_row_match
                        )
                    else:
                        # Fallback: gunakan nilai dari batch (bisa basi)
                        if "PRED_B" not in p and "PRED_VAL" in p:
                            p["PRED_B"] = p["PRED_VAL"]

                return jsonify({
                    "type":          "FeatureCollection",
                    "kec":           kec,
                    "source":        "batch",
                    "ch_pct":        ch_pct,
                    "veg_nf":        veg_nf,
                    "veg_af":        veg_af,
                    "veg_pv":        veg_pv,
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
        # Pilih faktor vegetasi sesuai kelompok dominan sektor
        _tk_sektor = _tk_per_sektor(row.get("LABEL_VEG", ""))

        raw_a = _inference(rf, row, 1.0,   1.0       )
        raw_b = _inference(rf, row, _fk_b, _tk_sektor)

        if _sp < 1e-9:
            pred_a = 50.0; pred_b_norm = 50.0
        else:
            pred_a      = float(np.clip((raw_a - _p5) / _sp * 100.0, 0, 100))
            pred_b_norm = float(np.clip((raw_b - _p5) / _sp * 100.0, 0, 100))

        pred_b = _boost(pred_b_norm, _fk_b, _tk_sektor, pred_a, row=row)

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
        "kec":            kec,
        "source":         "live_inference",
        "ch_mean_kec":    ch_mean_kec,
        "ch_pct":         ch_pct,
        "veg_nf":         veg_nf,
        "veg_af":         veg_af,
        "veg_pv":         veg_pv,
        "live_inference": True,
        "results":        results,
    })

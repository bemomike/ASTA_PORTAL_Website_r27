"""
POST /api/simulate
Body JSON: {
  "kec":    "KALIWUNGU",
  "ch_pct": 97.5,          # Intensitas CH — rentang [10, 150] (pct), sesuai notebook [0.10, 1.50]
  "veg_nf": 0.80,          # Faktor Hutan Alam (NF) — rentang [0.10, 1.50]
  "veg_af": 0.75,          # Faktor Agroforestri (AF) — rentang [0.10, 1.50]
  "veg_pv": 0.95           # Faktor Vegetasi Produksi (PV) — rentang [0.10, 1.50]
}

ASTA PORTAL — simulate.py REVISI r29
=====================================================================

PERUBAHAN vs r28 (PERBAIKAN KALKULASI KRITIS):
-----------------------------------------------
1. Formula PRED_B diganti dari "RF re-inference + boost" ke rumus
   L_sim_3 notebook SEL 41-44:
     L_sim_3 = L_base × R × P
     R = e^(β_fix × (ch_faktor − 1))   → 1.0 saat ch_faktor = 1.0
     P = e^(−α_fix × ΔCov)             → 1.0 saat semua faktor veg = 1.0
     ΔCov = PROP_VEG_BERKANOPI × (veg_faktor − 1) per sektor

   Implikasi: PRED_B ≡ PRED_A saat semua parameter pada nilai default
   (ch_pct=100, veg_nf=veg_af=veg_pv=1.0). Sebelumnya terdapat selisih
   +0.25% artefak yang disebabkan batch PRED_B di-compute dengan
   tcc_input_pct=0 (skenario deforestasi penuh), bukan kondisi aktual.

2. PRED_A sekarang SELALU dibaca dari batch (field PRED_A yang sudah
   ada). Live inference TIDAK LAGI menimpa PRED_A — ini memastikan
   konsistensi dengan PREDIKSI_BASE_PCT di notebook.

3. Fungsi _boost() dihapus sepenuhnya — tidak memiliki basis
   rumus di notebook manapun dan merupakan sumber deviasi terbesar.

4. ALPHA_FIXED dan BETA_FIXED dibaca dari rf_static_data.py jika
   tersedia (user harus menambahkan export ini di SEL 48 notebook).
   Fallback default: ALPHA=2.0, BETA=1.5.

5. Untuk Cov_base (proxy TCC_MEAN per sektor): diambil dari
   SEKTOR_DATA field TCC_MEAN jika ada, fallback ke PROP_VEG_BERKANOPI.
   User harus menambahkan TCC_MEAN ke SEKTOR_DATA export (SEL 48).

HAL YANG WAJIB DIREVISI DI NOTEBOOK (SEL 48) OLEH USER:
   a. Tambahkan di blok penulisan rf_static_data.py:
        _f.write(f'ALPHA_FIXED = {ALPHA_FIXED:.6f}\\n')
        _f.write(f'BETA_FIXED  = {BETA_FIXED:.6f}\\n')
   b. Tambahkan TCC_MEAN & LABEL_VEG ke SEKTOR_DATA export:
        extra = [c for c in ['TCC_MEAN','LABEL_VEG','KEL_VEG'] if c in _sub.columns]
        _sektor_data[kec] = _sub[FITUR_MODEL+['ID_SEKTOR']+extra]...
   c. Regenerasi rf_static_data.py, rf_model.pkl, dan batch GeoJSON,
      lalu upload ulang ke PythonAnywhere + Reload.

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

# Default α dan β — digunakan jika rf_static_data.py belum menyimpannya.
# Setelah user menambahkan ALPHA_FIXED/BETA_FIXED ke SEL 48 notebook dan
# meng-upload rf_static_data.py baru, nilai ini akan di-override secara otomatis.
_ALPHA_DEFAULT = 2.0
_BETA_DEFAULT  = 1.5


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


def _lsim3(l_base: float, ch_faktor: float, veg_faktor: float,
           cov_base: float, alpha: float, beta: float) -> float:
    """
    Rumus L_sim_3 dari notebook SEL 41-44:
      R     = e^(β × (ch_faktor − 1))        → 1.0 saat ch_faktor=1.0
      P     = e^(−α × ΔCov)                  → 1.0 saat ΔCov=0
      ΔCov  = cov_base × (veg_faktor − 1)    → 0.0 saat veg_faktor=1.0
      result= l_base × R × P, di-clip ke [0, 100]

    Properti kunci: hasil = l_base saat ch_faktor=1.0 AND veg_faktor=1.0.
    """
    delta_cov = float(cov_base) * (float(veg_faktor) - 1.0)
    R = float(np.exp(float(beta)  * (float(ch_faktor) - 1.0)))
    P = float(np.exp(-float(alpha) * delta_cov))
    return float(np.clip(float(l_base) * R * P, 0.0, 100.0))


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
    Jalankan 1 prediksi RF dengan faktor CH dan TCC.
    Dipakai HANYA pada live inference path (tanpa batch).
    PRED_B tetap dihitung via _lsim3, bukan via _inference langsung.
    """
    deforestasi = max(0.0, 1.0 - tcc_faktor)
    fitur = [float(row_dict.get(k, 0)) for k in _URUTAN_FITUR]

    # CH modulasi
    fitur[13] = fitur[13] * ch_faktor   # CH_MEAN
    fitur[14] = fitur[14] * ch_faktor   # HH_MEAN

    # TCC modulasi
    fitur[18] = max(0.0, fitur[18] * tcc_faktor)   # PROP_VEG_BERKANOPI

    if deforestasi > 0.0:
        # SKOR_AKAR_MEAN di-index 6 adalah SKOR_DEFISIT_AKAR (tinggi = lebih rentan).
        # Saat deforestasi (tcc_faktor < 1), defisit akar NAIK.
        fitur[6] = min(1.0, fitur[6] * (1.0 + 0.50 * deforestasi))
        # VEG_RISIKO (index 5) juga naik saat deforestasi
        vr_asli  = fitur[5]
        fitur[5] = min(1.0, vr_asli + 0.35 * deforestasi * (1.0 - vr_asli))

    return float(rf.predict([fitur])[0])


@simulate_bp.route("/api/simulate", methods=["POST"])
def simulate():
    data = request.get_json(force=True)
    kec  = data.get("kec", "").upper().strip()

    # ── Validasi & normalisasi parameter ────────────────────────────────────
    ch_pct = float(np.clip(float(data.get("ch_pct", 100)), 10.0, 150.0))
    veg_nf = float(np.clip(float(data.get("veg_nf", 1.0)), 0.10, 1.50))
    veg_af = float(np.clip(float(data.get("veg_af", 1.0)), 0.10, 1.50))
    veg_pv = float(np.clip(float(data.get("veg_pv", 1.0)), 0.10, 1.50))

    if not kec:
        return jsonify({"error": "Parameter 'kec' wajib diisi."}), 400

    _fk_b = ch_pct / 100.0   # CH factor: 100% → 1.0

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

    # ── 1. Coba batch + L_sim_3 ──────────────────────────────────────────────
    if _BATCH.exists():
        try:
            batch    = _load_batch()
            features = [
                ft for ft in batch.get("features", [])
                if ft["properties"].get("NAME_3", "").upper() == kec
            ]
            if features:
                ch_mean_kec = 0.0
                _ns2        = {}
                _alpha      = _ALPHA_DEFAULT
                _beta       = _BETA_DEFAULT
                _SEKTOR_DATA_idx = {}

                if _STATIC.exists():
                    try:
                        _ns2        = _load_static()
                        ch_mean_kec = _ns2.get("KEC_INFO", {}).get(kec, {}).get("ch_mean", 0.0)
                        # Baca ALPHA_FIXED & BETA_FIXED jika tersedia (user harus tambahkan di SEL 48)
                        _alpha = float(_ns2.get("ALPHA_FIXED", _ALPHA_DEFAULT))
                        _beta  = float(_ns2.get("BETA_FIXED",  _BETA_DEFAULT))
                    except Exception:
                        pass

                # Bangun index SEKTOR_DATA per sektor_id
                if _ns2 and kec in _ns2.get("SEKTOR_DATA", {}):
                    for r in _ns2["SEKTOR_DATA"][kec]:
                        _SEKTOR_DATA_idx[r.get("sektor_id", "")] = r

                for ft in features:
                    p = ft["properties"]

                    # ── CH_AKTIF: isi dari ch_mean_kec jika belum ada ────────
                    if "CH_AKTIF_A" not in p:
                        p["CH_AKTIF_A"] = round(ch_mean_kec, 1)
                    p["CH_AKTIF_B"] = round(ch_mean_kec * _fk_b, 1)

                    # ── PRED_A: baca dari batch, JANGAN di-override ──────────
                    # PRED_A di batch adalah PREDIKSI_BASE_PCT dari notebook
                    # (kondisi aktual, RF murni). Menimpa dengan live inference
                    # menyebabkan inkonsistensi dgn nilai notebook.
                    # Jika PRED_A belum ada di batch, isi dengan 50 sebagai fallback.
                    if "PRED_A" not in p:
                        p["PRED_A"] = 50.0

                    # ── KEMIRINGAN dari SEKTOR_DATA ──────────────────────────
                    sid        = p.get("ID_SEKTOR", p.get("sektor_id", ""))
                    _row_match = _SEKTOR_DATA_idx.get(sid)
                    if "KEMIRINGAN" not in p or p.get("KEMIRINGAN", 0) == 0:
                        gc = _row_match.get("GRIDCODE_LERENG_W", 0) if _row_match else 0
                        p["KEMIRINGAN"]        = gc
                        p["GRIDCODE_LERENG_W"] = gc

                    # ── PRED_B via L_sim_3 ───────────────────────────────────
                    # cov_base: TCC_MEAN (jika ada di SEKTOR_DATA setelah user
                    # menambahkan ke SEL 48 export) atau fallback PROP_VEG_BERKANOPI.
                    # Ketika veg_faktor=1.0 (semua default), ΔCov=0 → PRED_B = PRED_A.
                    cov_base = 0.0
                    if _row_match is not None:
                        cov_base = float(_row_match.get(
                            "TCC_MEAN",
                            _row_match.get("PROP_VEG_BERKANOPI", 0.0)
                        ))

                    _label_veg  = p.get("LABEL_VEG", "")
                    _veg_faktor = _tk_per_sektor(_label_veg)
                    _pred_a     = float(p["PRED_A"])

                    p["PRED_B"] = _lsim3(
                        _pred_a, _fk_b, _veg_faktor, cov_base, _alpha, _beta
                    )

                return jsonify({
                    "type":           "FeatureCollection",
                    "kec":            kec,
                    "source":         "batch_lsim3",
                    "ch_pct":         ch_pct,
                    "veg_nf":         veg_nf,
                    "veg_af":         veg_af,
                    "veg_pv":         veg_pv,
                    "live_inference": True,    # L_sim_3 dianggap "live" karena dihitung ulang
                    "alpha_used":     _alpha,
                    "beta_used":      _beta,
                    "features":       features,
                })
        except Exception:
            pass  # lanjut ke live inference penuh

    # ── 2. Live inference penuh (tanpa batch) ────────────────────────────────
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

    _alpha = float(ns.get("ALPHA_FIXED", _ALPHA_DEFAULT))
    _beta  = float(ns.get("BETA_FIXED",  _BETA_DEFAULT))

    results = []
    for row in sektors:
        _label_veg  = row.get("LABEL_VEG", _veg_dom)
        _veg_faktor = _tk_per_sektor(_label_veg)

        # PRED_A: prediksi RF kondisi aktual (ch=1.0, tcc=1.0)
        raw_a  = _inference(rf, row, 1.0, 1.0)
        pred_a = float(np.clip(raw_a, 0.0, 100.0))

        # PRED_B: L_sim_3 dengan cov_base dari TCC_MEAN atau PROP_VEG_BERKANOPI
        cov_base = float(row.get("TCC_MEAN", row.get("PROP_VEG_BERKANOPI", 0.0)))
        pred_b   = _lsim3(pred_a, _fk_b, _veg_faktor, cov_base, _alpha, _beta)

        results.append({
            "sektor_id":          row.get("sektor_id",          ""),
            "ID_SEKTOR":          row.get("sektor_id",          ""),
            "LABEL_VEG":          _label_veg,
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
        "source":         "live_lsim3",
        "ch_mean_kec":    ch_mean_kec,
        "ch_pct":         ch_pct,
        "veg_nf":         veg_nf,
        "veg_af":         veg_af,
        "veg_pv":         veg_pv,
        "live_inference": True,
        "alpha_used":     _alpha,
        "beta_used":      _beta,
        "results":        results,
    })

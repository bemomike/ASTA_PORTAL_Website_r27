"""
POST /api/simulate
Body JSON: {
  "kec":    "KALIWUNGU",
  "ch_pct": 100,        # Intensitas CH — rentang [10, 150] (pct), x_CH_2 = ch_pct/100
  "veg_nf": 1.00,       # Faktor Hutan Alam (NF)          — rentang [0.10, 1.50]
  "veg_af": 1.00,       # Faktor Agroforestri (AF)         — rentang [0.10, 1.50]
  "veg_pv": 1.00        # Faktor Vegetasi Produksi (PV)    — rentang [0.10, 1.50]
}

ASTA PORTAL — simulate.py r29 (L_sim_3 FAITHFUL)
=====================================================================

PERBAIKAN FUNDAMENTAL vs r28:
------------------------------
r26–r28 menggunakan _inference() + _boost() — yaitu:
  1. Menjalankan RF model secara live dengan fitur yang dimodifikasi, lalu
  2. Menambahkan post-hoc boost berbasis geomorfologi.
Pendekatan ini BERBEDA SECARA FUNDAMENTAL dari rumus notebook, sehingga
hasilnya melenceng dari notebook meski input identik.

r29 menggantinya dengan implementasi L_sim_3 yang 100% identik notebook
SEL 41-44 v3.2:

  L_sim_3 = clip(L_base × R × P, 0, 100)
  R       = exp(BETA_FIXED  × (x_CH_2 − 1))
  P       = exp(−ALPHA_FIXED × ΔCov_i)
  ΔCov_i  = BOBOT_KEL_i × TCC_i × (x_Veg_i − 1) / (BOBOT_NF + BOBOT_AF + BOBOT_PV)

Keterangan per-sektor:
  L_base  = PRED_A = PREDIKSI_BASE_PCT dari SEL 36 (RF murni kondisi aktual)
  TCC_i   = TCC_MEAN sektor i (dari kolom TCC_MEAN df_model)
  BOBOT_KEL_i = BOBOT_NF / BOBOT_AF / BOBOT_PV sesuai KEL_VEG sektor i
  x_Veg_i = veg_nf / veg_af / veg_pv sesuai KEL_VEG sektor i
  x_CH_2  = ch_pct / 100

Konsistensi:
  x_CH_2 = 1.0 dan semua veg = 1.0  →  R=1, ΔCov=0, P=1  →  PRED_B = PRED_A  ✓
  Sama persis dengan Skenario I ✓

Persyaratan rf_static_data.py (format baru dari notebook SEL 48 yang diperbarui):
  ALPHA_FIXED, BETA_FIXED, BOBOT_NF, BOBOT_AF, BOBOT_PV
  SEKTOR_DATA[kec][*]:
    sektor_id, PRED_A, TCC_MEAN, KEL_VEG, LABEL_VEG,
    MACAM_TANA, Kelas, GRIDCODE_LERENG_W, LUAS_HA
  KEC_INFO[kec]: ch_mean, tanah_dominan, veg_dominan
=====================================================================
"""
import json
import math
import numpy as np
from pathlib import Path
from flask import Blueprint, request, jsonify

simulate_bp = Blueprint("simulate", __name__)

_BASE   = Path(__file__).resolve().parents[1]
_BATCH  = _BASE / "data/batch/simulasi_batch_19kec.geojson"
_STATIC = _BASE / "data/static/rf_static_data.py"

# ── Pemetaan kelompok vegetasi — identik notebook SEL 2 ─────────────────────
_VEG_NF = frozenset(['Hutan Rimba', 'Vegetasi Non Budidaya Lainnya'])
_VEG_AF = frozenset([
    'Kopi', 'Kopi/Karet', 'Tanaman Campur',
    'Albasia/Bambu/Kelapa', 'Mahoni/Jati/Karet/Teh',
])
_VEG_PV = frozenset([
    'Albasia', 'Albasiah', 'Jati', 'Karet', 'Karet/Jati',
    'Perkebunan Umum', 'Semak Belukar',
])


def _kelompok_veg(label_veg: str) -> str:
    if label_veg in _VEG_NF: return 'NF'
    if label_veg in _VEG_AF: return 'AF'
    if label_veg in _VEG_PV: return 'PV'
    return ''


def _load_static():
    ns = {}
    with open(_STATIC, encoding="utf-8") as f:
        exec(f.read(), ns)
    return ns


def _load_batch():
    with open(_BATCH, encoding="utf-8") as f:
        return json.load(f)


def _l_sim_3(pred_a: float, tcc_mean: float, kel_veg: str,
             ch_pct: float, veg_nf: float, veg_af: float, veg_pv: float,
             alpha: float, beta: float,
             bobot_nf: float, bobot_af: float, bobot_pv: float) -> float:
    """
    Implementasi L_sim_3 per-sektor — identik notebook SEL 41.

    ΔCov_i  = BOBOT_KEL_i × TCC_i × (x_Veg_i − 1) / dn
    R       = exp(β × (x_CH_2 − 1))
    P       = exp(−α × ΔCov_i)
    L_sim_3 = clip(L_base × R × P, 0, 100)
    """
    dn    = bobot_nf + bobot_af + bobot_pv
    x_ch  = ch_pct / 100.0  # konversi persentase → faktor

    # Pilih bobot & faktor vegetasi sesuai kelompok sektor
    if kel_veg == 'NF':
        bobot_i = bobot_nf; x_veg_i = veg_nf
    elif kel_veg == 'AF':
        bobot_i = bobot_af; x_veg_i = veg_af
    elif kel_veg == 'PV':
        bobot_i = bobot_pv; x_veg_i = veg_pv
    else:
        # LABEL_VEG tidak teridentifikasi → tidak ada pengaruh vegetasi
        bobot_i = 0.0; x_veg_i = 1.0

    delta_cov = bobot_i * tcc_mean * (x_veg_i - 1.0) / max(dn, 1e-9)
    R = math.exp(beta  * (x_ch - 1.0))
    P = math.exp(-alpha * delta_cov)
    return float(np.clip(pred_a * R * P, 0.0, 100.0))


@simulate_bp.route("/api/simulate", methods=["POST"])
def simulate():
    data   = request.get_json(force=True)
    kec    = data.get("kec", "").upper().strip()

    # ── Validasi & normalisasi parameter ────────────────────────────────────
    ch_pct = float(np.clip(float(data.get("ch_pct", 100)), 10.0, 150.0))
    veg_nf = float(np.clip(float(data.get("veg_nf", 1.0)), 0.10, 1.50))
    veg_af = float(np.clip(float(data.get("veg_af", 1.0)), 0.10, 1.50))
    veg_pv = float(np.clip(float(data.get("veg_pv", 1.0)), 0.10, 1.50))

    if not kec:
        return jsonify({"error": "Parameter 'kec' wajib diisi."}), 400

    # ── Cek ketersediaan rf_static_data.py ──────────────────────────────────
    if not _STATIC.exists():
        return jsonify({
            "error": (
                "rf_static_data.py tidak ditemukan. "
                "Upload file ini ke backend/app/data/static/ "
                "lalu klik Reload di tab Web PythonAnywhere."
            )
        }), 503

    try:
        ns = _load_static()
    except Exception as exc:
        return jsonify({
            "error": f"rf_static_data.py tidak terbaca: {exc}. Upload ulang dari SEL 48."
        }), 503

    # ── Konstanta kalibrasi (dari SEL 41) ───────────────────────────────────
    alpha    = float(ns.get("ALPHA_FIXED", 0.5))
    beta_val = float(ns.get("BETA_FIXED",  0.5))
    bobot_nf = float(ns.get("BOBOT_NF", 1.00))
    bobot_af = float(ns.get("BOBOT_AF", 0.75))
    bobot_pv = float(ns.get("BOBOT_PV", 0.45))

    SEKTOR_DATA = ns.get("SEKTOR_DATA", {})
    KEC_INFO    = ns.get("KEC_INFO", {})

    if kec not in SEKTOR_DATA:
        return jsonify({"error": f"Kecamatan '{kec}' tidak ditemukan dalam rf_static_data.py."}), 404

    sektors = SEKTOR_DATA[kec]

    # ── Cek format baru (wajib ada PRED_A) ──────────────────────────────────
    if not sektors or "PRED_A" not in sektors[0]:
        return jsonify({
            "error": (
                "rf_static_data.py menggunakan format LAMA — tidak ada kolom PRED_A. "
                "Jalankan SEL 48 versi baru di notebook (tambahkan blok ekspor L_sim_3), "
                "lalu upload ulang rf_static_data.py dan klik Reload."
            )
        }), 503

    ch_mean_kec = float(KEC_INFO.get(kec, {}).get("ch_mean", 0.0))
    _fk_b       = ch_pct / 100.0

    # ── Hitung L_sim_3 per sektor ────────────────────────────────────────────
    results_by_sid: dict = {}
    for row in sektors:
        sid      = str(row.get("sektor_id", row.get("ID_SEKTOR", "")))
        pred_a   = float(row.get("PRED_A", 0.0))
        tcc_mean = float(row.get("TCC_MEAN", 0.0))
        # KEL_VEG dari data; fallback dari LABEL_VEG
        kel_veg  = str(row.get("KEL_VEG", ""))
        if not kel_veg:
            kel_veg = _kelompok_veg(str(row.get("LABEL_VEG", "")))

        pred_b = _l_sim_3(
            pred_a, tcc_mean, kel_veg, ch_pct,
            veg_nf, veg_af, veg_pv,
            alpha, beta_val, bobot_nf, bobot_af, bobot_pv,
        )

        results_by_sid[sid] = {
            "sektor_id":         sid,
            "ID_SEKTOR":         sid,
            "LABEL_VEG":         row.get("LABEL_VEG", "—"),
            "KEL_VEG":           kel_veg,
            "MACAM_TANA":        row.get("MACAM_TANA", "—"),
            "KEMIRINGAN":        row.get("GRIDCODE_LERENG_W", 0),
            "GRIDCODE_LERENG_W": row.get("GRIDCODE_LERENG_W", 0),
            "LUAS_HA":           round(float(row.get("LUAS_HA", 0)), 2),
            "CH_AKTIF_A":        round(ch_mean_kec, 1),
            "CH_AKTIF_B":        round(ch_mean_kec * _fk_b, 1),
            "PRED_A":            round(pred_a, 4),
            "PRED_B":            round(pred_b, 4),
        }

    # ── Coba pakai batch GeoJSON untuk geometry ──────────────────────────────
    _use_batch = False
    _batch_idx: dict = {}
    if _BATCH.exists():
        try:
            batch = _load_batch()
            for ft in batch.get("features", []):
                p   = ft["properties"]
                if p.get("NAME_3", "").upper() == kec:
                    sid = str(p.get("ID_SEKTOR", p.get("sektor_id", "")))
                    _batch_idx[sid] = ft
            _use_batch = bool(_batch_idx)
        except Exception:
            _use_batch = False

    if _use_batch:
        features = []
        for sid, ft in _batch_idx.items():
            if sid in results_by_sid:
                ft["properties"].update(results_by_sid[sid])
            else:
                ft["properties"]["PRED_A"] = ft["properties"].get("PRED_A", 0)
                ft["properties"]["PRED_B"] = ft["properties"].get("PRED_A", 0)
            features.append(ft)
        # Sektor di SEKTOR_DATA tapi tidak di batch (batas geometry tidak tersedia)
        for sid, r in results_by_sid.items():
            if sid not in _batch_idx:
                features.append({"type": "Feature", "geometry": None, "properties": r})

        return jsonify({
            "type":          "FeatureCollection",
            "kec":           kec,
            "source":        "batch+l_sim_3",
            "ch_pct":        ch_pct,
            "veg_nf":        veg_nf,
            "veg_af":        veg_af,
            "veg_pv":        veg_pv,
            "live_inference": True,
            "features":      features,
        })

    # ── Fallback: kembalikan array results tanpa geometry ────────────────────
    return jsonify({
        "kec":            kec,
        "source":         "l_sim_3",
        "ch_mean_kec":    ch_mean_kec,
        "ch_pct":         ch_pct,
        "veg_nf":         veg_nf,
        "veg_af":         veg_af,
        "veg_pv":         veg_pv,
        "live_inference": True,
        "results":        list(results_by_sid.values()),
    })

"""
GET /api/info/<kec_nama>
Mengembalikan ringkasan kecamatan termasuk daftar jenis pohon,
jenis tanah, dan label kemiringan lereng yang dihitung dari SEKTOR_DATA.

r28 PERBAIKAN:
- lereng_label sebelumnya TIDAK pernah dikembalikan oleh endpoint ini.
  ui.js membaca data?.lereng_label untuk panel Kemiringan Lereng,
  sehingga panel selalu menampilkan "Tidak ada data".
- veg_list dan tanah_list sebelumnya membaca field 'VEG_ENC' dan
  'TANAH_ENC' dari SEKTOR_DATA — field ini TIDAK selalu ada di
  rf_static_data.py yang diekspor dari notebook.
  Perbaikan (r28+): baca langsung dari file veg_<KEC>.geojson dan
  tanah_<KEC>.geojson yang sudah ada di data/geojson/. File-file ini
  SELALU memiliki field LABEL_VEG dan MACAM_TANA sehingga panel
  tidak lagi bergantung pada struktur internal rf_static_data.py.
"""

import json
from pathlib import Path
from flask import Blueprint, jsonify

info_bp = Blueprint('info', __name__)

# Path ke direktori data
_BASE       = Path(__file__).resolve().parents[1]
_STATIC     = _BASE / 'data/static/rf_static_data.py'
_GEOJSON_DIR = _BASE / 'data/geojson'


def _load_static():
    """Eksekusi rf_static_data.py dan kembalikan namespace-nya."""
    ns = {}
    with open(_STATIC, encoding='utf-8') as f:
        exec(f.read(), ns)
    return ns


def _baca_veg_list(kec: str) -> list:
    """
    Baca daftar jenis vegetasi unik dari veg_<KEC>.geojson.
    Fallback ke list kosong jika file tidak ada.
    """
    # Coba dengan spasi (misal: UNGARAN BARAT) dan underscore
    for nama in [kec, kec.replace(' ', '_')]:
        veg_file = _GEOJSON_DIR / f'veg_{nama}.geojson'
        if veg_file.exists():
            try:
                with open(veg_file, encoding='utf-8') as f:
                    data = json.load(f)
                labels = sorted(set(
                    ft['properties'].get('LABEL_VEG', '')
                    for ft in data.get('features', [])
                    if ft['properties'].get('LABEL_VEG')
                ))
                return labels
            except Exception:
                pass
    return []


def _baca_tanah_list(kec: str) -> list:
    """
    Baca daftar jenis tanah unik dari tanah_<KEC>.geojson.
    Fallback ke list kosong jika file tidak ada.
    """
    for nama in [kec, kec.replace(' ', '_')]:
        tanah_file = _GEOJSON_DIR / f'tanah_{nama}.geojson'
        if tanah_file.exists():
            try:
                with open(tanah_file, encoding='utf-8') as f:
                    data = json.load(f)
                labels = sorted(set(
                    ft['properties'].get('MACAM_TANA', '')
                    for ft in data.get('features', [])
                    if ft['properties'].get('MACAM_TANA')
                ))
                return labels
            except Exception:
                pass
    return []


def _hitung_lereng_label(sektors):
    """
    Hitung distribusi kemiringan lereng dari PROP_DATAR, PROP_LANDAI,
    PROP_CURAM seluruh sektor, lalu kembalikan label teks yang deskriptif.
    """
    total = len(sektors)
    if total == 0:
        return None

    sum_datar  = sum(r.get('PROP_DATAR',  0) for r in sektors)
    sum_landai = sum(r.get('PROP_LANDAI', 0) for r in sektors)
    sum_curam  = sum(r.get('PROP_CURAM',  0) for r in sektors)

    rata_datar  = sum_datar  / total
    rata_landai = sum_landai / total
    rata_curam  = sum_curam  / total

    gridcodes = [r.get('GRIDCODE_LERENG_W', 1.0) for r in sektors]
    rata_grid = sum(gridcodes) / len(gridcodes)

    pct_datar  = round(rata_datar  * 100, 1)
    pct_landai = round(rata_landai * 100, 1)
    pct_curam  = round(rata_curam  * 100, 1)

    if rata_grid < 1.10:
        kategori = "Dominan Datar"
    elif rata_grid < 1.40:
        kategori = "Dominan Landai"
    elif rata_grid < 2.00:
        kategori = "Dominan Agak Curam"
    else:
        kategori = "Dominan Curam"

    label = (
        f"{kategori} — "
        f"Datar {pct_datar}% | "
        f"Landai {pct_landai}% | "
        f"Curam {pct_curam}%"
    )
    return label


@info_bp.route('/api/info/<kec_nama>')
def info(kec_nama):
    """Endpoint utama: kembalikan ringkasan lingkungan kecamatan."""
    kec = kec_nama.upper().strip()

    # Muat data statis dari rf_static_data.py
    try:
        ns = _load_static()
        kec_info    = ns.get('KEC_INFO', {})
        sektor_data = ns.get('SEKTOR_DATA', {})
    except FileNotFoundError:
        return jsonify({'error': 'rf_static_data.py belum ada.'}), 503

    if kec not in kec_info:
        return jsonify({'error': f"Kecamatan '{kec}' tidak ditemukan."}), 404

    d       = kec_info[kec]
    sektors = sektor_data.get(kec, [])

    # ── Baca veg/tanah dari geojson (tidak bergantung VEG_ENC di SEKTOR_DATA) ──
    veg_set   = _baca_veg_list(kec)
    tanah_set = _baca_tanah_list(kec)

    # Hitung label kemiringan lereng
    lereng_label = _hitung_lereng_label(sektors)

    return jsonify({
        'kec':                kec,
        'veg_dominan':        d.get('veg_dominan',        '—'),
        'tanah_dominan':      d.get('tanah_dominan',      '—'),
        'veg_list':           veg_set,
        'tanah_list':         tanah_set,
        'lereng_label':       lereng_label,
        'ch_mean':            d.get('ch_mean',            0.0),
        'hh_mean':            d.get('hh_mean',            0.0),
        'tinggi_mean':        d.get('tinggi_mean',        0.0),
        'prop_veg_berkanopi': d.get('prop_veg_berkanopi', 0.0),
        'tcc_mean':           d.get('tcc_mean',           0.0),
    })

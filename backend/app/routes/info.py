"""
GET /api/info/<kec_nama>
Mengembalikan ringkasan kecamatan termasuk daftar lengkap jenis pohon & tanah.
"""
from pathlib import Path
from flask import Blueprint, jsonify

info_bp = Blueprint('info', __name__)

_STATIC = Path(__file__).resolve().parents[1] / 'data/static/rf_static_data.py'

def _load_static():
    ns = {}
    with open(_STATIC, encoding='utf-8') as f:
        exec(f.read(), ns)
    return ns

@info_bp.route('/api/info/<kec_nama>')
def info(kec_nama):
    kec = kec_nama.upper().strip()
    try:
        ns = _load_static()
        kec_info   = ns.get('KEC_INFO', {})
        sektor_data = ns.get('SEKTOR_DATA', {})
    except FileNotFoundError:
        return jsonify({'error': 'rf_static_data.py belum ada.'}), 503

    if kec not in kec_info:
        return jsonify({'error': f"Kecamatan '{kec}' tidak ditemukan."}), 404

    d = kec_info[kec]
    sektors = sektor_data.get(kec, [])

    # Kumpulkan semua jenis unik (urut abjad, tanpa None/kosong)
    veg_set   = sorted(set(r.get('LABEL_VEG','').strip()
                        for r in sektors
                        if r.get('LABEL_VEG','').strip()))
    tanah_set = sorted(set(r.get('MACAM_TANA','').strip()
                        for r in sektors
                        if r.get('MACAM_TANA','').strip()))

    return jsonify({
        'kec':                kec,
        'veg_dominan':        d.get('veg_dominan',       '—'),
        'tanah_dominan':      d.get('tanah_dominan',     '—'),
        'veg_list':           veg_set,    # BARU: semua jenis pohon
        'tanah_list':         tanah_set,  # BARU: semua jenis tanah
        'ch_mean':            d.get('ch_mean',           0.0),
        'hh_mean':            d.get('hh_mean',           0.0),
        'tinggi_mean':        d.get('tinggi_mean',       0.0),
        'prop_veg_berkanopi': d.get('prop_veg_berkanopi',0.0),
        'tcc_mean':           d.get('tcc_mean',          0.0),
    })

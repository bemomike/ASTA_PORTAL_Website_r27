"""
GET /api/info/<kec_nama>
Mengembalikan ringkasan kecamatan termasuk daftar jenis pohon,
jenis tanah, dan label kemiringan lereng yang dihitung dari SEKTOR_DATA.

r28 PERBAIKAN:
- lereng_label sebelumnya TIDAK pernah dikembalikan oleh endpoint ini.
  ui.js membaca data?.lereng_label untuk panel Kemiringan Lereng,
  sehingga panel selalu menampilkan "Tidak ada data".
- veg_list dan tanah_list sebelumnya membaca field 'LABEL_VEG' dan
  'MACAM_TANA' dari SEKTOR_DATA, padahal field tersebut tidak ada di
  SEKTOR_DATA (hanya ada VEG_ENC dan TANAH_ENC).
  Perbaikan: gunakan label lookup dari konstanta yang ada di file ini.
"""

# Import modul yang dibutuhkan
from pathlib import Path
from flask import Blueprint, jsonify

# Inisialisasi blueprint Flask untuk rute /api/info
info_bp = Blueprint('info', __name__)

# Path ke file data statis yang berisi KEC_INFO dan SEKTOR_DATA
_STATIC = Path(__file__).resolve().parents[1] / 'data/static/rf_static_data.py'

# Tabel lookup VEG_ENC → nama vegetasi (sesuai urutan encoding di notebook)
_LABEL_VEG = [
    "Albasia",                          # 0
    "Albasia/Bambu/Kelapa",             # 1
    "Albasiah",                         # 2
    "Hutan Rimba",                      # 3
    "Karet",                            # 4
    "Kopi",                             # 5
    "Kopi/Karet",                       # 6
    "Semak Belukar",                    # 7
    "Jati",                             # 8
    "Perkebunan/Kebun",                 # 9
    "Tanpa Vegetasi",                   # 10
    "Tidak Teridentifikasi",            # 11
    "Vegetasi Non Budidaya Lainnya",    # 12
]

# Tabel lookup TANAH_ENC → nama tanah (sesuai urutan encoding di notebook)
_LABEL_TANAH = [
    "Aluvial Hidromorf",                                        # 0
    "Aluvial Kelabu",                                           # 1
    "Aluvial Kelabu dan Aluvia Coklat Kekelabuan",              # 2
    "Asosiasi Mediteran Coklat Litosol",                        # 3
    "Andosol Coklat dan Latosol Coklat Kemerahan",              # 4
    "Andosol Coklat",                                           # 5
    "Kompleks Andosol Kelabu Tua dan Litosol",                  # 6
    "Kompleks Grumusol Kelabu dan Litosol",                     # 7
    "Mediteran Merah Tua dan Regosol",                          # 8
    "Latosol Coklat",                                           # 9
    "Kompleks Regosol Kelabu dan Grumusol Kelabu Tua",          # 10
    "Regosol Kelabu",                                           # 11
]

def _load_static():
    """Eksekusi rf_static_data.py dan kembalikan namespace-nya."""
    ns = {}
    with open(_STATIC, encoding='utf-8') as f:
        exec(f.read(), ns)
    return ns

def _hitung_lereng_label(sektors):
    """
    Hitung distribusi kemiringan lereng dari PROP_DATAR, PROP_LANDAI,
    PROP_CURAM seluruh sektor, lalu kembalikan label teks yang deskriptif.

    Skala nilai GRIDCODE_LERENG_W:
      1.0       = Datar (PROP_DATAR dominan)
      1.0–1.5   = Landai
      1.5–2.5   = Curam
      > 2.5     = Sangat Curam
    """
    # Hitung rata-rata tertimbang proporsi lereng dari semua sektor
    total = len(sektors)
    if total == 0:
        return None

    # Akumulasi proporsi dari seluruh sektor
    sum_datar  = sum(r.get('PROP_DATAR',  0) for r in sektors)
    sum_landai = sum(r.get('PROP_LANDAI', 0) for r in sektors)
    sum_curam  = sum(r.get('PROP_CURAM',  0) for r in sektors)

    # Hitung rata-rata proporsi per sektor
    rata_datar  = sum_datar  / total
    rata_landai = sum_landai / total
    rata_curam  = sum_curam  / total

    # Hitung rata-rata skor lereng tertimbang (GRIDCODE_LERENG_W)
    gridcodes = [r.get('GRIDCODE_LERENG_W', 1.0) for r in sektors]
    rata_grid = sum(gridcodes) / len(gridcodes)

    # Konversi ke persen untuk tampilan
    pct_datar  = round(rata_datar  * 100, 1)
    pct_landai = round(rata_landai * 100, 1)
    pct_curam  = round(rata_curam  * 100, 1)

    # Tentukan kategori dominan berdasarkan GRIDCODE rata-rata
    if rata_grid < 1.10:
        kategori = "Dominan Datar"
    elif rata_grid < 1.40:
        kategori = "Dominan Landai"
    elif rata_grid < 2.00:
        kategori = "Dominan Agak Curam"
    else:
        kategori = "Dominan Curam"

    # Susun teks label yang informatif untuk ditampilkan di panel
    label = (
        f"{kategori} — "
        f"Datar {pct_datar}% | "
        f"Landai {pct_landai}% | "
        f"Curam {pct_curam}%"
    )
    return label

# Dekorasi route untuk endpoint GET /api/info/<kec_nama>
@info_bp.route('/api/info/<kec_nama>')
def info(kec_nama):
    """Endpoint utama: kembalikan ringkasan lingkungan kecamatan."""
    # Normalisasi nama kecamatan ke huruf kapital
    kec = kec_nama.upper().strip()

    # Muat data statis dari rf_static_data.py
    try:
        ns = _load_static()
        kec_info    = ns.get('KEC_INFO', {})
        sektor_data = ns.get('SEKTOR_DATA', {})
    except FileNotFoundError:
        return jsonify({'error': 'rf_static_data.py belum ada.'}), 503

    # Validasi nama kecamatan
    if kec not in kec_info:
        return jsonify({'error': f"Kecamatan '{kec}' tidak ditemukan."}), 404

    # Ambil data ringkasan dan sektor untuk kecamatan yang dipilih
    d       = kec_info[kec]
    sektors = sektor_data.get(kec, [])

    # Kumpulkan semua jenis vegetasi unik via lookup VEG_ENC → nama
    veg_enc_set = sorted(set(
        r.get('VEG_ENC')
        for r in sektors
        if r.get('VEG_ENC') is not None
    ))
    # Terjemahkan encoding ke nama label, lewati encoding yang tidak dikenal
    veg_set = [
        _LABEL_VEG[enc]
        for enc in veg_enc_set
        if 0 <= enc < len(_LABEL_VEG)
    ]

    # Kumpulkan semua jenis tanah unik via lookup TANAH_ENC → nama
    tanah_enc_set = sorted(set(
        r.get('TANAH_ENC')
        for r in sektors
        if r.get('TANAH_ENC') is not None
    ))
    # Terjemahkan encoding ke nama label, lewati encoding yang tidak dikenal
    tanah_set = [
        _LABEL_TANAH[enc]
        for enc in tanah_enc_set
        if 0 <= enc < len(_LABEL_TANAH)
    ]

    # Hitung label kemiringan lereng dari data distribusi sektor
    lereng_label = _hitung_lereng_label(sektors)

    # Kembalikan JSON response lengkap
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

# ASTA PORTAL — Website Simulasi Longsor r27

**Analisis Sistem Tata guna lahan berbasis Artificial intelligence**  
Tugas Akhir Skripsi — Fakultas Sains dan Matematika UKSW

---

## Deskripsi
ASTA PORTAL adalah website simulasi potensi longsor untuk 19 kecamatan  
di Kabupaten Semarang menggunakan model Random Forest yang dilatih dari  
data BPS, jenis tanah, kemiringan lereng, curah hujan, dan tutupan lahan.

---

## Arsitektur Deploy (PythonAnywhere Only)
```
[VS Code lokal] → git push → [GitHub: bemomike/ASTA_PORTAL_Website_r27]
                                        ↓
                              [PythonAnywhere: git pull + Reload]
                                        ↓
                     Flask menyajikan SEMUA dari satu URL:
                     https://USERNAME.pythonanywhere.com/
                       ├── /                (index.html)
                       ├── /simulasi.html
                       ├── /hasil1.html
                       ├── /hasil2.html
                       ├── /api/simulate    (POST)
                       ├── /api/info/*      (GET)
                       └── /static/geojson/ (GeoJSON files)
```

---

## Struktur Folder
```
ASTA_PORTAL_Website_r27/
├── backend/
│   ├── app/
│   │   ├── main.py              # Flask app + serve frontend
│   │   ├── routes/
│   │   │   ├── simulate.py      # POST /api/simulate
│   │   │   └── info.py          # GET /api/info/*
│   │   ├── data/
│   │   │   ├── batch/           # simulasi_batch_19kec.geojson (upload manual)
│   │   │   ├── static/          # rf_static_data.py (upload manual)
│   │   │   └── geojson/         # GeoJSON per kecamatan (upload manual)
│   │   └── model/trained/       # *.pkl (upload manual)
│   ├── wsgi.py                  # Konfigurasi WSGI PythonAnywhere
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── simulasi.html
│   ├── hasil1.html
│   ├── hasil2.html
│   ├── panduan.html
│   ├── css/style.css
│   ├── js/
│   │   ├── config.js            # ← URL API_BASE diatur di sini
│   │   ├── api.js
│   │   ├── hasil.js
│   │   ├── map.js
│   │   └── ui.js
│   ├── geojson/
│   │   └── kecamatan_semarang.geojson  # ← WAJIB ada di GitHub
│   └── assets/images/
├── .gitignore
├── README.md
└── verify_deployment.py
```

---

## File yang TIDAK masuk GitHub (upload manual ke PythonAnywhere)
| File | Lokasi di PythonAnywhere |
|------|--------------------------|
| `rf_model.pkl` | `backend/app/model/trained/` |
| `le_tanah.pkl` | `backend/app/model/trained/` |
| `le_veg.pkl` | `backend/app/model/trained/` |
| `rf_static_data.py` | `backend/app/data/static/` |
| `simulasi_batch_19kec.geojson` | `backend/app/data/batch/` |
| `ringkasan_batch_19kec.json` | `backend/app/data/batch/` |
| `*.geojson` (per kecamatan) | `backend/app/data/geojson/` |

---

## Perubahan r27 → r28
- Slider vegetasi dipecah 3 faktor: NF/AF/PV, rentang [0.10–1.50]
- Slider curah hujan diperluas ke [10%–150%] sesuai notebook SEL 1
- Nav bar tidak lagi tertutup peta (fix z-index CSS)
- Deploy tanpa Vercel — Flask menyajikan frontend dan backend dari satu URL PythonAnywhere

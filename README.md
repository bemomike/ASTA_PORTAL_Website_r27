# ASTA PORTAL r24 — Panduan Setup Lengkap

**Simulasi Tanah dan Pohon untuk Prediksi Potensi Tanah Longsor**
Kabupaten Semarang | FSM UKSW | Tugas Akhir 2026

Stack: GitHub → PythonAnywhere (backend) + Vercel (frontend)

---

## Tautan Penting

| Sumber | Tautan |
|--------|--------|
| **Folder Dataset Utama (GDrive)** | https://drive.google.com/drive/folders/1W2UEZ815luDAU_aQ2rVj5-3EZg0ZH2uJ |
| **Notebook GColab Aktif** | https://colab.research.google.com/drive/1igS6gdwB7soCXSnkoSFPxWfUmDHPpsAc |
| **Dataset Administrasi (GADM)** | https://drive.google.com/drive/folders/13UJyhtr8kcSsXvqOTObCMPPifah2toVr |
| **Dataset Curah Hujan BPS** | https://drive.google.com/drive/folders/1mzeiODZJpQO7H8SXHFalQ2QvWpVAX4IL |
| **Dataset Jenis Tanah** | https://drive.google.com/drive/folders/1r6QxGF0o5hFnUEjmF4sJoleparX2I8ar |
| **Dataset Kemiringan Lereng** | https://drive.google.com/drive/folders/1GZelXz-8Pzy25LsXJC1cbWIXukN6uo4Y |
| **Dataset Vegetasi/Pohon** | https://drive.google.com/drive/folders/1jQzhxzpLgg3ZCXz6Dv4vlAIjxnp7eQMM |
| **Dataset Populasi Pohon TCC** | https://drive.google.com/file/d/18DzSir_B-5NKzqfaL9gTX9irs4to2qRQ |
| **Dataset Rekam Bencana BPS** | https://drive.google.com/drive/folders/1Ldhkb_xvYLF8XMEgD-PZd_pjH2FPuw9Z |

---

## LANGKAH A — Persiapkan File Gambar & Logo di Laptop

Letakkan 8 file berikut ke folder frontend/assets/images/ sebelum git push:

2 Logo (pojok kanan atas semua halaman):
  logo_fsm_uksw.png    -> PNG transparan, min 200x200px, < 100KB
  logo_uksw.png        -> PNG transparan, min 200x200px, < 100KB

6 Foto Slideshow Beranda:
  longsor_kab_smg.jpeg
  longsor_kab_smg2.jpeg
  longsor_kab_smg3.jpeg
  longsor_kab_smg4.jpeg
  longsor_kab_smg5.jpeg
  longsor_kab_smg6.jpeg

Ketentuan foto: ekstensi .jpeg (bukan .jpg), min 1920x1080px, < 500KB.
Kompres di https://squoosh.app jika perlu.

---

## LANGKAH B — Jalankan Notebook di Google Colab

1. Buka: https://colab.research.google.com/drive/1igS6gdwB7soCXSnkoSFPxWfUmDHPpsAc
2. Klik Runtime -> Run all (tunggu ~10-20 menit)
3. Unduh dari Google Drive setelah selesai:

   Dari Sel Export-1, 2, 3b, 3c (GeoJSON):
     kabupaten_semarang.geojson
     kecamatan_semarang.geojson
     [KEC].geojson           (19 file, huruf besar)
     veg_[KEC].geojson       (19 file)
     tanah_[KEC].geojson     (19 file)
   -> Kompres semua jadi: geojson_v89.zip

   Dari Sel Export-3, 4, 5, 5b (Model):
     rf_model.pkl
     le_tanah.pkl
     le_veg.pkl
     rf_static_data.py
     simulasi_batch_19kec.geojson
     ringkasan_batch_19kec.json

---

## LANGKAH C — Upload ke GitHub

1. Buka https://github.com -> login -> New repository
   Nama: ASTA_PORTAL_Website_r24 | Public | Create
   ⚠ JANGAN centang "Add a README file" atau opsi apapun di bawahnya

2. Upload via browser GitHub (cara termudah untuk pemula):
   - Di halaman repository yang baru dibuat, klik Add file → Upload files
   - Drag & drop seluruh isi folder ASTA_v11_FINAL (termasuk subfolder) ke area upload
     ⚠ Yang diupload adalah ISI folder ASTA_v11_FINAL, bukan foldernya sendiri
     ⚠ Nama folder di GitHub tidak harus sama dengan nama ZIP — yang penting
        nama repository GitHub sesuai dengan yang ditulis di wsgi.py dan path di Langkah D
   - Pastikan 8 file gambar sudah ada di frontend/assets/images/ sebelum upload
   - Tulis pesan commit: Initial commit ASTA PORTAL r24 v11
   - Klik Commit changes

   Alternatif (jika terbiasa Git di terminal):
   git init
   git add .
   git commit -m "Initial commit ASTA PORTAL r24 v11"
   git branch -M main
   git remote add origin https://github.com/[USERNAME]/ASTA_PORTAL_Website_r24.git
   git push -u origin main

3. Pastikan 8 file gambar (Langkah A) sudah ada sebelum push.

Update berikutnya:
   git add .
   git commit -m "Keterangan perubahan"
   git push

---

## LANGKAH D — Setup PythonAnywhere (Backend)

1. Login https://www.pythonanywhere.com akun mikeomed

2. Tab Files -> hapus: ASTA_PORTAL_Website_r24/ dan geojson_v89.zip lama

3. Upload semua isi folder backend/ ke:
   /home/mikeomed/ASTA_PORTAL_Website_r24/backend/

4. Upload rf_model.pkl, le_tanah.pkl, le_veg.pkl ke:
   /home/mikeomed/ASTA_PORTAL_Website_r24/backend/app/model/trained/
   WAJIB subfolder trained/ -- jika salah path, website error 503

5. Upload rf_static_data.py ke:
   /home/mikeomed/ASTA_PORTAL_Website_r24/backend/app/data/static/

6. Upload simulasi_batch_19kec.geojson dan ringkasan_batch_19kec.json ke:
   /home/mikeomed/ASTA_PORTAL_Website_r24/backend/app/data/batch/

7. Upload geojson_v89.zip ke ~/ lalu buka Tab Consoles -> Bash:
   bash ~/ASTA_PORTAL_Website_r24/upload_geojson.sh
   Tunggu hingga: STATUS: OK

8. Install library (di Bash PythonAnywhere):
   pip install flask flask-cors scikit-learn pandas numpy joblib --user

9. Tab Web -> Add new web app -> Manual configuration -> Python 3.10
   Source code: /home/mikeomed/ASTA_PORTAL_Website_r24/backend
   Working directory: /home/mikeomed/ASTA_PORTAL_Website_r24/backend
   Klik link WSGI configuration file -> hapus isinya -> paste isi file backend/wsgi.py
   Simpan -> Reload

10. Verifikasi (di Bash):
    cd ~/ASTA_PORTAL_Website_r24
    python3.10 verify_deployment.py
    Harus: STATUS: SEMUA OK

11. Verifikasi manual di browser:
    https://mikeomed.pythonanywhere.com/api/health
    https://mikeomed.pythonanywhere.com/api/info/KALIWUNGU
    https://mikeomed.pythonanywhere.com/static/geojson/kecamatan_semarang.geojson

---

## LANGKAH E — Deploy Frontend ke Vercel

1. Buka https://vercel.com -> Log in with GitHub
2. Add New Project -> pilih ASTA_PORTAL_Website_r24 -> Deploy
3. Tunggu 1-2 menit -> URL aktif
4. Cek: slideshow foto, 2 logo, tabel panduan, simulasi, hasil I & II

---

## LANGKAH F — Penyelesaian Error Umum

503 Model belum tersedia  -> Upload 3 PKL ke model/trained/ -> Reload
SEKTOR_DATA kosong        -> Upload rf_static_data.py dari Export-4 -> Reload
404 Kecamatan             -> Pastikan NAME_3 huruf besar di GeoJSON
Foto tidak muncul         -> Cek nama file persis (.jpeg bukan .jpg)
Logo tidak muncul         -> Cek huruf kecil/besar nama file PNG
Peta kosong               -> Jalankan upload_geojson.sh lagi
FAIL N/19 GeoJSON         -> Buka ZIP -> masuk subfolder -> ZIP ulang isi langsung
Slider mm tidak muncul    -> Pastikan rf_static_data.py terisi & Reload
PRED_A = PRED_B           -> Upload simulasi_batch_19kec.geojson dari Export-5 notebook
Vercel tidak update        -> Buka Vercel dashboard -> klik Redeploy

---

## LANGKAH G — Update Model

1. Run All notebook di Colab
2. Unduh ulang: rf_static_data.py, 3 PKL, simulasi_batch_19kec.geojson
3. Upload ke path yang sama di PythonAnywhere (timpa file lama)
4. Klik Reload di tab Web PythonAnywhere

---

## Catatan Teknis

Logika PRED_A vs PRED_B:
  PRED_A = CH_INPUT 100% dari rerata CH tahunan kecamatan terpilih
  PRED_B = CH_INPUT = nilai slider pengguna (0-100%) dari rerata CH kecamatan terpilih
  CH_MAX_KAB = 2057.668421 mm hanya sebagai referensi konteks label slider, bukan pembagi

Storage PythonAnywhere tier gratis = 512 MB:
  Kosongkan folder lama sebelum upload (Langkah D poin 2)
  Cek sisa storage di sudut kanan atas halaman Files

---
Versi: r24_v11 | Notebook: v89_finale_r24 | FSM UKSW 2026

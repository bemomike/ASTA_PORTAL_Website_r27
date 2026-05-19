#!/bin/bash
# upload_geojson.sh — ASTA PORTAL r24
# Dijalankan di Bash PythonAnywhere setelah upload file ZIP GeoJSON ke ~/
#
# Cara pakai:
#   bash ~/ASTA_PORTAL_Website_r24/upload_geojson.sh
#
# Script ini otomatis mencari file ZIP GeoJSON di folder home (~/)
# tanpa perlu mengganti nama file ZIP terlebih dahulu.

TARGET="$HOME/ASTA_PORTAL_Website_r24/backend/app/data/geojson"

echo "=================================================="
echo "ASTA PORTAL r24 — Upload GeoJSON"
echo "=================================================="

# ── Cari file ZIP GeoJSON secara otomatis ──────────────────────────────────
# Cari semua ZIP di folder home, prioritaskan yang namanya mengandung "geojson"
ZIP_FILE=""

# Cari ZIP yang namanya mengandung "geojson" (hasil unduhan Google Drive)
for f in "$HOME"/*geojson*.zip "$HOME"/*GeoJSON*.zip "$HOME"/geojson_v89.zip; do
    if [ -f "$f" ]; then
        ZIP_FILE="$f"
        break
    fi
done

# Jika tidak ditemukan, cari ZIP apapun yang ada di home (kecuali yang di subfolder)
if [ -z "$ZIP_FILE" ]; then
    ZIP_FILE=$(find "$HOME" -maxdepth 1 -name "*.zip" | head -1)
fi

if [ -z "$ZIP_FILE" ]; then
    echo "[FAIL] Tidak ada file ZIP ditemukan di folder home (~/)."
    echo "       Upload file ZIP GeoJSON dari Google Drive ke folder home"
    echo "       melalui tab Files di PythonAnywhere, lalu jalankan script ini lagi."
    echo "       Nama ZIP tidak perlu diubah — script akan menemukan otomatis."
    exit 1
fi

echo "[OK] File ZIP ditemukan: $ZIP_FILE"
echo ""

# ── Ekstrak ke folder sementara ───────────────────────────────────────────
TMP_DIR="$HOME/_geojson_tmp_asta"
rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR"

echo "Mengekstrak ZIP..."
unzip -q "$ZIP_FILE" -d "$TMP_DIR"

# Cari semua .geojson di hasil ekstrak (termasuk jika ada subfolder)
mapfile -t GEOJSON_FILES < <(find "$TMP_DIR" -name "*.geojson" -type f)
COUNT=${#GEOJSON_FILES[@]}

echo "Ditemukan $COUNT file GeoJSON di dalam ZIP."
echo ""

if [ "$COUNT" -lt 10 ]; then
    echo "[FAIL] Kurang dari 10 file GeoJSON ditemukan."
    echo "       Kemungkinan file ada di subfolder di dalam ZIP."
    echo "       Buka ZIP di komputer (7-Zip/WinRAR):"
    echo "       Jika ada subfolder → masuk subfolder → pilih semua file"
    echo "       → klik kanan → Add to archive → simpan sebagai ZIP baru"
    echo "       → upload ulang → jalankan script ini lagi."
    rm -rf "$TMP_DIR"
    exit 1
fi

# ── Salin ke target ───────────────────────────────────────────────────────
mkdir -p "$TARGET"
COPIED=0
for f in "${GEOJSON_FILES[@]}"; do
    cp "$f" "$TARGET/"
    COPIED=$((COPIED + 1))
done

# Hitung per jenis
SEKTOR_COUNT=$(ls "$TARGET"/*.geojson 2>/dev/null | xargs -I{} basename {} | grep -v "^veg_" | grep -v "^tanah_" | grep -v "^kabupaten" | grep -v "^kecamatan" | wc -l)
VEG_COUNT=$(ls "$TARGET"/veg_*.geojson 2>/dev/null | wc -l)
TANAH_COUNT=$(ls "$TARGET"/tanah_*.geojson 2>/dev/null | wc -l)

echo "Hasil salin ke $TARGET:"
echo "  Sektor kecamatan : $SEKTOR_COUNT/19"
echo "  Vegetasi (veg_*) : $VEG_COUNT/19"
echo "  Tanah (tanah_*)  : $TANAH_COUNT/19"
echo "  Total            : $COPIED file"
echo ""

# Bersihkan
rm -rf "$TMP_DIR"

EXPECTED=59  # 19 sektor + 19 veg_ + 19 tanah_ + 2 admin (kabupaten + kecamatan)
if [ "$COPIED" -ge "$EXPECTED" ]; then
    echo "=================================================="
    echo "STATUS: OK — $COPIED file GeoJSON siap."
    echo "Langkah berikutnya: klik Reload di tab Web PythonAnywhere."
    echo "=================================================="
else
    echo "=================================================="
    echo "STATUS: PERLU DICEK — hanya $COPIED dari ~$EXPECTED file."
    echo "Jalankan verify_deployment.py untuk detail lebih lanjut."
    echo "=================================================="
fi

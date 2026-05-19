// ============================================================
//  hasil.js — ASTA PORTAL r26
//  Tabel 8 kolom sesuai PDF p.9-10, diurut tertinggi→terendah,
//  narasi otomatis, disclaimer wajib, timestamp, unduh CSV+PNG
//
//  r25 PERBAIKAN:
//  - _norm(): hapus threshold < 2 yang menyebabkan nilai batch 0–2
//    dikali 100 secara salah.
//  - hasilNarasi(): tambah notice kondisi identik (CH=100, TCC=100)
//
//  r26 PERBAIKAN:
//  - hasilNarasi(): tambah notice "live_inference: false" — ketika
//    rf_static_data.py tidak tersedia, PRED_B diambil dari batch
//    (skenario tetap CH=98.45%, TCC=44.85%), bukan dari slider pengguna.
//    Notice ini muncul di Hasil II dan menjelaskan keterbatasan tersebut.
//  - hasilNarasi(): tambah notice dua slider berlawanan arah — ketika
//    CH turun DAN TCC turun bersamaan, RF menghitung kedua efek sekaligus.
//    Efek CH sering mendominasi efek TCC karena CH berbobot 11.2% di RF
//    vs semua fitur vegetasi hanya 1.92%. Ini bukan anomali melainkan
//    perilaku model yang mencerminkan data historis rekam bencana.
//  - labelDeltaKonteks(): fungsi baru — menjelaskan Δ dengan konteks
//    apakah itu naik/turun signifikan dan mengapa.
// ============================================================

/* ── Kategori ──────────────────────────────────────────────── */
function labelPotensi(pct) {
  if (pct < 20)  return "Sangat Rendah";
  if (pct < 40)  return "Rendah";
  if (pct < 60)  return "Sedang";
  if (pct < 80)  return "Tinggi";
  return "Sangat Tinggi";
}

function labelKemiringan(gc) {
  const M = { 1:"Datar (<8°)", 2:"Landai (8–15°)",
              3:"Curam (15–40°)", 4:"Sangat Curam (>40°)" };
  return M[Math.round(gc)] || "Tidak ada data";
}

/* ── Normalisasi nilai PRED ke 0–100 ──────────────────────── */
// r25 FIX: Kedua jalur (batch dan live inference) sudah mengirim
// nilai dalam skala 0–100 ke frontend. Fungsi ini hanya memastikan
// nilai tidak keluar dari rentang valid [0, 100].
function _norm(v) {
  return Math.min(Math.max(parseFloat(v) || 0, 0), 100);
}

/* ── Ambil list sektor dari response backend ───────────────── */
function _ambilSektor(data) {
  if (data.features) return data.features.map(f => f.properties);
  return data.results || [];
}

/* ── Render tabel 8 kolom (sesuai PDF p.9) ─────────────────── */
function hasilRenderTabel(containerId, data, predKey, chKey) {
  const el = document.getElementById(containerId);
  if (!el) return;

  const sektor = _ambilSektor(data);
  if (!sektor.length) {
    el.innerHTML = "<p style='color:#888;font-style:italic'>Tidak ada data sektor.</p>";
    return;
  }

  const terurut = sektor.slice().sort(
    (a, b) => _norm(b[predKey] || 0) - _norm(a[predKey] || 0)
  );

  const baris = terurut.map(s => {
    const pct    = _norm(s[predKey] || 0).toFixed(2);
    const chMm   = (s[chKey] || s["CH_AKTIF"] || s["CH_SKENARIO_A"] || s["CH_SKENARIO"] || 0).toFixed(1);
    const luas   = s.LUAS_HA != null ? s.LUAS_HA
                 : s.PROPORSI_LUAS   != null ? s.PROPORSI_LUAS * 100
                 : 0;
    const luasStr = typeof luas === "number" ? luas.toFixed(1) : "—";
    return `<tr>
      <td>${s.sektor_id || s.ID_SEKTOR || "—"}</td>
      <td>${s.LABEL_VEG  || "—"}</td>
      <td>${s.MACAM_TANA || "—"}</td>
      <td>${labelKemiringan(s.KEMIRINGAN || s.GRIDCODE_LERENG_W || 0)}</td>
      <td>${luasStr}</td>
      <td>${chMm}</td>
      <td>${pct}</td>
      <td>${labelPotensi(parseFloat(pct))}</td>
    </tr>`;
  }).join("");

  el.innerHTML = `
    <div class="tabel-wrap">
      <table id="tabel-hasil-data">
        <thead>
          <tr>
            <th>ID Sektor</th>
            <th>Jenis Vegetasi</th>
            <th>Jenis Tanah</th>
            <th>Kemiringan Lereng</th>
            <th>Luas (Ha)</th>
            <th>CH Skenario (mm)</th>
            <th>Potensi (%)</th>
            <th>Label</th>
          </tr>
        </thead>
        <tbody>${baris}</tbody>
      </table>
    </div>`;
}

/* ── Konteks delta untuk narasi ─────────────────────────────── */
// Menjelaskan arah Δ dengan mempertimbangkan kondisi slider
function labelDeltaKonteks(delta, chPct, tccPct) {
  const chTurun  = chPct  < 99.0;
  const tccTurun = tccPct < 99.0;
  const chNaik   = chPct  > 101.0;

  if (!chTurun && !tccTurun && !chNaik) return ""; // kondisi aktual, tidak perlu konteks

  if (delta > 3) {
    if (tccTurun && !chTurun) return " — peningkatan ini konsisten dengan meningkatnya deforestasi.";
    if (chNaik   && !tccTurun) return " — peningkatan ini konsisten dengan meningkatnya curah hujan.";
    if (chTurun  && tccTurun) return " — meski curah hujan lebih rendah, deforestasi mendominasi peningkatan risiko di kecamatan ini.";
    return " — potensi meningkat dari kondisi aktual.";
  }
  if (delta < -3) {
    if (chTurun  && !tccTurun) return " — penurunan ini konsisten dengan berkurangnya curah hujan.";
    if (tccTurun && !chTurun)  return " — meski ada deforestasi, saturasi risiko di kecamatan ini membatasi peningkatan lebih lanjut.";
    if (chTurun  && tccTurun)  return " — efek penurunan curah hujan mendominasi efek deforestasi di kecamatan ini (RF: CH berbobot 11.2%, vegetasi 1.92%).";
    return " — potensi menurun dari kondisi aktual.";
  }
  return " — perubahan kecil dari kondisi aktual.";
}

/* ── Narasi otomatis ────────────────────────────────────────── */
function hasilNarasi(containerId, kec, data, predKey, jenisData) {
  const el = document.getElementById(containerId);
  if (!el) return;

  const sektor = _ambilSektor(data);
  if (!sektor.length) return;

  const nilaiArr = sektor.map(s => _norm(s[predKey] || 0));
  const rerata   = (nilaiArr.reduce((a, b) => a + b, 0) / nilaiArr.length).toFixed(2);
  const iMax     = nilaiArr.indexOf(Math.max(...nilaiArr));
  const sMax     = sektor[iMax];
  const nilMax   = nilaiArr[iMax].toFixed(2);
  const katMax   = labelPotensi(parseFloat(nilMax));

  const chPct  = parseFloat(sessionStorage.getItem("asta_ch_pct")  || "100");
  const tccPct = parseFloat(sessionStorage.getItem("asta_tcc_pct") || "100");
  const liveInf = data.live_inference !== false; // true jika tidak ada kunci, atau kunci true

  // Hitung Δ terhadap PRED_A (hanya relevan untuk Hasil II)
  let deltaRerata = null;
  if (predKey === "PRED_B") {
    const nilaiA = sektor.map(s => _norm(s["PRED_A"] || 0));
    const rerataA = nilaiA.reduce((a,b) => a+b, 0) / nilaiA.length;
    deltaRerata = parseFloat(rerata) - rerataA;
  }

  // Notices
  let notices = "";

  // Notice 1: kondisi identik (slider di 100%/100%)
  if (predKey === "PRED_B" && chPct >= 99.9 && tccPct >= 99.9) {
    notices += `<div class="disclaimer" style="border-left-color:#e67e22;background:#fff8f0;margin-top:0.5rem">
      ⚠️ <strong>Kondisi identik dengan Hasil I (CH=100%, Pohon=100%).</strong>
      Nilai Δ yang muncul adalah artefak normalisasi komputasi, bukan perubahan nyata.
      Ubah slider CH atau Populasi Pohon untuk melihat skenario yang bermakna.
    </div>`;
  }

  // Notice 2: PRED_B dari batch (rf_static_data.py tidak tersedia di server)
  if (predKey === "PRED_B" && !liveInf) {
    notices += `<div class="disclaimer" style="border-left-color:#c0392b;background:#fff5f5;margin-top:0.5rem">
      ⚠️ <strong>Nilai Hasil II diambil dari data pre-computed (CH≈98%, Pohon≈45%).</strong>
      File rf_static_data.py tidak tersedia di server, sehingga slider Anda tidak berdampak
      pada nilai ini. Untuk mengaktifkan simulasi interaktif, upload rf_static_data.py
      (dari Sel Export-4 notebook) ke <code>backend/app/data/static/</code> lalu Reload.
    </div>`;
  }

  // Notice 3: dua slider berlawanan arah
  const chTurun  = chPct  < 99.0;
  const tccTurun = tccPct < 99.0;
  if (predKey === "PRED_B" && chTurun && tccTurun && deltaRerata !== null && deltaRerata < -2) {
    notices += `<div class="disclaimer" style="border-left-color:#8e44ad;background:#fdf5ff;margin-top:0.5rem">
      ℹ️ <strong>Efek CH mendominasi efek deforestasi.</strong>
      Dalam skenario ini, curah hujan turun ${(100-chPct).toFixed(0)}% DAN populasi pohon
      turun ${(100-tccPct).toFixed(0)}% sekaligus. Penurunan curah hujan mendominasi
      karena CH berbobot 11.2% di model RF, sedangkan semua fitur vegetasi gabungan hanya 1.92%.
      Untuk melihat murni efek deforestasi, gunakan CH=100% dan turunkan slider Pohon saja.
    </div>`;
  }

  const konteks = deltaRerata !== null
    ? labelDeltaKonteks(deltaRerata, chPct, tccPct)
    : "";
  const deltaStr = deltaRerata !== null
    ? ` (Δ <strong>${deltaRerata > 0 ? "+" : ""}${deltaRerata.toFixed(2)}%</strong>${konteks})`
    : "";

  el.innerHTML = `
    <div class="narasi-kotak">
      <p>
        Berdasarkan hasil simulasi menggunakan <strong>${jenisData}</strong>,
        Kecamatan <strong>${kec.charAt(0) + kec.slice(1).toLowerCase()}</strong>
        memiliki rerata potensi longsor sebesar <strong>${rerata}%</strong>${deltaStr}
        dengan sektor di kawasan vegetasi <em>${sMax.LABEL_VEG || "—"}</em>
        dan tanah <em>${sMax.MACAM_TANA || "—"}</em>
        memiliki potensi longsor terbesar yakni
        <strong>${nilMax}%</strong> (<strong>${katMax}</strong>).
      </p>
      ${notices}
      <div class="disclaimer">
        ⚠️ Angka potensi longsor di atas adalah <strong>indeks komparatif
        dalam skala Kabupaten Semarang (0–100%)</strong>, bukan probabilitas
        absolut kejadian longsor. Model divalidasi untuk 19 kecamatan
        Kabupaten Semarang berdasarkan data historis BPS.
      </div>
    </div>`;
}

/* ── Timestamp ──────────────────────────────────────────────── */
function hasilTimestamp(elId) {
  const el = document.getElementById(elId);
  if (!el) return;
  const now = new Date();
  el.textContent =
    `Hasil diperoleh: ${now.toLocaleDateString("id-ID", {
      day:"2-digit", month:"long", year:"numeric"
    })} pukul ${now.toLocaleTimeString("id-ID", {
      hour:"2-digit", minute:"2-digit"
    })} WIB`;
}

/* ── Unduh CSV ───────────────────────────────────────────────── */
function hasilUnduhCSV(kec, predKey) {
  const tabel = document.getElementById("tabel-hasil-data");
  if (!tabel) return alert("Tabel belum tersedia. Jalankan simulasi terlebih dahulu.");
  const baris = Array.from(tabel.querySelectorAll("tr"));
  const csv   = baris.map(tr =>
    Array.from(tr.querySelectorAll("th, td"))
      .map(td => `"${td.textContent.trim()}"`)
      .join(",")
  ).join("\n");
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
  const link = document.createElement("a");
  link.href     = URL.createObjectURL(blob);
  link.download = `ASTA_PORTAL_${kec}_${predKey}.csv`;
  link.click();
}

/* ── Unduh PNG ───────────────────────────────────────────────── */
function hasilUnduhPeta(kec, predKey) {
  if (typeof html2canvas !== "undefined") {
    html2canvas(document.getElementById("peta")).then(canvas => {
      const link    = document.createElement("a");
      link.download = `ASTA_PORTAL_${kec}_${predKey}.png`;
      link.href     = canvas.toDataURL("image/png");
      link.click();
    });
  } else {
    alert(
      "Untuk menyimpan peta sebagai gambar:\n" +
      "1. Klik kanan pada peta\n" +
      "2. Pilih 'Simpan gambar sebagai...'\n" +
      "   atau gunakan tombol Print Screen / Snipping Tool"
    );
  }
}

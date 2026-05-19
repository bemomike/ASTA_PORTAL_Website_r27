// ============================================================
//  ui.js — ASTA PORTAL r25
//
//  r25 PERBAIKAN:
//  - uiTampilPanelInfo(): panel-lereng fallback dikoreksi.
//    Versi lama menampilkan "Rerata elevasi: X m dpl" di panel
//    berlabel "Kemiringan Lereng" — dua konsep berbeda yang
//    menyesatkan pengguna. Fallback baru menampilkan "Tidak ada
//    data kemiringan" secara eksplisit tanpa substitusi nilai
//    topografi yang berbeda konsep.
// ============================================================


/* ── Dropdown 19 kecamatan dari GeoJSON ─────────────────── */
async function uiMuatDropdown(selectId, geojsonPath, onChange) {
  const data = await fetch(geojsonPath).then(r => r.json()).catch(() => null);
  const sel  = document.getElementById(selectId);
  if (!data) { sel.innerHTML = "<option value=''>Gagal memuat daftar</option>"; return; }

  const fitur = data.features.slice().sort(
    (a, b) => (a.properties.ID_Dummy || 0) - (b.properties.ID_Dummy || 0)
  );
  sel.innerHTML = `<option value=''>Pilih Kecamatan</option>`;
  fitur.forEach(ft => {
    const nama = ft.properties.NAME_3 || "";
    const opt  = document.createElement("option");
    opt.value       = nama;
    opt.textContent = `${ft.properties.ID_Dummy}. ${nama}`;
    sel.appendChild(opt);
  });
  sel.addEventListener("change", () => { if (sel.value && onChange) onChange(sel.value); });
}

/* ── Sinkronkan dropdown dengan klik peta ─────────────────── */
function uiSinkronDropdown(selectId, kec) {
  const sel = document.getElementById(selectId);
  if (sel && sel.value !== kec) sel.value = kec;
}

/* ── Slider realtime ──────────────────────────────────────── */
function uiInitSlider(sliderId, displayId) {
  const s = document.getElementById(sliderId);
  const d = document.getElementById(displayId);
  if (!s || !d) return;
  d.textContent = s.value + "%";
  s.addEventListener("input", () => { d.textContent = s.value + "%"; });
}

/* ── Panel info kecamatan ─────────────────────────────────── */
function uiTampilPanelInfo(data) {
  // Pohon dan tanah: tampilkan semua jenis, dominan dicetak tebal di atas
  const vegList   = data?.veg_list   || [];
  const tanahList = data?.tanah_list || [];
  const vegDom    = data?.veg_dominan   || null;
  const tanahDom  = data?.tanah_dominan || null;

  _setPanelList("panel-pohon", vegList,   vegDom);
  _setPanelList("panel-tanah", tanahList, tanahDom);

  // Lereng: hanya data kemiringan (bukan elevasi)
  const lerengTeks = data?.lereng_label || null;
  _setPanelTeks("panel-lereng", lerengTeks);

  _setPanelTeks("panel-ch", data?.ch_mean != null
    ? `${data.ch_mean.toFixed(1)} mm/tahun` : null);
}

/* Render list jenis di panel — dominan cetak tebal, sisanya abu kecil */
function _setPanelList(id, list, dominan) {
  const el = document.getElementById(id);
  if (!el) return;
  if (!list || !list.length) {
    el.textContent = "Tidak ada data";
    el.className   = "panel-isi kosong";
    return;
  }
  el.className = "panel-isi scrollable";
  el.innerHTML = list.map(item => {
    const isDom = item === dominan;
    return `<div style="${isDom
      ? "font-weight:700;color:var(--hijau-panel)"
      : "color:var(--teks-redup);font-size:0.80rem"}">
      ${isDom ? "● " : "◦ "}${item}
    </div>`;
  }).join("");
}

function uiResetPanelInfo() {
  ["panel-pohon","panel-tanah","panel-lereng","panel-ch"].forEach(id =>
    _setPanelTeks(id, null)
  );
}

function _setPanelTeks(id, teks) {
  const el = document.getElementById(id);
  if (!el) return;
  if (teks) {
    el.textContent = teks;
    el.className   = "panel-isi";
  } else {
    el.textContent = "Tidak ada data";
    el.className   = "panel-isi kosong";
  }
}

/* ── Aktifkan/nonaktifkan tombol simulasi ──────────────────── */
function uiSetSimulasiSiap(btnId, siap) {
  const btn = document.getElementById(btnId);
  if (!btn) return;
  btn.disabled = !siap;
  if (!siap) btn.setAttribute("data-tooltip", "Pilih kecamatan terlebih dahulu");
  else       btn.removeAttribute("data-tooltip");
}

/* ── Spinner ───────────────────────────────────────────────── */
function uiSpinner(tampil) {
  document.querySelectorAll(".spinner").forEach(el =>
    el.style.display = tampil ? "block" : "none"
  );
}

/* ── Pesan error ───────────────────────────────────────────── */
function uiTampilError(containerId, pesan) {
  const el = document.getElementById(containerId);
  if (el) el.innerHTML = `<div class="pesan-error">⚠️ ${pesan}</div>`;
}
function uiBersihkanError(containerId) {
  const el = document.getElementById(containerId);
  if (el) el.innerHTML = "";
}

/* ── Slideshow Beranda (6 foto, ganti tiap 4.5 detik) ─────── */
function uiInitSlideshow(containerId, namaFile) {
  const kontainer = document.getElementById(containerId);
  if (!kontainer || !namaFile.length) return;

  namaFile.forEach((nama, i) => {
    const div = document.createElement("div");
    div.className = "slideshow-slide" + (i === 0 ? " aktif" : "");
    div.style.backgroundImage = `url('assets/images/${nama}')`;
    kontainer.appendChild(div);
  });

  let indeks = 0;
  setInterval(() => {
    const slides = kontainer.querySelectorAll(".slideshow-slide");
    slides[indeks].classList.remove("aktif");
    indeks = (indeks + 1) % slides.length;
    slides[indeks].classList.add("aktif");
  }, 4500);
}

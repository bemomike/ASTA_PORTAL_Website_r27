// ============================================================
//  map.js — ASTA PORTAL r26
//  Leaflet + GeoJSON sesuai Bagian 2.11 Anatomi Website
//
//  r25 PERBAIKAN:
//  - _normPred(): hapus threshold < 2 yang menyebabkan nilai batch
//    0–2 dikali 100 secara salah. Kedua jalur sudah mengirim 0–100.
//
//  r26 PERBAIKAN:
//  - petaMuatKecamatan() sekarang menerima string (URL) ATAU objek
//    GeoJSON langsung. Versi lama hanya menerima URL sehingga
//    simulasi.html harus fetch dua kali (sekali untuk dropdown,
//    sekali untuk peta). Sekarang cukup fetch sekali, objek
//    dipakai ulang oleh keduanya. Ini juga memungkinkan peta
//    tetap berfungsi meski GeoJSON diambil dari sumber fallback.
// ============================================================

const WARNA = {
  abu:      "#C0C0C0",
  hover:    "#A8D08D",
  terpilih: "#3A5F0B",
};

// Warna vegetasi — identik dengan _WARNA_VEG_KOMPOSIT notebook
const WARNA_VEG = {
  "Albasia":"#78c679","Albasia/Bambu/Kelapa":"#c7e9b4","Albasiah":"#41ab5d",
  "Bambu":"#238b45","Jati":"#d4541a","Karet":"#5a7a34","Karet/Jati":"#b5651d",
  "Kelapa":"#f0c040","Kopi":"#1a6b1a","Kopi/Karet":"#3d8b37","Kakao":"#6b3a2a",
  "Cengkeh":"#8b4513","Teh":"#4caf50","Mahoni":"#a0522d",
  "Mahoni/Jati/Karet/Teh":"#c68642","Perkebunan/Kebun":"#d4a84b",
  "Hutan Rimba":"#2d6a2d","Hutan Sekunder":"#52b352",
  "Vegetasi Non Budidaya Lainnya":"#6aab6a","Tanaman Campur Lainnya":"#a8d58a",
  "Semak Belukar":"#9c7a3c","Tanpa Vegetasi":"#d9d9d9",
  "Tidak Teridentifikasi":"#d3d3d3",
};

// Warna tanah — matplotlib Set3 sesuai notebook
const WARNA_TANAH = {
  "Aluvial Hidromorf":"#8dd3c7","Aluvial Kelabu":"#ffffb3",
  "Aluvial Kelabu dan Aluvia Coklat Kekelabuan":"#bebada",
  "Andosol Coklat":"#fb8072","Andosol Coklat dan Latosol Coklat Kemerahan":"#80b1d3",
  "Asosiasi Mediteran Coklat Litosol":"#fdb462",
  "Kompleks Andosol Kelabu Tua dan Litosol":"#b3de69",
  "Kompleks Grumusol Kelabu dan Litosol":"#fccde5",
  "Kompleks Regosol Kelabu dan Grumusol Kelabu Tua":"#d9d9d9",
  "Latosol Coklat":"#bc80bd","Mediteran Merah Tua dan Regosol":"#ccebc5",
  "Regosol Kelabu":"#ffed6f",
};

let _peta         = null;
let _layerKec     = null;
let _layerOverlay = null;
let _layerMask    = null;
let _layerHasil   = null;
let _kecTerpilih  = null;
let _onKlikKec    = null;
let _kecGeoJSON   = null;

/* ── Normalisasi PRED ke 0–100 ────────────────────────────── */
// r25 FIX: Batch dan live inference sudah mengirim skala 0–100.
// Threshold lama (v < 2 → v*100) menyebabkan nilai kecil dikali 100.
function _normPred(v) {
  return Math.min(Math.max(parseFloat(v) || 0, 0), 100);
}

/* ── Skala warna hijau→kuning→merah (0–100) ──────────────── */
function _predWarna(val) {
  const v = Math.min(Math.max(val, 0), 100) / 100;
  const r = Math.round(v < 0.5 ? 2 * v * 210 : 210);
  const g = Math.round(v < 0.5 ? 180 : 180 * (1 - (v - 0.5) * 2));
  return `rgb(${r},${g},20)`;
}

/* ── Init peta ──────────────────────────────────────────────── */
function petaInit(divId) {
  _peta = L.map(divId).setView([-7.22, 110.45], 10);
  L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
    attribution: "© OpenStreetMap © CARTO",
    subdomains: "abcd", maxZoom: 18,
  }).addTo(_peta);
  return _peta;
}

/* ── Muat 19 kecamatan ──────────────────────────────────────── */
// r26: Menerima URL (string) ATAU objek GeoJSON langsung.
// Jika URL → fetch dulu, lalu render. Jika objek → render langsung.
async function petaMuatKecamatan(sumber, onKlik) {
  _onKlikKec = onKlik;
  // Tentukan apakah sumber adalah URL atau objek GeoJSON
  let data;
  if (typeof sumber === "string") {
    data = await fetch(sumber).then(r => r.json());
  } else {
    // Sudah berupa objek GeoJSON — tidak perlu fetch ulang
    data = sumber;
  }
  _kecGeoJSON = data;
  if (_layerKec) _peta.removeLayer(_layerKec);

  _layerKec = L.geoJSON(data, {
    style: _gayaDefault,
    onEachFeature: (feature, layer) => {
      layer.on({
        mouseover: (e) => {
          if (feature.properties.NAME_3 !== _kecTerpilih)
            e.target.setStyle({ fillColor: WARNA.hover, fillOpacity: 0.65 });
        },
        mouseout: (e) => {
          if (feature.properties.NAME_3 !== _kecTerpilih)
            _layerKec.resetStyle(e.target);
        },
        click: (e) => {
          _kecTerpilih = feature.properties.NAME_3;
          _layerKec.setStyle(_gayaDefault);
          e.target.setStyle({
            fillColor: WARNA.terpilih, fillOpacity: 0.72,
            color: "#1a2f05", weight: 2.5,
          });
          if (_onKlikKec) _onKlikKec(_kecTerpilih);
        },
      });
    },
  }).addTo(_peta);
  _peta.fitBounds(_layerKec.getBounds());
}

function _gayaDefault() {
  return { fillColor: WARNA.abu, fillOpacity: 0.5, color: "#555", weight: 1 };
}

/* ── Sorot kecamatan dari luar (dropdown) ───────────────────── */
function petaSorotKecamatan(nama) {
  if (!_layerKec) return;
  _kecTerpilih = nama;
  _layerKec.eachLayer(layer => {
    const nm = layer.feature && layer.feature.properties.NAME_3;
    if (nm === nama) {
      layer.setStyle({ fillColor: WARNA.terpilih, fillOpacity: 0.72,
                       color: "#1a2f05", weight: 2.5 });
      if (layer.getBounds) _peta.fitBounds(layer.getBounds(), { maxZoom: 13 });
    } else {
      _layerKec.resetStyle(layer);
    }
  });
}

/* ── Masking: tutup kecamatan lain saat overlay aktif ─────────── */
function _tampilMask(kecNama) {
  if (_layerMask) { _peta.removeLayer(_layerMask); _layerMask = null; }
  if (!_kecGeoJSON || !kecNama) return;
  const luar = { type: "FeatureCollection",
    features: _kecGeoJSON.features.filter(f => f.properties.NAME_3 !== kecNama) };
  _layerMask = L.geoJSON(luar, {
    style: { fillColor: "#ffffff", fillOpacity: 0.60, color: "#aaa", weight: 0.5 },
    interactive: false,
  }).addTo(_peta);
}
function _hapusMask() {
  if (_layerMask) { _peta.removeLayer(_layerMask); _layerMask = null; }
}

/* ── Toggle overlay veg/tanah dengan warna per jenis ─────────── */
async function petaToggleOverlay(geojsonPath, mode) {
  if (_layerOverlay) { _peta.removeLayer(_layerOverlay); _layerOverlay = null; }
  _hapusMask();
  if (!geojsonPath) return null;
  const data = await fetch(geojsonPath).then(r => r.json()).catch(() => null);
  if (!data) return null;

  const prop      = mode === "veg" ? "LABEL_VEG" : "MACAM_TANA";
  const paletDict = mode === "veg" ? WARNA_VEG   : WARNA_TANAH;
  const defColor  = "#cccccc";
  const jenisSet  = [...new Set(data.features.map(f => f.properties[prop]||"").filter(Boolean))].sort();
  const warnaMap  = {};
  jenisSet.forEach(j => { warnaMap[j] = paletDict[j] || defColor; });

  _layerOverlay = L.geoJSON(data, {
    style: (f) => ({
      fillColor:   warnaMap[f.properties[prop]||""] || defColor,
      fillOpacity: 0.72, color: "#333", weight: 0.8,
    }),
    onEachFeature: (feature, layer) => {
      const label = feature.properties[prop] || "";
      if (label) layer.bindTooltip(label, { sticky: true, direction: "top" });
    },
  }).addTo(_peta);

  if (_kecTerpilih) _tampilMask(_kecTerpilih);
  return warnaMap;
}

/* ── Render legenda warna jenis di div ──────────────────────── */
function petaLegendaOverlay(divId, warnaMap, judul) {
  const el = document.getElementById(divId);
  if (!el || !warnaMap) return;
  const items = Object.entries(warnaMap).map(([j, w]) =>
    `<span style="display:inline-flex;align-items:center;gap:3px;margin:2px 5px 2px 0">
       <span style="width:12px;height:12px;background:${w};border-radius:2px;
         border:1px solid #aaa;flex-shrink:0"></span>
       <span style="font-size:0.74rem">${j}</span>
     </span>`
  ).join("");
  el.innerHTML = `<strong style="font-size:0.76rem;color:var(--hijau-tua)">${judul}:</strong>
    <div style="display:flex;flex-wrap:wrap;margin-top:3px">${items}</div>`;
}

/* ── Render peta hasil ──────────────────────────────────────── */
function petaRenderHasil(geojsonData, predKey) {
  if (_layerHasil) _peta.removeLayer(_layerHasil);
  _layerHasil = L.geoJSON(geojsonData, {
    style: (f) => {
      const rawVal = f.properties[predKey] || 0;
      const val    = _normPred(rawVal);
      return {
        fillColor:   _predWarna(val),
        fillOpacity: 0.78, color: "#333", weight: 0.7,
      };
    },
    onEachFeature: (feature, layer) => {
      const p      = feature.properties;
      const rawVal = p[predKey] || 0;
      const val    = _normPred(rawVal).toFixed(2);
      const sid = p.ID_SEKTOR || p.sektor_id || "—";
      layer.bindTooltip(
        `<strong>${sid}</strong><br>` +
        `Vegetasi: ${p.LABEL_VEG  || "—"}<br>` +
        `Tanah: ${p.MACAM_TANA || "—"}<br>` +
        `Potensi: <strong>${val}%</strong>`,
        { sticky: true }
      );
    },
  }).addTo(_peta);
  _peta.fitBounds(_layerHasil.getBounds());
}

/* ── Legenda ────────────────────────────────────────────────── */
function petaLegenda(divId) {
  const el = document.getElementById(divId);
  if (!el) return;
  const stops = [
    { v: 0,   label: "Sgt Rendah (<20%)" },
    { v: 20,  label: "Rendah (20–40%)" },
    { v: 40,  label: "Sedang (40–60%)" },
    { v: 60,  label: "Tinggi (60–80%)" },
    { v: 80,  label: "Sgt Tinggi (≥80%)" },
  ];
  el.innerHTML = stops.map(s =>
    `<span style="display:inline-flex;align-items:center;gap:3px;margin-right:6px">
       <span style="width:18px;height:12px;background:${_predWarna(s.v)};
         border-radius:2px;display:inline-block;border:1px solid #bbb"></span>
       <span>${s.label}</span>
     </span>`
  ).join("&nbsp;");
}

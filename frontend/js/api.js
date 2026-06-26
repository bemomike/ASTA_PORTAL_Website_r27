// ============================================================
//  api.js — ASTA PORTAL r28
//  Semua request ke backend PythonAnywhere.
//  BASE_URL dibaca dari config.js (wajib dimuat lebih dulu di HTML).
//
//  r28 PERUBAHAN:
//  - apiSimulate(): tcc_pct dihapus, diganti veg_nf, veg_af, veg_pv
//    Rentang masing-masing: [0.10, 1.50] sesuai notebook SEL 1
// ============================================================

function _base() {
  return (typeof ASTA_CONFIG !== "undefined" && ASTA_CONFIG.API_BASE)
    ? ASTA_CONFIG.API_BASE
    : "https://mikeomed.pythonanywhere.com";
}

/**
 * GET /api/info/{kec}
 * Mengembalikan ringkasan kecamatan untuk panel info Simulasi.
 */
async function apiGetInfo(kec) {
  const res = await fetch(`${_base()}/api/info/${encodeURIComponent(kec)}`);
  if (!res.ok) throw new Error(`Info gagal: ${res.status}`);
  return res.json();
}

/**
 * POST /api/simulate
 * Body: { kec, ch_pct, veg_nf, veg_af, veg_pv }
 *
 * @param {string} kec      - Nama kecamatan (huruf besar)
 * @param {number} ch_pct   - Intensitas curah hujan [10–150] %
 *                            (10% = faktor 0.10, 100% = aktual, 150% = faktor 1.50)
 * @param {number} veg_nf   - Faktor tutupan kanopi Hutan Alam (NF) [0.10–1.50]
 * @param {number} veg_af   - Faktor tutupan kanopi Agroforestri (AF) [0.10–1.50]
 * @param {number} veg_pv   - Faktor tutupan kanopi Vegetasi Produksi (PV) [0.10–1.50]
 * @returns {Promise<Object>} Response JSON dari backend
 */
async function apiSimulate(kec, ch_pct, veg_nf, veg_af, veg_pv) {
  const res = await fetch(`${_base()}/api/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kec, ch_pct, veg_nf, veg_af, veg_pv }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Simulasi gagal: ${res.status}`);
  }
  return res.json();
}

// ============================================================
//  api.js — ASTA PORTAL r24
//  Semua request ke backend PythonAnywhere.
//  BASE_URL dibaca dari config.js (wajib dimuat lebih dulu di HTML).
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
 * Body: { kec, ch_pct, tcc_pct }
 * Response: { kec, source, features/results }
 */
async function apiSimulate(kec, ch_pct, tcc_pct) {
  const res = await fetch(`${_base()}/api/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kec, ch_pct, tcc_pct }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Simulasi gagal: ${res.status}`);
  }
  return res.json();
}

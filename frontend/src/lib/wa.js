export const WA_STATUS = {
  mengirim: { label: "Sedang dikirim…", cls: "border-slate-300 bg-slate-100 text-slate-800" },
  antre: { label: "Diterima Fonnte · masuk antrean", cls: "border-emerald-300 bg-emerald-50 text-emerald-900" },
  ditolak: { label: "Ditolak Fonnte", cls: "border-red-300 bg-red-50 text-red-900" },
  gagal: { label: "Gagal terhubung · belum terkirim", cls: "border-red-300 bg-red-50 text-red-900" },
  tidak_pasti: { label: "Tidak pasti · cek Fonnte sebelum kirim ulang", cls: "border-amber-300 bg-amber-50 text-amber-900" },
};

export const waStatus = (s) => WA_STATUS[s] || { label: s || "-", cls: "border-slate-300 bg-slate-100 text-slate-800" };

// Sama dengan normalize_wa di backend: 08… / 62… / +62… → 62…; null jika tidak valid.
export function normalizeWa(raw) {
  let s = String(raw || "").replace(/[\s\-().]/g, "");
  if (s.startsWith("+")) s = s.slice(1);
  if (!/^\d+$/.test(s)) return null;
  if (s.startsWith("0")) s = "62" + s.slice(1);
  return /^628\d{7,11}$/.test(s) ? s : null;
}

export const hasActiveSend = (logs) => (logs || []).some((l) => ["mengirim", "antre", "tidak_pasti"].includes(l.status));

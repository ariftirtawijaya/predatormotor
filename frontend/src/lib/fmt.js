const TZ = "Asia/Jakarta";

export const rp = (n) => "Rp" + Math.round(Number(n || 0)).toLocaleString("id-ID");

export const fmtDate = (iso) => {
  if (!iso) return "-";
  const d = iso.length === 10 ? new Date(iso + "T00:00:00+07:00") : new Date(iso);
  return d.toLocaleDateString("id-ID", { timeZone: TZ, day: "numeric", month: "short", year: "numeric" });
};

export const fmtDateTime = (iso) => {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("id-ID", { timeZone: TZ, day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) + " WIB";
};

export const today = () => new Date().toLocaleDateString("en-CA", { timeZone: TZ });

export const monthStart = () => today().slice(0, 8) + "01";

export const waLink = (phone, text) => {
  let p = String(phone || "").replace(/\D/g, "");
  if (p.startsWith("0")) p = "62" + p.slice(1);
  return `https://wa.me/${p}${text ? `?text=${encodeURIComponent(text)}` : ""}`;
};

export const KIND_LABEL = { job: "Pekerjaan", sale: "Penjualan", order: "Pesanan WA" };
export const KIND_PATH = { job: "pekerjaan", sale: "penjualan", order: "pesanan" };

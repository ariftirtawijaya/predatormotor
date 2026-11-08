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

export function notaText(doc, kind, shopName) {
  const lines = (doc.lines || []).filter((l) => !l.removed);
  const rows = lines.map((l) => `- ${l.name}${l.qty > 1 ? ` x${l.qty}` : ""}: ${rp(l.subtotal)}`).join("\n");
  const link = doc.public_token ? `\nLihat nota: ${window.location.origin}/nota/${doc.public_token}` : "";
  const remaining = Math.max((doc.total || 0) - (doc.paid || 0), 0);
  return `${shopName || "Predator Autolight"}\nNota ${doc.no} (${KIND_LABEL[kind]})\n${rows}` +
    (doc.discount_amount ? `\nDiskon: -${rp(doc.discount_amount)}` : "") +
    (doc.shipping_cost ? `\nOngkir: ${rp(doc.shipping_cost)}` : "") +
    `\nTotal: ${rp(doc.total)}\nDibayar: ${rp(doc.paid)}` + (remaining ? `\nSisa: ${rp(remaining)}` : "") + link;
}

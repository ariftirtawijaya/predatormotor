import { rp, fmtDateTime, fmtDate, KIND_LABEL } from "@/lib/fmt";

const Row = ({ l, r, b }) => <div className={`flex justify-between gap-2 ${b ? "font-bold" : ""}`}><span>{l}</span><span className="text-right">{r}</span></div>;

export default function Receipt({ d, identity = {}, contact = {}, size = "80" }) {
  const a4 = size === "a4";
  const lines = d.lines || [];
  return (
    <div className={`print-area mx-auto bg-white p-4 text-black ${a4 ? "receipt-a4" : "receipt-80"}`} style={{ fontFamily: "'IBM Plex Mono', monospace" }} data-testid="receipt">
      <div className={a4 ? "flex items-start justify-between border-b-2 border-black pb-3" : "border-b border-dashed border-black pb-2 text-center"}>
        <div>
          <p className={`font-bold ${a4 ? "text-xl" : "text-sm"}`}>{identity.name || "Predator Autolight"}</p>
          {contact.address && <p>{contact.address}</p>}
          {contact.whatsapp && <p>WA: {contact.whatsapp}</p>}
        </div>
        <div className={a4 ? "text-right" : "mt-2"}>
          <p className="font-bold">NOTA {KIND_LABEL[d.kind]?.toUpperCase()}</p>
          <p data-testid="receipt-no">{d.no}</p>
          <p>{fmtDateTime(d.date)}</p>
        </div>
      </div>
      <div className="border-b border-dashed border-black py-2">
        {d.customer_name && <Row l="Pelanggan" r={d.customer_name} />}
        {d.plate && <Row l="Plat" r={d.plate} />}
        {d.status && <Row l="Status" r={d.status} />}
      </div>
      {a4 ? (
        <table className="my-3 w-full border-collapse text-left">
          <thead><tr className="border-b border-black"><th className="py-1">Barang / Jasa</th><th className="text-right">Qty</th><th className="text-right">Harga</th><th className="text-right">Subtotal</th></tr></thead>
          <tbody>
            {lines.map((l, i) => (
              <tr key={i} className="border-b border-gray-300 align-top">
                <td className="py-1.5"><b>{l.name}</b>{l.detail && <div>{l.detail}</div>}{(l.options || []).map((o, k) => <div key={k}>+ {o.name} ({rp(o.price)})</div>)}
                  {l.warranty_until && <div>Garansi s/d {fmtDate(l.warranty_until)}</div>}</td>
                <td className="text-right">{l.qty}</td><td className="text-right">{rp(l.unit_price)}</td><td className="text-right">{rp(l.subtotal)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="space-y-1.5 border-b border-dashed border-black py-2">
          {lines.map((l, i) => (
            <div key={i}>
              <p className="font-bold">{l.name}</p>
              {l.detail && <p>{l.detail}</p>}
              {(l.options || []).map((o, k) => <p key={k}>+ {o.name}</p>)}
              <Row l={`${l.qty} x ${rp(l.unit_price)}`} r={rp(l.subtotal)} />
              {l.warranty_until && <p>Garansi s/d {fmtDate(l.warranty_until)}</p>}
            </div>
          ))}
        </div>
      )}
      <div className="space-y-0.5 py-2">
        <Row l="Subtotal" r={rp(d.subtotal)} />
        {!!d.discount_amount && <Row l="Diskon (disetujui)" r={`-${rp(d.discount_amount)}`} />}
        {!!d.shipping_cost && (d.shipping_payer === "cod_kurir"
          ? <Row l={`Ongkir COD (dibayar ke kurir ${d.courier || "J&T"} saat diterima)`} r={rp(d.shipping_cost)} />
          : <Row l={d.kind === "order" ? "Ongkir (dibayar ke bengkel)" : "Ongkir"} r={rp(d.shipping_cost)} />)}
        <Row l={d.kind === "order" ? "TAGIHAN BENGKEL" : "TOTAL"} r={rp(d.total)} b />
        <Row l={d.kind === "order" ? "Dibayar ke bengkel" : "Dibayar"} r={rp(d.paid)} />
        {!!d.refunded && <Row l="Dikembalikan" r={rp(d.refunded)} />}
        {d.kind === "order" ? <Row l="Sisa tagihan ke bengkel" r={rp(Math.max(d.remaining, 0))} b /> : d.remaining > 0 && <Row l="Sisa" r={rp(d.remaining)} b />}
        {d.change > 0 && <Row l="Kembalian" r={rp(d.change)} />}
      </div>
      {!!d.payments?.length && a4 && (
        <div className="border-t border-dashed border-black py-2">
          <p className="font-bold">Riwayat pembayaran</p>
          {d.payments.map((p, i) => <Row key={i} l={`${fmtDate(p.date_local)} · ${p.kind} · ${p.method}`} r={`${p.direction === "out" ? "-" : ""}${rp(p.amount)}`} />)}
        </div>
      )}
      <p className="border-t border-dashed border-black pt-2 text-center">Terima kasih</p>
    </div>
  );
}

export function toReceipt(kind, doc) {
  return {
    kind, no: doc.no, date: doc.created_at, customer_name: doc.customer?.name || doc.customer_name, plate: doc.vehicle?.plate,
    status: doc.status === "proses" ? "" : doc.status || doc.ship_status, lines: (doc.lines || []).filter((l) => !l.removed),
    subtotal: doc.subtotal, discount_amount: doc.discount_amount, shipping_cost: doc.shipping_cost, total: doc.total, paid: doc.paid,
    refunded: doc.refunded, remaining: Math.max(doc.total - doc.paid, 0), change: doc.change, payments: doc.payments,
    shipping_payer: doc.shipping_payer, courier: doc.courier,
  };
}

import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Plus, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { rp, fmtDateTime } from "@/lib/fmt";
import { Btn, Field, Input, Textarea, Select, NumInput, Card, Table, Td, PageHead, Badge } from "@/admin/ui";
import { useLoad, act, LinePicker } from "@/admin/tx";

export function OrderList() {
  const [status, setStatus] = useState("");
  const [cod, setCod] = useState(false);
  const [q, setQ] = useState("");
  const [rows] = useLoad(`/orders?q=${encodeURIComponent(q)}${status ? `&status=${status}` : ""}${cod ? "&cod_pending=true" : ""}`);
  return (
    <div>
      <PageHead title="Pesanan WhatsApp" sub="Pesanan langsung via WA (bukan marketplace). COD hanya Pulau Jawa." actions={<Link to="/admin/pesanan/baru"><Btn data-testid="order-new-button"><Plus className="h-4 w-4" />Pesanan baru</Btn></Link>} />
      <div className="mb-4 flex flex-wrap gap-2">
        {["", "Baru", "Dikirim", "Diterima", "Diambil", "Kembali", "Batal"].map((s) => (
          <button key={s || "all"} onClick={() => { setStatus(s); setCod(false); }} className={`rounded-md px-3 py-1.5 text-sm font-semibold ${status === s && !cod ? "bg-slate-900 text-white" : "border border-slate-300 bg-white"}`} data-testid={`order-filter-${s || "semua"}`}>{s || "Semua"}</button>
        ))}
        <button onClick={() => { setCod(!cod); setStatus(""); }} className={`rounded-md px-3 py-1.5 text-sm font-semibold ${cod ? "bg-amber-600 text-white" : "border border-amber-400 bg-amber-50 text-amber-900"}`} data-testid="order-filter-cod-pending">COD belum cair</button>
        <Input className="max-w-xs" placeholder="Cari no / nama / resi" value={q} onChange={(e) => setQ(e.target.value)} data-testid="order-search" />
      </div>
      <Table head={["No", "Tanggal", "Pelanggan", "Tujuan", "Bayar", "Total", "Dibayar", "Status"]} testid="order-table" empty={rows && !rows.length && "Tidak ada pesanan."}>
        {(rows || []).map((o) => (
          <tr key={o.id}><Td><Link to={`/admin/pesanan/${o.id}`} className="font-semibold text-sky-800 hover:underline" data-testid={`order-link-${o.no}`}>{o.no}</Link></Td>
            <Td className="whitespace-nowrap">{fmtDateTime(o.created_at)}</Td><Td>{o.customer.name}<div className="text-xs text-slate-500">{o.customer.phone}</div></Td>
            <Td>{o.delivery === "ambil" ? "Ambil sendiri" : `${o.province} · ${o.courier}`}</Td>
            <Td><Badge tone={o.payment_type === "cod" ? "Masuk" : "Baru"}>{o.payment_type === "cod" ? "COD" : "Prabayar"}</Badge></Td>
            <Td className="font-mono-num">{rp(o.total)}</Td><Td className="font-mono-num">{rp(o.paid)}</Td><Td><Badge>{o.ship_status}</Badge></Td></tr>
        ))}
      </Table>
    </div>
  );
}

export function OrderNew() {
  const nav = useNavigate();
  const [provs] = useLoad("/provinces");
  const [pkgs] = useLoad("/packages");
  const [items] = useLoad("/items?active_only=true");
  const [lines, setLines] = useState([]);
  const [f, setF] = useState({ customer_name: "", customer_phone: "", address: "", province: "", delivery: "kurir", courier: "J&T", shipping_cost: 0, payment_type: "prabayar", notes: "" });
  const java = (provs || []).find((p) => p.name === f.province)?.is_java;
  const codOk = f.delivery === "kurir" && java;
  const label = (l) => {
    if (l.type === "package") { const p = pkgs?.find((x) => x.id === l.package_id); const o = p?.options.filter((x) => l.option_ids.includes(x.id)) || []; return [p?.name + (o.length ? ` + ${o.map((x) => x.name).join(", ")}` : ""), (p?.price || 0) + o.reduce((s, x) => s + x.price, 0)]; }
    if (l.type === "item") { const i = items?.find((x) => x.id === l.item_id); return [i?.name, i?.price || 0]; }
    return [l.name, l.unit_price];
  };
  const sub = useMemo(() => lines.reduce((s, l) => s + label(l)[1] * l.qty, 0), [lines, pkgs, items]); // eslint-disable-line react-hooks/exhaustive-deps
  const submit = async () => {
    const r = await act(() => api.post("/orders", { ...f, shipping_cost: Number(f.shipping_cost || 0), payment_type: codOk ? f.payment_type : "prabayar", lines }), "Pesanan dicatat");
    if (r) nav(`/admin/pesanan/${r.id}`);
  };
  return (
    <div className="max-w-4xl">
      <PageHead title="Pesanan WhatsApp Baru" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Pelanggan & pengiriman">
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <Field label="Nama"><Input value={f.customer_name} onChange={(e) => setF({ ...f, customer_name: e.target.value })} data-testid="order-customer-name" /></Field>
              <Field label="No WhatsApp"><Input value={f.customer_phone} onChange={(e) => setF({ ...f, customer_phone: e.target.value })} data-testid="order-customer-phone" /></Field>
            </div>
            <Field label="Pengiriman"><Select value={f.delivery} onChange={(e) => setF({ ...f, delivery: e.target.value })} data-testid="order-delivery-select"><option value="kurir">Dikirim kurir</option><option value="ambil">Diambil langsung di bengkel</option></Select></Field>
            {f.delivery === "kurir" && (<>
              <Field label="Provinsi tujuan"><Select value={f.province} onChange={(e) => setF({ ...f, province: e.target.value })} data-testid="order-province-select">
                <option value="">Pilih provinsi…</option>{(provs || []).map((p) => <option key={p.name} value={p.name}>{p.name}{p.is_java ? " (Jawa)" : ""}</option>)}</Select></Field>
              <Field label="Alamat lengkap"><Textarea value={f.address} onChange={(e) => setF({ ...f, address: e.target.value })} data-testid="order-address" /></Field>
              <div className="grid grid-cols-2 gap-2">
                <Field label="Kurir"><Input value={f.courier} onChange={(e) => setF({ ...f, courier: e.target.value })} data-testid="order-courier" /></Field>
                <Field label="Ongkir"><NumInput value={f.shipping_cost} onChange={(v) => setF({ ...f, shipping_cost: v })} data-testid="order-shipping-cost" /></Field>
              </div>
            </>)}
            <Field label="Pembayaran" hint={f.delivery === "kurir" && f.province && !java ? "Tujuan luar Jawa: wajib bayar di muka (COD tidak tersedia)." : ""}>
              <Select value={codOk ? f.payment_type : "prabayar"} onChange={(e) => setF({ ...f, payment_type: e.target.value })} data-testid="order-payment-type">
                <option value="prabayar">Bayar di muka (tunai/transfer)</option>{codOk && <option value="cod">COD (bayar di tempat)</option>}
              </Select>
            </Field>
            <Field label="Catatan"><Input value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} data-testid="order-notes" /></Field>
          </div>
        </Card>
        <Card title="Barang">
          <LinePicker onAdd={(l) => setLines([...lines, l])} />
          <div className="mt-4 divide-y divide-slate-100 text-sm" data-testid="order-lines">
            {lines.map((l, i) => { const [n, p] = label(l); return (
              <div key={i} className="flex items-center justify-between gap-2 py-2"><span>{n} x{l.qty}</span><span className="flex items-center gap-2 font-mono-num">{rp(p * l.qty)}
                <button onClick={() => setLines(lines.filter((_, k) => k !== i))} className="text-red-700"><Trash2 className="h-4 w-4" /></button></span></div>); })}
          </div>
          <div className="mt-3 space-y-1 border-t pt-3 text-sm">
            <p className="flex justify-between"><span>Subtotal barang</span><span className="font-mono-num">{rp(sub)}</span></p>
            <p className="flex justify-between"><span>Ongkir</span><span className="font-mono-num">{rp(f.delivery === "kurir" ? f.shipping_cost : 0)}</span></p>
            <p className="flex justify-between text-base font-bold"><span>Total</span><span className="font-mono-num" data-testid="order-total-preview">{rp(sub + (f.delivery === "kurir" ? Number(f.shipping_cost || 0) : 0))}</span></p>
          </div>
        </Card>
      </div>
      <Btn className="mt-4" onClick={submit} disabled={!lines.length || !f.customer_name} data-testid="order-create-submit">Simpan pesanan</Btn>
    </div>
  );
}

import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Plus, Trash2, UserPlus, X } from "lucide-react";
import { api } from "@/lib/api";
import { rp, fmtDateTime } from "@/lib/fmt";
import { normalizeWa } from "@/lib/wa";
import { Btn, Field, Input, Textarea, Select, NumInput, Card, Table, Td, PageHead, Badge } from "@/admin/ui";
import { useLoad, act, LinePicker } from "@/admin/tx";

export const shipLabel = (o) => (o.delivery === "ambil" ? "Ambil sendiri" : o.shipping_payer === "cod_kurir" ? "COD ongkir ke kurir" : o.legacy_cod ? "COD barang (data lama)" : "Ongkir di muka");

export function OrderList() {
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [rows] = useLoad(`/orders?q=${encodeURIComponent(q)}${status ? `&status=${status}` : ""}`);
  return (
    <div>
      <PageHead title="Pesanan WhatsApp" sub="Harga barang selalu dibayar di muka. COD hanya untuk ongkir (tujuan Pulau Jawa, kurir J&T)." actions={<Link to="/admin/pesanan/baru"><Btn data-testid="order-new-button"><Plus className="h-4 w-4" />Pesanan baru</Btn></Link>} />
      <div className="mb-4 flex flex-wrap gap-2">
        {["", "Baru", "Dikirim", "Diterima", "Diambil", "Kembali", "Batal"].map((s) => (
          <button key={s || "all"} onClick={() => setStatus(s)} className={`rounded-md px-3 py-1.5 text-sm font-semibold ${status === s ? "bg-slate-900 text-white" : "border border-slate-300 bg-white"}`} data-testid={`order-filter-${s || "semua"}`}>{s || "Semua"}</button>
        ))}
        <Input className="max-w-xs" placeholder="Cari no / nama / resi" value={q} onChange={(e) => setQ(e.target.value)} data-testid="order-search" />
      </div>
      <Table head={["No", "Tanggal", "Pelanggan", "Tujuan", "Ongkir", "Tagihan bengkel", "Dibayar", "Status"]} testid="order-table" empty={rows && !rows.length && "Tidak ada pesanan."}>
        {(rows || []).map((o) => (
          <tr key={o.id}><Td><Link to={`/admin/pesanan/${o.id}`} className="font-semibold text-sky-800 hover:underline" data-testid={`order-link-${o.no}`}>{o.no}</Link></Td>
            <Td className="whitespace-nowrap">{fmtDateTime(o.created_at)}</Td><Td>{o.customer.name}<div className="text-xs text-slate-500">{o.customer.phone}</div></Td>
            <Td>{o.delivery === "ambil" ? "Ambil sendiri" : `${o.province} · ${o.courier}`}</Td>
            <Td><Badge tone={o.legacy_cod ? "Masuk" : "Baru"}>{shipLabel(o)}</Badge></Td>
            <Td className="font-mono-num">{rp(o.total)}</Td><Td className="font-mono-num">{rp(o.paid)}</Td><Td><Badge>{o.ship_status}</Badge></Td></tr>
        ))}
      </Table>
    </div>
  );
}

function CustomerPicker({ value, onPick }) {
  const [q, setQ] = useState("");
  const [res, setRes] = useState([]);
  const [nf, setNf] = useState(null);
  useEffect(() => {
    if (q.trim().length < 2) { setRes([]); return; }
    const t = setTimeout(() => api.get(`/customers?q=${encodeURIComponent(q)}`).then((r) => setRes(r.data.slice(0, 8))), 250);
    return () => clearTimeout(t);
  }, [q]);
  const create = async () => {
    const r = await act(() => api.post("/customers", nf), "Pelanggan baru dibuat");
    if (r) { onPick(r); setNf(null); }
  };
  if (value) return (
    <div className="flex items-start justify-between rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm" data-testid="order-customer-selected">
      <div><b>{value.name}</b> · {value.phone}{value.address && <p className="text-xs text-slate-600">Alamat tersimpan: {value.address}{value.province && ` (${value.province})`}</p>}</div>
      <button onClick={() => onPick(null)} className="text-slate-600" data-testid="order-customer-clear"><X className="h-4 w-4" /></button>
    </div>
  );
  if (nf) return (
    <div className="space-y-2 rounded-md border border-slate-200 p-3" data-testid="order-customer-new-form">
      <div className="grid grid-cols-2 gap-2">
        <Field label="Nama"><Input value={nf.name} onChange={(e) => setNf({ ...nf, name: e.target.value })} data-testid="order-customer-name" /></Field>
        <Field label="No WhatsApp" hint={nf.phone && !normalizeWa(nf.phone) ? "Format 08…, 62…, atau +62…" : ""}><Input value={nf.phone} onChange={(e) => setNf({ ...nf, phone: e.target.value })} data-testid="order-customer-phone" /></Field>
      </div>
      <div className="flex gap-2"><Btn size="sm" disabled={!nf.name || !normalizeWa(nf.phone)} onClick={create} data-testid="order-customer-create">Simpan pelanggan</Btn><Btn size="sm" v="outline" onClick={() => setNf(null)}>Batal</Btn></div>
    </div>
  );
  return (
    <div className="space-y-2">
      <Input placeholder="Cari nama atau nomor WhatsApp pelanggan…" value={q} onChange={(e) => setQ(e.target.value)} data-testid="order-customer-search" />
      {res.map((c) => (
        <button key={c.id} onClick={() => onPick(c)} className="block w-full rounded-md border border-slate-200 bg-white p-2 text-left text-sm hover:border-sky-400" data-testid={`order-customer-result-${c.phone}`}>
          <b>{c.name}</b> · {c.phone || "tanpa nomor"}{c.address && <span className="text-xs text-slate-500"> · {c.province || c.address.slice(0, 30)}</span>}
        </button>
      ))}
      {q.trim().length >= 2 && !res.length && <p className="text-xs text-slate-500">Tidak ditemukan.</p>}
      <Btn size="sm" v="outline" onClick={() => setNf({ name: normalizeWa(q) ? "" : q, phone: normalizeWa(q) ? q : "" })} data-testid="order-customer-new"><UserPlus className="h-4 w-4" />Pelanggan baru</Btn>
    </div>
  );
}

function ShippingFields({ f, setF, provs, java }) {
  return (<>
    <Field label="Provinsi tujuan"><Select value={f.province} onChange={(e) => setF({ ...f, province: e.target.value })} data-testid="order-province-select">
      <option value="">Pilih provinsi…</option>{(provs || []).map((p) => <option key={p.name} value={p.name}>{p.name}{p.is_java ? " (Jawa)" : ""}</option>)}</Select></Field>
    <Field label="Alamat lengkap"><Textarea value={f.address} onChange={(e) => setF({ ...f, address: e.target.value })} data-testid="order-address" /></Field>
    <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={f.save_address} onChange={(e) => setF({ ...f, save_address: e.target.checked })} data-testid="order-save-address" />Simpan alamat ini ke data pelanggan</label>
    <div className="grid grid-cols-2 gap-2">
      <Field label="Kurir"><Input value={f.shipping_payer === "cod_kurir" ? "J&T" : f.courier} disabled={f.shipping_payer === "cod_kurir"} onChange={(e) => setF({ ...f, courier: e.target.value })} data-testid="order-courier" /></Field>
      <Field label="Ongkir"><NumInput value={f.shipping_cost} onChange={(v) => setF({ ...f, shipping_cost: v })} data-testid="order-shipping-cost" /></Field>
    </div>
    <Field label="Cara bayar ongkir" hint={f.province && !java ? "Tujuan luar Pulau Jawa: ongkir wajib dibayar di muka ke bengkel." : "COD ongkir: pelanggan membayar ongkir ke kurir J&T saat paket diterima — bukan uang bengkel."}>
      <Select value={java ? f.shipping_payer : "bengkel"} onChange={(e) => setF({ ...f, shipping_payer: e.target.value })} data-testid="order-shipping-payer">
        <option value="bengkel">Dibayar di muka ke bengkel (bersama barang)</option>{java && <option value="cod_kurir">COD ongkir — dibayar ke kurir J&T saat diterima</option>}
      </Select>
    </Field>
  </>);
}

export function OrderNew() {
  const nav = useNavigate();
  const [provs] = useLoad("/provinces");
  const [pkgs] = useLoad("/packages");
  const [items] = useLoad("/items?active_only=true");
  const [lines, setLines] = useState([]);
  const [cust, setCust] = useState(null);
  const [f, setF] = useState({ address: "", province: "", delivery: "kurir", courier: "J&T", shipping_cost: 0, shipping_payer: "bengkel", save_address: true, notes: "" });
  const java = (provs || []).find((p) => p.name === f.province)?.is_java;
  const pick = (c) => {
    setCust(c);
    if (c?.address && (!f.address || window.confirm(`Pakai alamat tersimpan?\n${c.address} (${c.province || "-"})`))) setF({ ...f, address: c.address, province: c.province || f.province });
  };
  const label = (l) => {
    if (l.type === "package") { const p = pkgs?.find((x) => x.id === l.package_id); const o = p?.options.filter((x) => l.option_ids.includes(x.id)) || []; return [p?.name + (o.length ? ` + ${o.map((x) => x.name).join(", ")}` : ""), (p?.price || 0) + o.reduce((s, x) => s + x.price, 0)]; }
    if (l.type === "item") { const i = items?.find((x) => x.id === l.item_id); return [i ? `${i.name} (${i.sku})` : "", i?.price || 0]; }
    return [l.name, l.unit_price];
  };
  const sub = useMemo(() => lines.reduce((s, l) => s + label(l)[1] * l.qty, 0), [lines, pkgs, items]); // eslint-disable-line react-hooks/exhaustive-deps
  const kurir = f.delivery === "kurir";
  const payer = !kurir ? "none" : java ? f.shipping_payer : "bengkel";
  const ship = kurir ? Number(f.shipping_cost || 0) : 0;
  const submit = async () => {
    const r = await act(() => api.post("/orders", { ...f, customer_id: cust.id, shipping_cost: ship, shipping_payer: payer === "none" ? "bengkel" : payer, lines }), "Pesanan dicatat");
    if (r) nav(`/admin/pesanan/${r.id}`);
  };
  return (
    <div className="max-w-4xl">
      <PageHead title="Pesanan WhatsApp Baru" sub="Pilih pelanggan dari master pelanggan, atau buat pelanggan baru di sini." />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Pelanggan & pengiriman">
          <div className="space-y-3">
            <CustomerPicker value={cust} onPick={pick} />
            <Field label="Pengiriman"><Select value={f.delivery} onChange={(e) => setF({ ...f, delivery: e.target.value })} data-testid="order-delivery-select"><option value="kurir">Dikirim kurir</option><option value="ambil">Diambil langsung di bengkel (tanpa ongkir)</option></Select></Field>
            {kurir && <ShippingFields f={f} setF={setF} provs={provs} java={java} />}
            <p className="rounded-md bg-slate-50 p-2 text-xs text-slate-700" data-testid="order-goods-payment-info">Cara bayar barang: <b>dibayar lunas di muka</b> (tunai/transfer) sebelum dikirim. Stok berkurang saat barang lunas.</p>
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
            <p className="flex justify-between"><span>Harga barang</span><span className="font-mono-num">{rp(sub)}</span></p>
            <p className="flex justify-between"><span>Ongkir {payer === "cod_kurir" ? "(COD, dibayar ke kurir)" : payer === "bengkel" ? "(dibayar ke bengkel)" : ""}</span><span className="font-mono-num">{rp(ship)}</span></p>
            <p className="flex justify-between text-base font-bold"><span>Tagihan ke bengkel</span><span className="font-mono-num" data-testid="order-total-preview">{rp(sub + (payer === "bengkel" ? ship : 0))}</span></p>
          </div>
        </Card>
      </div>
      <Btn className="mt-4" onClick={submit} disabled={!lines.length || !cust} data-testid="order-create-submit">Simpan pesanan</Btn>
    </div>
  );
}

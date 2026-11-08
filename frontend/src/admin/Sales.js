import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Minus, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, errMsg, newKey } from "@/lib/api";
import { rp, fmtDateTime, today } from "@/lib/fmt";
import { useAuth, isOwner, isManager } from "@/context/AuthContext";
import { Btn, Field, Input, NumInput, Card, Table, Td, PageHead, Badge, Modal } from "@/admin/ui";
import { useLoad, ItemSearch, LinesTable, Totals, PaymentsList, ReturnDialog, NotaActions, ReturnsList } from "@/admin/tx";
import Receipt, { toReceipt } from "@/components/Receipt";
import { ClaimStart } from "@/admin/JobDetail";

export default function Kasir() {
  const { user } = useAuth();
  const [cart, setCart] = useState([]);
  const [f, setF] = useState({ customer_name: "", customer_phone: "", method: "tunai", cash_received: "" });
  const [disc, setDisc] = useState({ amount: "", reason: "" });
  const [key, setKey] = useState(newKey());
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null);
  const [site] = useLoad("/public/site");
  const [searchKey, setSearchKey] = useState(0);
  const add = (i) => setCart((c) => {
    const ex = c.find((x) => x.id === i.id);
    if (ex) return c.map((x) => (x.id === i.id ? { ...x, qty: Math.min(x.qty + 1, i.stock) } : x));
    return [...c, { id: i.id, name: i.name, sku: i.sku, price: i.price, stock: i.stock, qty: 1 }];
  });
  const setQty = (id, q) => setCart((c) => c.map((x) => (x.id === id ? { ...x, qty: Math.max(1, Math.min(q, x.stock)) } : x)));
  const sub = cart.reduce((s, x) => s + x.price * x.qty, 0);
  const d = isOwner(user) && disc.amount ? Math.min(Number(disc.amount), sub) : 0;
  const total = sub - d;
  const submit = async () => {
    setBusy(true);
    try {
      const body = { ...f, cash_received: f.method === "tunai" && f.cash_received !== "" ? Number(f.cash_received) : null, idem_key: key,
        lines: cart.map((x) => ({ item_id: x.id, qty: x.qty })), discount: d ? { amount: d, reason: disc.reason || "Diskon owner" } : null };
      const r = await api.post("/sales", body);
      setDone(r.data);
      toast.success(`Penjualan ${r.data.no} tersimpan`);
      setCart([]); setF({ customer_name: "", customer_phone: "", method: "tunai", cash_received: "" }); setDisc({ amount: "", reason: "" });
      setKey(newKey()); setSearchKey((k) => k + 1);
    } catch (e) {
      toast.error(errMsg(e));
    }
    setBusy(false);
  };
  return (
    <div>
      <PageHead title="Kasir Penjualan Langsung" sub="Satu transaksi per pembeli. Rekap harian dihitung otomatis." actions={<Link to={`/admin/penjualan?date=${today()}`}><Btn v="outline" data-testid="kasir-today-sales">Penjualan hari ini</Btn></Link>} />
      <div className="grid gap-4 lg:grid-cols-[1fr_420px]">
        <Card title="Pilih barang"><ItemSearch key={searchKey} onPick={add} testid="kasir-item" /></Card>
        <Card title="Keranjang" data-testid="kasir-cart">
          {!cart.length && <p className="text-sm text-slate-500">Belum ada barang.</p>}
          <div className="divide-y divide-slate-100">
            {cart.map((x) => (
              <div key={x.id} className="flex items-center gap-2 py-2 text-sm" data-testid={`cart-row-${x.sku}`}>
                <div className="min-w-0 flex-1"><p className="truncate font-semibold">{x.name}</p><p className="font-mono-num text-xs text-slate-500">{rp(x.price)} · stok {x.stock}</p></div>
                <button onClick={() => setQty(x.id, x.qty - 1)} className="rounded border p-1" data-testid={`cart-dec-${x.sku}`}><Minus className="h-3 w-3" /></button>
                <span className="w-8 text-center font-mono-num" data-testid={`cart-qty-${x.sku}`}>{x.qty}</span>
                <button onClick={() => setQty(x.id, x.qty + 1)} className="rounded border p-1" data-testid={`cart-inc-${x.sku}`}><Plus className="h-3 w-3" /></button>
                <span className="w-24 text-right font-mono-num">{rp(x.price * x.qty)}</span>
                <button onClick={() => setCart(cart.filter((c) => c.id !== x.id))} className="text-red-700" data-testid={`cart-remove-${x.sku}`}><Trash2 className="h-4 w-4" /></button>
              </div>
            ))}
          </div>
          <div className="mt-3 space-y-3 border-t border-slate-200 pt-3">
            <div className="grid grid-cols-2 gap-2">
              <Input placeholder="Nama pembeli (opsional)" value={f.customer_name} onChange={(e) => setF({ ...f, customer_name: e.target.value })} data-testid="kasir-customer-name" />
              <Input placeholder="No WA (opsional)" value={f.customer_phone} onChange={(e) => setF({ ...f, customer_phone: e.target.value })} data-testid="kasir-customer-phone" />
            </div>
            {isOwner(user) && (
              <div className="grid grid-cols-2 gap-2">
                <NumInput placeholder="Diskon (owner)" value={disc.amount} onChange={(v) => setDisc({ ...disc, amount: v })} data-testid="kasir-discount-amount" />
                <Input placeholder="Alasan diskon" value={disc.reason} onChange={(e) => setDisc({ ...disc, reason: e.target.value })} data-testid="kasir-discount-reason" />
              </div>
            )}
            <div className="flex gap-2">
              {["tunai", "transfer"].map((m) => (
                <button key={m} onClick={() => setF({ ...f, method: m })} className={`flex-1 rounded-md border py-2 text-sm font-semibold capitalize ${f.method === m ? "border-sky-700 bg-sky-50 text-sky-900" : "border-slate-300"}`} data-testid={`kasir-method-${m}`}>{m}</button>
              ))}
            </div>
            {f.method === "tunai" && <Field label="Uang diterima (opsional, untuk kembalian)"><NumInput value={f.cash_received} onChange={(v) => setF({ ...f, cash_received: v })} data-testid="kasir-cash-received" /></Field>}
            <div className="flex justify-between text-sm"><span>Subtotal</span><span className="font-mono-num">{rp(sub)}</span></div>
            {!!d && <div className="flex justify-between text-sm"><span>Diskon</span><span className="font-mono-num">-{rp(d)}</span></div>}
            <div className="flex justify-between text-lg font-bold"><span>Total</span><span className="font-mono-num" data-testid="kasir-total">{rp(total)}</span></div>
            {f.method === "tunai" && f.cash_received !== "" && <div className="flex justify-between text-sm"><span>Kembalian</span><span className="font-mono-num">{rp(Math.max(f.cash_received - total, 0))}</span></div>}
            <Btn className="h-12 w-full text-base" disabled={!cart.length || busy} onClick={submit} data-testid="kasir-submit">{busy ? "Menyimpan…" : "Simpan & bayar"}</Btn>
          </div>
        </Card>
      </div>
      <Modal open={!!done} onClose={() => setDone(null)} title={`Nota ${done?.no || ""}`}>
        {done && <div className="space-y-3"><div className="max-h-[50vh] overflow-y-auto border"><Receipt d={toReceipt("sale", done)} identity={site?.identity} contact={site?.contact} /></div>
          <NotaActions kind="sale" doc={done} shopName={site?.identity?.name} /></div>}
      </Modal>
    </div>
  );
}

export function SaleList() {
  const params = new URLSearchParams(window.location.search);
  const [date, setDate] = useState(params.get("date") || today());
  const [q, setQ] = useState("");
  const [rows] = useLoad(`/sales?q=${encodeURIComponent(q)}${date ? `&date_from=${date}&date_to=${date}` : ""}`);
  const [recap] = useLoad(`/reports/daily?date=${date || today()}`);
  return (
    <div>
      <PageHead title="Nota Penjualan Langsung" sub="Cari, buka, cetak, dan retur nota penjualan." />
      <div className="mb-4 flex flex-wrap gap-2">
        <Input type="date" className="w-44" value={date} onChange={(e) => setDate(e.target.value)} data-testid="sales-date-filter" />
        <Input className="max-w-xs" placeholder="Cari no nota / nama" value={q} onChange={(e) => setQ(e.target.value)} data-testid="sales-search" />
      </div>
      {recap && date && (
        <div className="mb-4 rounded-md border border-sky-200 bg-sky-50 p-3 text-sm" data-testid="sales-daily-recap">
          Rekap otomatis {date}: <b>{recap.types.sale.count}</b> transaksi · omzet <b className="font-mono-num">{rp(recap.types.sale.omzet)}</b> · tunai masuk (semua jenis) {rp(recap.payments_in.tunai)} · transfer {rp(recap.payments_in.transfer)}
        </div>
      )}
      <Table head={["No", "Waktu", "Pembeli", "Metode", "Total", "Status"]} testid="sales-table" empty={rows && !rows.length && "Tidak ada penjualan."}>
        {(rows || []).map((s) => (
          <tr key={s.id}><Td><Link to={`/admin/penjualan/${s.id}`} className="font-semibold text-sky-800 hover:underline" data-testid={`sale-link-${s.no}`}>{s.no}</Link></Td>
            <Td>{fmtDateTime(s.created_at)}</Td><Td>{s.customer_name || "-"}</Td><Td className="capitalize">{s.method}</Td>
            <Td className="font-mono-num">{rp(s.total)}</Td><Td><Badge>{s.returns?.length ? "Ada retur" : s.status}</Badge></Td></tr>
        ))}
      </Table>
    </div>
  );
}

export function SaleDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const [s, , setS] = useLoad(`/sales/${id}`);
  const [site] = useLoad("/public/site");
  const [ret, setRet] = useState(false);
  const [claim, setClaim] = useState(false);
  if (!s) return <p>Memuat…</p>;
  return (
    <div>
      <PageHead title={s.no} sub={`Penjualan langsung · ${fmtDateTime(s.created_at)} · ${s.created_by}`} actions={<NotaActions kind="sale" doc={s} shopName={site?.identity?.name} />} />
      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <div className="space-y-4"><Card title={`Pembeli: ${s.customer_name || "Umum"}`}><LinesTable doc={s} /></Card><ReturnsList returns={s.returns} /></div>
        <div className="space-y-4">
          <Card title="Total"><Totals doc={s} /></Card>
          <Card title="Pembayaran"><PaymentsList payments={s.payments} /></Card>
          <div className="flex flex-wrap gap-2">
            <Btn v="outline" onClick={() => setClaim(true)} data-testid="sale-claim-button">Klaim garansi</Btn>
            {isManager(user) && <Btn v="outline" onClick={() => setRet(true)} data-testid="sale-return-button">Retur / pengembalian</Btn>}
          </div>
          {!!s.claims?.length && <Card title="Klaim garansi">{s.claims.map((c) => <p key={c.id} className="text-sm"><Link className="font-semibold text-sky-800 underline" to={`/admin/pekerjaan/${c.id}`}>{c.no}</Link> · {c.claim.line_name} · {c.status}</p>)}</Card>}
        </div>
      </div>
      {ret && <ReturnDialog kind="sale" doc={s} open onClose={() => setRet(false)} onDone={setS} />}
      {claim && <ClaimStart job={s} kind="sale" onClose={() => setClaim(false)} />}
    </div>
  );
}

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Printer, Send, Trash2, Pencil } from "lucide-react";
import { api, errMsg, newKey } from "@/lib/api";
import { rp, fmtDateTime, fmtDate, waLink, notaText } from "@/lib/fmt";
import { useAuth, isManager, isOwner } from "@/context/AuthContext";
import { Btn, Field, Input, NumInput, Select, Card, Table, Td, Modal, Badge } from "@/admin/ui";

export function useLoad(url) {
  const [data, setData] = useState(null);
  const load = useCallback(() => {
    if (url) api.get(url).then((r) => setData(r.data)).catch((e) => toast.error(errMsg(e)));
  }, [url]);
  useEffect(() => { load(); }, [load]);
  return [data, load, setData];
}

export async function act(fn, ok) {
  try {
    const r = await fn();
    if (ok) toast.success(ok);
    return r?.data ?? true;
  } catch (e) {
    toast.error(errMsg(e));
    return null;
  }
}

export function ItemSearch({ onPick, testid = "item-search" }) {
  const [q, setQ] = useState("");
  const [items] = useLoad("/items?active_only=true");
  const list = (items || []).filter((i) => !q || `${i.name} ${i.sku} ${i.brand} ${i.category}`.toLowerCase().includes(q.toLowerCase())).slice(0, 30);
  return (
    <div>
      <Input placeholder="Cari nama / SKU barang…" value={q} onChange={(e) => setQ(e.target.value)} data-testid={`${testid}-input`} />
      <div className="mt-2 max-h-72 divide-y divide-slate-100 overflow-y-auto rounded-md border border-slate-200">
        {list.map((i) => (
          <button key={i.id} type="button" onClick={() => onPick(i)} disabled={i.stock <= 0}
            className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-sky-50 disabled:opacity-50" data-testid={`${testid}-result-${i.sku}`}>
            <span><b>{i.name}</b> <span className="text-xs text-slate-500">{i.sku} {i.variant}</span></span>
            <span className="whitespace-nowrap text-right"><span className="font-mono-num">{rp(i.price)}</span><span className={`ml-2 text-xs ${i.stock <= (i.min_stock || 0) ? "text-red-700" : "text-slate-500"}`}>stok {i.stock}</span></span>
          </button>
        ))}
        {!list.length && <p className="p-3 text-sm text-slate-500">Tidak ada barang.</p>}
      </div>
    </div>
  );
}

export function LinePicker({ onAdd, garansi, busy }) {
  const { user } = useAuth();
  const [tab, setTab] = useState("package");
  const [pkgs] = useLoad("/packages");
  const [pid, setPid] = useState("");
  const [opts, setOpts] = useState([]);
  const [qty, setQty] = useState(1);
  const [svc, setSvc] = useState({ name: "", price: "" });
  const [repl, setRepl] = useState(!!garansi);
  const pkg = (pkgs || []).find((p) => p.id === pid);
  const T = ({ k, l }) => <button type="button" onClick={() => setTab(k)} className={`rounded-md px-3 py-1.5 text-sm font-semibold ${tab === k ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-700"}`} data-testid={`linepicker-tab-${k}`}>{l}</button>;
  return (
    <div className="space-y-3" data-testid="line-picker">
      <div className="flex gap-2"><T k="package" l="Paket" /><T k="item" l="Barang" /><T k="service" l="Jasa" /></div>
      {tab === "package" && (
        <div className="space-y-3">
          <Select value={pid} onChange={(e) => { setPid(e.target.value); setOpts([]); }} data-testid="linepicker-package-select">
            <option value="">Pilih paket…</option>
            {(pkgs || []).filter((p) => p.active).map((p) => <option key={p.id} value={p.id}>{p.name} — {rp(p.price)}</option>)}
          </Select>
          {pkg && (
            <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">
              <p className="font-semibold">{pkg.main_brand_model}</p>
              <p className="text-xs text-slate-600">Komponen: {pkg.components.map((c) => `${c.name} x${c.qty} (stok ${c.stock})`).join(", ")}</p>
              {pkg.options.map((o) => (
                <label key={o.id} className="mt-2 flex items-center gap-2">
                  <input type="checkbox" checked={opts.includes(o.id)} onChange={(e) => setOpts(e.target.checked ? [...opts, o.id] : opts.filter((x) => x !== o.id))} data-testid={`linepicker-option-${o.id}`} />
                  {o.name} (+{rp(o.price)})
                </label>
              ))}
            </div>
          )}
          <Btn type="button" disabled={!pid || busy} onClick={() => onAdd({ type: "package", package_id: pid, option_ids: opts, qty: 1 })} data-testid="linepicker-add-package">Tambah paket</Btn>
        </div>
      )}
      {tab === "item" && (
        <div className="space-y-2">
          <div className="flex items-end gap-3">
            <Field label="Jumlah" className="w-24"><NumInput value={qty} onChange={setQty} min={1} data-testid="linepicker-item-qty" /></Field>
            {garansi && <label className="mb-2 flex items-center gap-2 text-sm"><input type="checkbox" checked={repl} onChange={(e) => setRepl(e.target.checked)} data-testid="linepicker-warranty-replacement" />Pengganti garansi (Rp0)</label>}
          </div>
          <ItemSearch testid="linepicker-item" onPick={(i) => onAdd({ type: "item", item_id: i.id, qty: qty || 1, warranty_replacement: garansi && repl })} />
        </div>
      )}
      {tab === "service" && (
        <div className="grid gap-2 sm:grid-cols-[1fr_160px_auto] sm:items-end">
          <Field label="Nama jasa"><Input value={svc.name} onChange={(e) => setSvc({ ...svc, name: e.target.value })} data-testid="linepicker-service-name" /></Field>
          <Field label="Harga"><NumInput value={svc.price} onChange={(v) => setSvc({ ...svc, price: v })} data-testid="linepicker-service-price" /></Field>
          <Btn type="button" disabled={!svc.name || svc.price === "" || busy} onClick={() => { onAdd({ type: "service", name: svc.name, unit_price: svc.price, qty: 1 }); setSvc({ name: "", price: "" }); }} data-testid="linepicker-add-service">Tambah</Btn>
        </div>
      )}
      {isManager(user) || <p className="text-xs text-slate-500">Perubahan/pembatalan baris yang sudah tercatat memerlukan admin/owner.</p>}
    </div>
  );
}

export function LinesTable({ doc, onEdit, onRemove }) {
  const { user } = useAuth();
  const canMod = onEdit && isManager(user);
  return (
    <Table head={["Barang / Jasa", "Qty", "Harga", "Subtotal", ""]} testid="lines-table" empty={!doc.lines.length && "Belum ada baris."}>
      {doc.lines.map((l) => (
        <tr key={l.lid} className={l.removed ? "bg-red-50 text-slate-400 line-through" : ""} data-testid={`line-${l.lid}`}>
          <Td><b>{l.name}</b>{l.detail && <div className="text-xs text-slate-600">{l.detail}</div>}
            {l.options?.map((o, i) => <div key={i} className="text-xs text-slate-600">+ {o.name} ({rp(o.price)})</div>)}
            {l.type === "package" && <div className="text-xs text-slate-500">Komponen: {l.components.map((c) => `${c.name} x${c.qty}`).join(", ")}</div>}
            {l.warranty_replacement && <Badge tone="Baru">Pengganti garansi</Badge>}
            {l.warranty_until && <div className="text-xs text-emerald-700">Garansi s/d {fmtDate(l.warranty_until)}</div>}
            {l.removed && <div className="text-xs no-underline">Dihapus {l.removed_by}: {l.removed_reason}</div>}
            <div className="text-[11px] text-slate-400">ditambah {l.added_by}</div></Td>
          <Td className="font-mono-num">{l.qty}</Td>
          <Td className="font-mono-num whitespace-nowrap">{rp(l.unit_price)}</Td>
          <Td className="font-mono-num whitespace-nowrap">{rp(l.subtotal)}</Td>
          <Td className="whitespace-nowrap">{canMod && !l.removed && (<>
            <button onClick={() => onEdit(l)} className="mr-2 text-slate-600 hover:text-sky-700" data-testid={`line-edit-${l.lid}`}><Pencil className="h-4 w-4" /></button>
            <button onClick={() => onRemove(l)} className="text-slate-600 hover:text-red-700" data-testid={`line-remove-${l.lid}`}><Trash2 className="h-4 w-4" /></button>
          </>)}</Td>
        </tr>
      ))}
    </Table>
  );
}

export function Totals({ doc }) {
  const R = ({ l, v, b, t }) => <div className={`flex justify-between py-1 ${b ? "text-base font-bold" : "text-sm"}`} data-testid={t}><span>{l}</span><span className="font-mono-num">{v}</span></div>;
  const rem = Math.max(doc.total - doc.paid, 0);
  return (
    <div className="divide-y divide-slate-100">
      <R l="Subtotal" v={rp(doc.subtotal)} t="total-subtotal" />
      {doc.discount && <R l={`Diskon (${doc.discount.status === "approved" ? "disetujui" : doc.discount.status === "pending" ? "menunggu owner" : "ditolak"})`} v={`-${rp(doc.discount_amount)}`} t="total-discount" />}
      {!!doc.shipping_cost && <R l="Ongkir" v={rp(doc.shipping_cost)} />}
      <R l="Total" v={rp(doc.total)} b t="total-grand" />
      <R l="Dibayar" v={rp(doc.paid)} t="total-paid" />
      {!!doc.refunded && <R l="Dikembalikan" v={rp(doc.refunded)} t="total-refunded" />}
      <R l="Sisa" v={doc.status === "Batal" || doc.ship_status === "Batal" ? "— (batal)" : rp(rem)} b t="total-remaining" />
    </div>
  );
}

export function PaymentBox({ kind, doc, onDone, cod }) {
  const rem = Math.max(doc.total - doc.paid, 0);
  const [f, setF] = useState({ amount: "", method: cod ? "cod" : "tunai", note: "" });
  const [key, setKey] = useState(newKey());
  const [busy, setBusy] = useState(false);
  if (doc.total <= 0) return <p className="text-sm text-slate-500" data-testid="payment-no-bill">Belum ada tagihan.</p>;
  if (rem <= 0) return <p className="text-sm font-semibold text-emerald-700" data-testid="payment-paid-full">Lunas</p>;
  const submit = async () => {
    setBusy(true);
    const r = await act(() => api.post(`/tx/${kind}/${doc.id}/payments`, { ...f, amount: Number(f.amount), idem_key: key }), "Pembayaran dicatat");
    setBusy(false);
    if (r) { setKey(newKey()); setF({ ...f, amount: "" }); onDone(r); }
  };
  return (
    <div className="space-y-2" data-testid="payment-box">
      <div className="grid grid-cols-2 gap-2">
        <Field label="Jumlah"><NumInput value={f.amount} onChange={(v) => setF({ ...f, amount: v })} data-testid="payment-amount-input" /></Field>
        <Field label="Metode">
          <Select value={f.method} onChange={(e) => setF({ ...f, method: e.target.value })} disabled={cod} data-testid="payment-method-select">
            {cod ? <option value="cod">COD (dana cair)</option> : <><option value="tunai">Tunai</option><option value="transfer">Transfer</option></>}
          </Select>
        </Field>
      </div>
      <Input placeholder="Catatan (opsional)" value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} data-testid="payment-note-input" />
      <div className="flex gap-2">
        <Btn v="outline" size="sm" type="button" onClick={() => setF({ ...f, amount: rem })} data-testid="payment-fill-remaining">Isi sisa {rp(rem)}</Btn>
        <Btn size="sm" disabled={!f.amount || busy} onClick={submit} data-testid="payment-submit">Catat pembayaran</Btn>
      </div>
    </div>
  );
}

export function PaymentsList({ payments }) {
  if (!payments?.length) return <p className="text-sm text-slate-500">Belum ada pembayaran.</p>;
  return (
    <div className="space-y-1 text-sm" data-testid="payments-list">
      {payments.map((p) => (
        <div key={p.id} className="flex justify-between gap-2 border-b border-slate-100 py-1">
          <span>{fmtDateTime(p.created_at)} · <b>{p.kind}</b> · {p.method} · {p.user_name}{p.note && ` · ${p.note}`}</span>
          <span className={`font-mono-num ${p.direction === "out" ? "text-red-700" : "text-emerald-700"}`}>{p.direction === "out" ? "-" : "+"}{rp(p.amount)}</span>
        </div>
      ))}
    </div>
  );
}

export function DiscountBox({ kind, doc, onDone, editable }) {
  const { user } = useAuth();
  const [f, setF] = useState({ amount: "", reason: "" });
  const d = doc.discount;
  const decide = async (approve) => { const r = await act(() => api.post(`/tx/${kind}/${doc.id}/discount/decide`, { approve }), approve ? "Diskon disetujui" : "Diskon ditolak"); r && onDone(r); };
  return (
    <div className="space-y-2 text-sm" data-testid="discount-box">
      {!d && !editable && <p className="text-slate-500">Tidak ada diskon.</p>}
      {d && <p data-testid="discount-status">Diskon {rp(d.amount)} — <b>{{ approved: "disetujui", pending: "menunggu persetujuan owner", rejected: "ditolak" }[d.status]}</b> · diajukan {d.requested_by}{d.decided_by && ` · diputuskan ${d.decided_by}`} · {d.reason}</p>}
      {d?.status === "pending" && isOwner(user) && (
        <div className="flex gap-2"><Btn v="success" size="sm" onClick={() => decide(true)} data-testid="discount-approve">Setujui</Btn><Btn v="danger" size="sm" onClick={() => decide(false)} data-testid="discount-reject">Tolak</Btn></div>
      )}
      {editable && d?.status !== "pending" && (
        <div className="grid gap-2 sm:grid-cols-[120px_1fr_auto] sm:items-end">
          <NumInput placeholder="Jumlah" value={f.amount} onChange={(v) => setF({ ...f, amount: v })} data-testid="discount-amount-input" />
          <Input placeholder="Alasan diskon" value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} data-testid="discount-reason-input" />
          <Btn size="sm" v="outline" disabled={!f.amount || f.reason.length < 3} data-testid="discount-submit"
            onClick={async () => { const r = await act(() => api.post(`/tx/${kind}/${doc.id}/discount`, { amount: Number(f.amount), reason: f.reason }), isOwner(user) ? "Diskon diterapkan" : "Diskon diajukan ke owner"); r && onDone(r); }}>
            {isOwner(user) ? "Terapkan diskon" : "Ajukan diskon"}
          </Btn>
        </div>
      )}
    </div>
  );
}

const CONDS = [["layak", "Layak jual (stok +)"], ["rusak", "Rusak (catat rusak)"], ["belum_kembali", "Belum kembali"]];

export function ReturnDialog({ kind, doc, open, onClose, onDone, title = "Retur / Pengembalian", endpoint, extra, cancelMode }) {
  const used = {};
  doc.lines.filter((l) => !l.removed).forEach((l) => l.components.forEach((c) => { used[c.item_id] = { name: c.name, qty: (used[c.item_id]?.qty || 0) + c.qty * l.qty }; }));
  (doc.returns || []).forEach((r) => r.items.forEach((i) => { if (used[i.item_id] && i.condition !== "belum_kembali") used[i.item_id].qty -= i.qty; }));
  const conds = cancelMode ? CONDS : CONDS.slice(0, 2);
  const [rows, setRows] = useState({});
  const [f, setF] = useState({ refund_amount: 0, refund_method: "tunai", reason: "" });
  const [key] = useState(newKey());
  const list = Object.entries(used).filter(([, u]) => u.qty > 0);
  const items = Object.entries(rows).flatMap(([item_id, r]) => conds.filter(([c]) => r[c] > 0).map(([c]) => ({ item_id, qty: r[c], condition: c })));
  const sumOf = (id) => conds.reduce((s, [c]) => s + (rows[id]?.[c] || 0), 0);
  const unassigned = list.filter(([id, u]) => sumOf(id) !== u.qty);
  const over = list.some(([id, u]) => sumOf(id) > u.qty);
  const blocked = over || (cancelMode && doc.stock_applied && unassigned.length > 0);
  const submit = async () => {
    const r = await act(() => api.post(endpoint || `/tx/${kind}/${doc.id}/return`, { ...f, refund_amount: Number(f.refund_amount || 0), items, idem_key: key }), "Tercatat");
    if (r) { onDone(r); onClose(); }
  };
  return (
    <Modal open={open} onClose={onClose} title={title} wide>
      <div className="space-y-4">
        {extra}
        {doc.stock_applied && (
          <div data-testid="return-items">
            <p className="mb-2 text-sm font-semibold">{cancelMode ? "Barang sudah keluar dari stok — tentukan status setiap pcs" : "Barang yang benar-benar kembali (isi 0 jika tidak ada)"}</p>
            <div className="mb-1 grid gap-2 text-xs font-semibold text-slate-600" style={{ gridTemplateColumns: `1fr repeat(${conds.length}, 110px)` }}>
              <span>Barang</span>{conds.map(([c, l]) => <span key={c}>{l}</span>)}
            </div>
            {list.map(([id, u]) => (
              <div key={id} className="mb-2 grid items-center gap-2 text-sm" style={{ gridTemplateColumns: `1fr repeat(${conds.length}, 110px)` }}>
                <span>{u.name} <span className={`text-xs ${sumOf(id) === u.qty ? "text-emerald-700" : "text-slate-500"}`}>({sumOf(id)}/{u.qty} pcs)</span></span>
                {conds.map(([c]) => (
                  <NumInput key={c} value={rows[id]?.[c] ?? 0} onChange={(v) => setRows({ ...rows, [id]: { ...rows[id], [c]: Math.max(0, Number(v || 0)) } })} data-testid={`return-${c}-${id}`} />
                ))}
              </div>
            ))}
            {cancelMode && unassigned.length > 0 && <p className="rounded-md bg-amber-50 p-2 text-sm text-amber-900" data-testid="return-unassigned">Belum ditentukan: {unassigned.map(([id, u]) => `${u.name} (${u.qty - sumOf(id)} pcs)`).join(", ")}. Semua pcs wajib dicatat sebelum pesanan dibatalkan.</p>}
            {over && <p className="text-sm text-red-700">Jumlah melebihi barang yang keluar.</p>}
          </div>
        )}
        <div className="grid grid-cols-2 gap-2">
          <Field label={`Uang dikembalikan (maks ${rp(doc.paid - (doc.refunded || 0))})`}><NumInput value={f.refund_amount} onChange={(v) => setF({ ...f, refund_amount: v })} data-testid="return-refund-input" /></Field>
          <Field label="Metode pengembalian"><Select value={f.refund_method} onChange={(e) => setF({ ...f, refund_method: e.target.value })} data-testid="return-refund-method"><option value="tunai">Tunai</option><option value="transfer">Transfer</option></Select></Field>
        </div>
        <Field label="Alasan / catatan keputusan"><Input value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} data-testid="return-reason-input" /></Field>
        <Btn v="danger" disabled={f.reason.length < 3 || blocked} onClick={submit} data-testid="return-submit">Simpan</Btn>
      </div>
    </Modal>
  );
}

export function NotaActions({ kind, doc, shopName }) {
  const nav = useNavigate();
  const phone = doc.customer?.phone || doc.customer_phone;
  return (
    <div className="flex flex-wrap gap-2">
      <Btn v="outline" size="sm" onClick={() => nav(`/admin/cetak/${kind}/${doc.id}?size=80`)} data-testid="nota-print-80"><Printer className="h-4 w-4" />Cetak 80mm</Btn>
      <Btn v="outline" size="sm" onClick={() => nav(`/admin/cetak/${kind}/${doc.id}?size=a4`)} data-testid="nota-print-a4"><Printer className="h-4 w-4" />A4</Btn>
      {phone && <Btn v="success" size="sm" onClick={() => window.open(waLink(phone, notaText(doc, kind, shopName)), "_blank", "noopener")} data-testid="nota-send-wa"><Send className="h-4 w-4" />Kirim via WhatsApp</Btn>}
    </div>
  );
}

export function ReturnsList({ returns }) {
  if (!returns?.length) return null;
  return (
    <Card title="Riwayat retur / pengembalian" data-testid="returns-list">
      {returns.map((r) => (
        <div key={r.id} className="border-b border-slate-100 py-2 text-sm">
          <b>{fmtDateTime(r.at)}</b> · {r.by} · refund {rp(r.refund)} ({r.refund_method}) · {r.reason}
          <div className="text-xs text-slate-600">{r.items.map((i) => `${i.name} x${i.qty} (${i.condition})`).join(", ") || "Tanpa barang kembali"}</div>
        </div>
      ))}
    </Card>
  );
}

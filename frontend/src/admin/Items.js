import { useState } from "react";
import { Plus } from "lucide-react";
import { api } from "@/lib/api";
import { rp } from "@/lib/fmt";
import { useAuth, isOwner } from "@/context/AuthContext";
import { Btn, Field, Input, NumInput, Select, Table, Td, PageHead, Modal, Badge } from "@/admin/ui";
import { useLoad, act } from "@/admin/tx";

const EMPTY = { sku: "", name: "", category: "", brand: "", variant: "", cost: 0, price: 0, active: true, min_stock: 0, warranty_days: 0, initial_stock: 0 };
const MODES = {
  in: ["Barang masuk (diterima di bengkel)", "/stock/in"], opname: ["Stok opname", "/stock/opname"], correction: ["Koreksi stok", "/stock/correction"],
  damage: ["Catat barang rusak", "/stock/damage"], internal: ["Pemakaian internal", "/stock/internal"],
};

function ItemForm({ item, onClose, onSaved }) {
  const { user } = useAuth();
  const [f, setF] = useState(item?.id ? { ...EMPTY, ...item } : EMPTY);
  const s = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const save = async () => {
    const body = { ...f, cost: Number(f.cost || 0), price: Number(f.price || 0), min_stock: Number(f.min_stock || 0), warranty_days: Number(f.warranty_days || 0), initial_stock: Number(f.initial_stock || 0) };
    const r = await act(() => (item?.id ? api.put(`/items/${item.id}`, body) : api.post("/items", body)), "Barang disimpan");
    if (r) { onSaved(); onClose(); }
  };
  return (
    <Modal open onClose={onClose} title={item?.id ? `Ubah ${item.name}` : "Barang baru"} wide>
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="Kode / SKU"><Input value={f.sku} onChange={s("sku")} data-testid="item-form-sku" /></Field>
        <Field label="Nama barang" className="sm:col-span-2"><Input value={f.name} onChange={s("name")} data-testid="item-form-name" /></Field>
        <Field label="Kategori"><Input value={f.category} onChange={s("category")} data-testid="item-form-category" /></Field>
        <Field label="Merek"><Input value={f.brand} onChange={s("brand")} data-testid="item-form-brand" /></Field>
        <Field label="Varian"><Input value={f.variant} onChange={s("variant")} data-testid="item-form-variant" /></Field>
        {isOwner(user) || !item?.id ? <Field label="Modal per pcs"><NumInput value={f.cost} onChange={(v) => setF({ ...f, cost: v })} data-testid="item-form-cost" /></Field> : <div />}
        <Field label="Harga jual per pcs"><NumInput value={f.price} onChange={(v) => setF({ ...f, price: v })} data-testid="item-form-price" /></Field>
        <Field label="Stok minimum"><NumInput value={f.min_stock} onChange={(v) => setF({ ...f, min_stock: v })} data-testid="item-form-minstock" /></Field>
        <Field label="Masa garansi (hari, 0 = tanpa)"><NumInput value={f.warranty_days} onChange={(v) => setF({ ...f, warranty_days: v })} data-testid="item-form-warranty" /></Field>
        {!item?.id && <Field label="Stok awal (pcs)"><NumInput value={f.initial_stock} onChange={(v) => setF({ ...f, initial_stock: v })} data-testid="item-form-initial-stock" /></Field>}
        <Field label="Status"><Select value={f.active ? "1" : "0"} onChange={(e) => setF({ ...f, active: e.target.value === "1" })} data-testid="item-form-active"><option value="1">Aktif</option><option value="0">Nonaktif</option></Select></Field>
      </div>
      <p className="text-xs text-slate-500">Stok hanya berubah melalui mutasi (barang masuk, opname, koreksi, transaksi). Satuan: pcs.</p>
      <Btn onClick={save} disabled={!f.sku || !f.name} data-testid="item-form-save">Simpan</Btn>
    </Modal>
  );
}

function StockForm({ item, mode, onClose, onSaved }) {
  const [f, setF] = useState({ qty: 1, counted: item.stock, delta: 0, reason: "", note: "" });
  const [title, url] = MODES[mode];
  const save = async () => {
    const body = { item_id: item.id, ...(mode === "in" ? { qty: Number(f.qty), note: f.note } : mode === "opname" ? { counted: Number(f.counted), note: f.note }
      : mode === "correction" ? { delta: Number(f.delta), reason: f.reason } : { qty: Number(f.qty), reason: f.reason }) };
    const r = await act(() => api.post(url, body), "Mutasi stok tercatat");
    if (r) { onSaved(); onClose(); }
  };
  const needReason = ["correction", "damage", "internal"].includes(mode);
  return (
    <Modal open onClose={onClose} title={`${title}: ${item.name}`}>
      <div className="space-y-3">
        <p className="text-sm">Stok saat ini: <b className="font-mono-num">{item.stock} pcs</b></p>
        {["in", "damage", "internal"].includes(mode) && <Field label="Jumlah (pcs)"><NumInput value={f.qty} onChange={(v) => setF({ ...f, qty: v })} min={1} data-testid="stock-form-qty" /></Field>}
        {mode === "opname" && <Field label="Hasil hitung fisik (pcs)"><NumInput value={f.counted} onChange={(v) => setF({ ...f, counted: v })} data-testid="stock-form-counted" /></Field>}
        {mode === "correction" && <Field label="Selisih (+ tambah / − kurang)"><Input type="number" value={f.delta} onChange={(e) => setF({ ...f, delta: e.target.value })} data-testid="stock-form-delta" /></Field>}
        {needReason ? <Field label="Alasan (wajib)"><Input value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} data-testid="stock-form-reason" /></Field>
          : <Field label="Catatan"><Input value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} data-testid="stock-form-note" /></Field>}
        <Btn onClick={save} disabled={needReason && f.reason.length < 3} data-testid="stock-form-save">Simpan</Btn>
      </div>
    </Modal>
  );
}

export default function Items() {
  const { user } = useAuth();
  const [q, setQ] = useState("");
  const [items, load] = useLoad(`/items?q=${encodeURIComponent(q)}`);
  const [form, setForm] = useState(null);
  const [stock, setStock] = useState(null);
  return (
    <div>
      <PageHead title="Master Barang" sub="Stok fisik bengkel saja (stok marketplace di rumah tidak dicatat di sini)." actions={<Btn onClick={() => setForm({})} data-testid="item-new-button"><Plus className="h-4 w-4" />Barang baru</Btn>} />
      <Input className="mb-4 max-w-sm" placeholder="Cari nama / SKU / merek…" value={q} onChange={(e) => setQ(e.target.value)} data-testid="items-search" />
      <Table head={["SKU", "Nama", "Kategori / Merek", isOwner(user) ? "Modal" : "", "Harga", "Stok", "Garansi", "Aksi"]} testid="items-table" empty={items && !items.length && "Belum ada barang."}>
        {(items || []).map((i) => (
          <tr key={i.id} className={!i.active ? "opacity-50" : ""} data-testid={`item-row-${i.sku}`}>
            <Td className="font-mono-num">{i.sku}</Td><Td><b>{i.name}</b><div className="text-xs text-slate-500">{i.variant}</div></Td>
            <Td>{i.category}<div className="text-xs text-slate-500">{i.brand}</div></Td>
            <Td className="font-mono-num">{isOwner(user) ? rp(i.cost) : ""}</Td><Td className="font-mono-num">{rp(i.price)}</Td>
            <Td><span className={`font-mono-num font-bold ${i.stock <= (i.min_stock || 0) ? "text-red-700" : ""}`} data-testid={`item-stock-${i.sku}`}>{i.stock}</span></Td>
            <Td>{i.warranty_days ? `${i.warranty_days} hari` : <Badge>Tanpa</Badge>}</Td>
            <Td className="whitespace-nowrap">
              <Select className="h-8 w-40 text-xs" value="" onChange={(e) => (e.target.value === "edit" ? setForm(i) : setStock({ item: i, mode: e.target.value }))} data-testid={`item-actions-${i.sku}`}>
                <option value="">Pilih aksi…</option><option value="edit">Ubah data</option>
                {Object.entries(MODES).map(([k, [l]]) => <option key={k} value={k}>{l}</option>)}
              </Select>
            </Td>
          </tr>
        ))}
      </Table>
      {form && <ItemForm item={form} onClose={() => setForm(null)} onSaved={load} />}
      {stock && <StockForm {...stock} onClose={() => setStock(null)} onSaved={load} />}
    </div>
  );
}

import { useState } from "react";
import { ChevronDown, ChevronRight, Download, Plus, Upload } from "lucide-react";
import { api } from "@/lib/api";
import { rp } from "@/lib/fmt";
import { useAuth, isOwner } from "@/context/AuthContext";
import { Btn, Field, Input, NumInput, Select, Table, Td, PageHead, Modal, Badge } from "@/admin/ui";
import { useLoad, act } from "@/admin/tx";
import { ImportDialog } from "@/admin/ItemImport";

const VAR = { sku: "", variant: "", cost: 0, price: 0, active: true, min_stock: 0, warranty_days: 0, initial_stock: 0 };
const MODES = {
  in: ["Barang masuk (diterima di bengkel)", "/stock/in"], opname: ["Stok opname", "/stock/opname"], correction: ["Koreksi stok", "/stock/correction"],
  damage: ["Catat barang rusak", "/stock/damage"], internal: ["Pemakaian internal", "/stock/internal"],
};
const nums = (v) => ({ ...v, cost: Number(v.cost || 0), price: Number(v.price || 0), min_stock: Number(v.min_stock || 0), warranty_days: Number(v.warranty_days || 0), initial_stock: Number(v.initial_stock || 0) });

function VariantFields({ v, set, showCost, isNew, i = "" }) {
  const n = (k) => (x) => set({ ...v, [k]: x });
  return (
    <div className="grid gap-2 sm:grid-cols-4">
      <Field label="Nama varian" hint="Kosong = Standar"><Input value={v.variant} onChange={(e) => set({ ...v, variant: e.target.value })} data-testid={`variant-name-${i}`} /></Field>
      <Field label="SKU"><Input value={v.sku} onChange={(e) => set({ ...v, sku: e.target.value })} data-testid={`variant-sku-${i}`} /></Field>
      <Field label="Harga jual"><NumInput value={v.price} onChange={n("price")} data-testid={`variant-price-${i}`} /></Field>
      {showCost ? <Field label="Modal"><NumInput value={v.cost} onChange={n("cost")} data-testid={`variant-cost-${i}`} /></Field> : <div />}
      <Field label="Stok minimum"><NumInput value={v.min_stock} onChange={n("min_stock")} data-testid={`variant-min-${i}`} /></Field>
      <Field label="Garansi (hari)"><NumInput value={v.warranty_days} onChange={n("warranty_days")} data-testid={`variant-warranty-${i}`} /></Field>
      {isNew && <Field label="Stok awal"><NumInput value={v.initial_stock} onChange={n("initial_stock")} data-testid={`variant-initial-${i}`} /></Field>}
      <Field label="Status"><Select value={v.active ? "1" : "0"} onChange={(e) => set({ ...v, active: e.target.value === "1" })} data-testid={`variant-active-${i}`}><option value="1">Aktif</option><option value="0">Nonaktif</option></Select></Field>
    </div>
  );
}

function ProductForm({ product, onClose, onSaved }) {
  const isNew = !product.id;
  const [f, setF] = useState(isNew ? { code: "", name: "", category: "", brand: "", active: true } : product);
  const [vars, setVars] = useState([{ ...VAR }]);
  const save = async () => {
    const body = { code: f.code, name: f.name, category: f.category, brand: f.brand, active: f.active };
    const r = await act(() => (isNew ? api.post("/products", { ...body, variants: vars.map(nums) }) : api.put(`/products/${product.id}`, body)), "Produk disimpan");
    if (r) { onSaved(); onClose(); }
  };
  return (
    <Modal open onClose={onClose} title={isNew ? "Produk baru" : `Ubah produk ${product.name}`} wide>
      <div className="grid gap-3 sm:grid-cols-4">
        <Field label="Kode produk" hint={isNew ? "Kosong = otomatis" : ""}><Input value={f.code} onChange={(e) => setF({ ...f, code: e.target.value })} data-testid="product-form-code" /></Field>
        <Field label="Nama produk" className="sm:col-span-3"><Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} data-testid="product-form-name" /></Field>
        <Field label="Kategori"><Input value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })} data-testid="product-form-category" /></Field>
        <Field label="Merek"><Input value={f.brand} onChange={(e) => setF({ ...f, brand: e.target.value })} data-testid="product-form-brand" /></Field>
        <Field label="Status"><Select value={f.active ? "1" : "0"} onChange={(e) => setF({ ...f, active: e.target.value === "1" })} data-testid="product-form-active"><option value="1">Aktif</option><option value="0">Nonaktif</option></Select></Field>
      </div>
      {isNew && (
        <div className="space-y-3">
          <p className="text-sm font-semibold">Varian fisik (masing-masing punya SKU & stok sendiri)</p>
          {vars.map((v, i) => (
            <div key={i} className="rounded-md border border-slate-200 p-3" data-testid={`product-form-variant-${i}`}>
              <VariantFields v={v} i={i} isNew showCost set={(x) => setVars(vars.map((y, k) => (k === i ? x : y)))} />
              {vars.length > 1 && <button className="mt-1 text-xs text-red-700" onClick={() => setVars(vars.filter((_, k) => k !== i))}>Hapus varian</button>}
            </div>
          ))}
          <Btn v="outline" size="sm" onClick={() => setVars([...vars, { ...VAR }])} data-testid="product-form-add-variant">+ Varian</Btn>
        </div>
      )}
      <Btn onClick={save} disabled={!f.name || (isNew && vars.some((v) => !v.sku))} data-testid="product-form-save">Simpan</Btn>
    </Modal>
  );
}

function VariantForm({ product, item, onClose, onSaved }) {
  const { user } = useAuth();
  const [v, setV] = useState(item ? { ...VAR, ...item } : { ...VAR });
  const save = async () => {
    const body = nums(v);
    if (item && !isOwner(user)) delete body.cost;
    const r = await act(() => (item ? api.put(`/items/${item.id}`, body) : api.post(`/products/${product.id}/variants`, body)), "Varian disimpan");
    if (r) { onSaved(); onClose(); }
  };
  return (
    <Modal open onClose={onClose} title={item ? `Ubah varian ${item.name}` : `Varian baru · ${product.name}`} wide>
      <VariantFields v={v} set={setV} isNew={!item} showCost={!item || isOwner(user)} i="edit" />
      <p className="text-xs text-slate-500">Stok hanya berubah melalui mutasi (barang masuk, opname, koreksi, transaksi). Satuan: pcs.</p>
      <Btn onClick={save} disabled={!v.sku} data-testid="variant-form-save">Simpan</Btn>
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
        <p className="text-sm">Stok varian <b>{item.sku}</b> saat ini: <b className="font-mono-num">{item.stock} pcs</b></p>
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

function VariantRow({ i, owner, setModal }) {
  return (
    <tr className={`bg-slate-50/60 ${!i.active ? "opacity-50" : ""}`} data-testid={`item-row-${i.sku}`}>
      <Td className="pl-10 font-mono-num">{i.sku}</Td><Td>{i.variant || <span className="text-slate-500">Standar</span>}</Td>
      <Td className="font-mono-num">{owner ? rp(i.cost) : ""}</Td><Td className="font-mono-num">{rp(i.price)}</Td>
      <Td><span className={`font-mono-num font-bold ${i.stock <= (i.min_stock || 0) ? "text-red-700" : ""}`} data-testid={`item-stock-${i.sku}`}>{i.stock}</span><span className="text-xs text-slate-500"> / min {i.min_stock || 0}</span></Td>
      <Td>{i.warranty_days ? `${i.warranty_days} hari` : <Badge>Tanpa</Badge>}</Td>
      <Td className="whitespace-nowrap">
        <Select className="h-8 w-40 text-xs" value="" onChange={(e) => setModal(e.target.value === "edit" ? { type: "variant", item: i } : { type: "stock", item: i, mode: e.target.value })} data-testid={`item-actions-${i.sku}`}>
          <option value="">Pilih aksi…</option><option value="edit">Ubah varian</option>
          {Object.entries(MODES).map(([k, [l]]) => <option key={k} value={k}>{l}</option>)}
        </Select>
      </Td>
    </tr>
  );
}

function ProductRows({ p, owner, open, toggle, setModal }) {
  return (
    <>
      <tr className={!p.active ? "opacity-50" : ""} data-testid={`product-row-${p.code}`}>
        <Td><button onClick={toggle} className="flex items-center gap-1 font-mono-num text-xs" data-testid={`product-toggle-${p.code}`}>{open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}{p.code}</button></Td>
        <Td><b>{p.name}</b><div className="text-xs text-slate-500">{[p.category, p.brand].filter(Boolean).join(" · ")}</div></Td>
        <Td colSpan={2} className="text-xs text-slate-600">{p.variants.length} varian</Td>
        <Td className="font-mono-num font-semibold">{p.stock_total}</Td><Td />
        <Td className="whitespace-nowrap space-x-1">
          <Btn size="sm" v="outline" onClick={() => setModal({ type: "product", product: p })} data-testid={`product-edit-${p.code}`}>Ubah</Btn>
          <Btn size="sm" v="outline" onClick={() => setModal({ type: "variant", product: p })} data-testid={`product-add-variant-${p.code}`}>+ Varian</Btn>
        </Td>
      </tr>
      {open && p.variants.map((i) => <VariantRow key={i.id} i={i} owner={owner} setModal={setModal} />)}
    </>
  );
}

export default function Items() {
  const { user } = useAuth();
  const owner = isOwner(user);
  const [q, setQ] = useState("");
  const [prods, load] = useLoad(`/products?q=${encodeURIComponent(q)}`);
  const [open, setOpen] = useState({});
  const [modal, setModal] = useState(null);
  const close = () => setModal(null);
  const template = async () => {
    const r = await api.get("/items/import/template", { responseType: "blob" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(r.data); a.download = "template-master-barang.xlsx"; a.click();
  };
  return (
    <div>
      <PageHead title="Master Barang" sub="Produk induk dengan varian fisik (SKU & stok per varian). Stok bengkel saja, bukan stok marketplace."
        actions={<>
          <Btn v="outline" onClick={template} data-testid="items-template-download"><Download className="h-4 w-4" />Unduh Template Excel (.xlsx)</Btn>
          <Btn v="outline" onClick={() => setModal({ type: "import" })} data-testid="items-import-button"><Upload className="h-4 w-4" />Impor Excel</Btn>
          <Btn onClick={() => setModal({ type: "product", product: {} })} data-testid="item-new-button"><Plus className="h-4 w-4" />Produk baru</Btn>
        </>} />
      <Input className="mb-4 max-w-sm" placeholder="Cari produk / varian / SKU / merek…" value={q} onChange={(e) => setQ(e.target.value)} data-testid="items-search" />
      <Table head={["Kode / SKU", "Produk / Varian", owner ? "Modal" : "", "Harga", "Stok", "Garansi", "Aksi"]} testid="items-table" empty={prods && !prods.length && "Belum ada barang."}>
        {(prods || []).map((p) => <ProductRows key={p.id} p={p} owner={owner} open={!!open[p.id] || !!q} toggle={() => setOpen({ ...open, [p.id]: !open[p.id] })} setModal={setModal} />)}
      </Table>
      {modal?.type === "product" && <ProductForm product={modal.product} onClose={close} onSaved={load} />}
      {modal?.type === "variant" && <VariantForm product={modal.product} item={modal.item} onClose={close} onSaved={load} />}
      {modal?.type === "stock" && <StockForm item={modal.item} mode={modal.mode} onClose={close} onSaved={load} />}
      {modal?.type === "import" && <ImportDialog onClose={close} onDone={load} />}
    </div>
  );
}

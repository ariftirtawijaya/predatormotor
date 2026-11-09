import { useState } from "react";
import { ChevronDown, ChevronRight, Download, Plus, Upload, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { rp } from "@/lib/fmt";
import { useAuth, isOwner } from "@/context/AuthContext";
import { Btn, Field, Input, NumInput, Select, Table, Td, PageHead, Modal, Badge } from "@/admin/ui";
import { useLoad, act } from "@/admin/tx";
import { ImportDialog } from "@/admin/ItemImport";
import { DeleteDialog } from "@/admin/DeleteDialog";

const VAR = { sku: "", variant: "", cost: 0, price: 0, active: true, min_stock: 0, warranty_days: 0, initial_stock: 0 };
const MODES = {
  in: ["Barang masuk (diterima di bengkel)", "/stock/in"], opname: ["Stok opname", "/stock/opname"], correction: ["Koreksi stok", "/stock/correction"],
  damage: ["Catat barang rusak", "/stock/damage"], internal: ["Pemakaian internal", "/stock/internal"],
};
const nums = (v) => ({ ...v, cost: Number(v.cost || 0), price: Number(v.price || 0), min_stock: Number(v.min_stock || 0), warranty_days: Number(v.warranty_days || 0), initial_stock: Number(v.initial_stock || 0) });

const Advanced = ({ children, testid }) => (
  <details className="rounded-md border border-dashed border-slate-300 px-3 py-2" data-testid={testid}>
    <summary className="cursor-pointer text-xs font-semibold text-slate-600">Detail lanjutan (SKU, modal, stok minimum, status)</summary>
    <div className="mt-2 grid gap-2 sm:grid-cols-4">{children}</div>
  </details>
);

function VariantFields({ v, set, showCost, isNew, i = "" }) {
  const n = (k) => (x) => set({ ...v, [k]: x });
  return (
    <div className="grid gap-2 sm:grid-cols-4">
      <Field label="Nama varian" hint="Mis. Merah, 2 warna"><Input value={v.variant} onChange={(e) => set({ ...v, variant: e.target.value })} data-testid={`variant-name-${i}`} /></Field>
      <Field label="SKU" hint={isNew ? "Kosong = otomatis" : ""}><Input value={v.sku} onChange={(e) => set({ ...v, sku: e.target.value })} data-testid={`variant-sku-${i}`} /></Field>
      <Field label="Harga jual"><NumInput value={v.price} onChange={n("price")} data-testid={`variant-price-${i}`} /></Field>
      {isNew ? <Field label="Stok awal"><NumInput value={v.initial_stock} onChange={n("initial_stock")} data-testid={`variant-initial-${i}`} /></Field> : <div />}
      {showCost && <Field label="Modal"><NumInput value={v.cost} onChange={n("cost")} data-testid={`variant-cost-${i}`} /></Field>}
      <Field label="Garansi (hari)"><NumInput value={v.warranty_days} onChange={n("warranty_days")} data-testid={`variant-warranty-${i}`} /></Field>
      <Field label="Stok minimum"><NumInput value={v.min_stock} onChange={n("min_stock")} data-testid={`variant-min-${i}`} /></Field>
      <Field label="Status"><Select value={v.active ? "1" : "0"} onChange={(e) => set({ ...v, active: e.target.value === "1" })} data-testid={`variant-active-${i}`}><option value="1">Aktif</option><option value="0">Nonaktif</option></Select></Field>
    </div>
  );
}

function SimpleFields({ m, set }) {
  const n = (k) => (x) => set({ ...m, [k]: x });
  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="Harga jual utama"><NumInput value={m.price} onChange={n("price")} data-testid="product-form-price" /></Field>
        <Field label="Stok awal (pcs)"><NumInput value={m.initial_stock} onChange={n("initial_stock")} data-testid="product-form-initial-stock" /></Field>
        <Field label="Garansi (hari)"><NumInput value={m.warranty_days} onChange={n("warranty_days")} data-testid="product-form-warranty" /></Field>
      </div>
      <Advanced testid="product-form-advanced">
        <Field label="SKU" hint="Kosong = dari kode produk"><Input value={m.sku} onChange={(e) => set({ ...m, sku: e.target.value })} data-testid="product-form-sku" /></Field>
        <Field label="Modal"><NumInput value={m.cost} onChange={n("cost")} data-testid="product-form-cost" /></Field>
        <Field label="Stok minimum"><NumInput value={m.min_stock} onChange={n("min_stock")} data-testid="product-form-min" /></Field>
      </Advanced>
    </div>
  );
}

function ProductForm({ product, onClose, onSaved }) {
  const isNew = !product.id;
  const [f, setF] = useState(isNew ? { code: "", name: "", category: "", brand: "", active: true } : product);
  const [m, setM] = useState({ ...VAR });
  const [vars, setVars] = useState([]);
  const addVar = () => setVars([...vars, { ...VAR, price: m.price, warranty_days: m.warranty_days, cost: m.cost }]);
  const save = async () => {
    const body = { code: f.code, name: f.name, category: f.category, brand: f.brand, active: f.active };
    const r = await act(() => (isNew ? api.post("/products", { ...body, ...nums(m), variants: vars.map(nums) }) : api.put(`/products/${product.id}`, body)), "Produk disimpan");
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
      {isNew && !vars.length && <SimpleFields m={m} set={setM} />}
      {isNew && !!vars.length && (
        <div className="space-y-3" data-testid="product-form-variants">
          <p className="text-sm font-semibold">Varian (masing-masing punya SKU, harga & stok sendiri)</p>
          {vars.map((v, i) => (
            <div key={i} className="rounded-md border border-slate-200 p-3" data-testid={`product-form-variant-${i}`}>
              <VariantFields v={v} i={i} isNew showCost set={(x) => setVars(vars.map((y, k) => (k === i ? x : y)))} />
              <button className="mt-1 text-xs text-red-700" onClick={() => setVars(vars.filter((_, k) => k !== i))} data-testid={`product-form-remove-variant-${i}`}>Hapus baris varian</button>
            </div>
          ))}
        </div>
      )}
      {isNew && <Btn v="outline" size="sm" className="w-fit" onClick={addVar} data-testid="product-form-add-variant"><Plus className="h-4 w-4" />Tambah Varian</Btn>}
      <Btn onClick={save} disabled={!f.name || vars.some((v) => !v.variant.trim())} data-testid="product-form-save">Simpan</Btn>
    </Modal>
  );
}

function VariantForm({ product, item, onClose, onSaved }) {
  const { user } = useAuth();
  const [v, setV] = useState(item ? { ...VAR, ...item } : { ...VAR, price: product?.variants?.[0]?.price || 0 });
  const [std, setStd] = useState("");
  const standard = !item && product?.simple ? product.variants[0] : null;
  const save = async () => {
    const body = nums(v);
    if (item && !isOwner(user)) delete body.cost;
    const r = await act(() => (item ? api.put(`/items/${item.id}`, body) : api.post(`/products/${product.id}/variants`, { ...body, standard_name: std })), "Varian disimpan");
    if (r) { onSaved(); onClose(); }
  };
  return (
    <Modal open onClose={onClose} title={item ? `Ubah varian ${item.name}` : `Tambah varian · ${product.name}`} wide>
      {standard && (
        <div className="rounded-md border border-sky-200 bg-sky-50 p-3 text-sm" data-testid="variant-form-standard">
          <p>Produk ini belum bervarian. Barang lama (SKU <b>{standard.sku}</b>, stok {standard.stock} pcs) akan menjadi <b>varian pertama</b> — ID, stok, paket & riwayat transaksinya tetap.</p>
          <Field label="Nama varian untuk barang lama" className="mt-2"><Input value={std} onChange={(e) => setStd(e.target.value)} placeholder="Mis. Merah" data-testid="variant-form-standard-name" /></Field>
        </div>
      )}
      <VariantFields v={v} set={setV} isNew={!item} showCost={!item || isOwner(user)} i="edit" />
      <p className="text-xs text-slate-500">Stok hanya berubah melalui mutasi (barang masuk, opname, koreksi, transaksi). Satuan: pcs.</p>
      <Btn onClick={save} disabled={(item ? !v.sku : !v.variant.trim()) || (standard && !std.trim())} data-testid="variant-form-save">Simpan</Btn>
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
        <p className="text-sm">Stok <b>{item.sku}</b> saat ini: <b className="font-mono-num">{item.stock} pcs</b></p>
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

function ItemActions({ i, owner, setModal, canDelete }) {
  const pick = (val) => {
    if (val === "edit") setModal({ type: "variant", item: i });
    else if (val === "delete") setModal({ type: "delete-item", item: i });
    else if (val === "toggle") setModal({ type: "toggle-item", item: i });
    else setModal({ type: "stock", item: i, mode: val });
  };
  return (
    <Select className="h-8 w-40 text-xs" value="" onChange={(e) => pick(e.target.value)} data-testid={`item-actions-${i.sku}`}>
      <option value="">Pilih aksi…</option><option value="edit">Ubah data barang</option>
      {Object.entries(MODES).map(([k, [l]]) => <option key={k} value={k}>{l}</option>)}
      {owner && <option value="toggle">{i.active ? "Nonaktifkan" : "Aktifkan"}</option>}
      {owner && canDelete && <option value="delete">Hapus varian</option>}
    </Select>
  );
}

function StockCell({ i }) {
  return <Td><span className={`font-mono-num font-bold ${i.stock <= (i.min_stock || 0) ? "text-red-700" : ""}`} data-testid={`item-stock-${i.sku}`}>{i.stock}</span><span className="text-xs text-slate-500"> / min {i.min_stock || 0}</span></Td>;
}

function VariantRow({ i, owner, setModal }) {
  return (
    <tr className={`bg-slate-50/60 ${!i.active ? "opacity-50" : ""}`} data-testid={`item-row-${i.sku}`}>
      <Td className="pl-10 font-mono-num">{i.sku}</Td><Td>{i.variant}</Td>
      <Td className="font-mono-num">{owner ? rp(i.cost) : ""}</Td><Td className="font-mono-num">{rp(i.price)}</Td>
      <StockCell i={i} /><Td>{i.warranty_days ? `${i.warranty_days} hari` : <Badge>Tanpa</Badge>}</Td>
      <Td className="whitespace-nowrap"><ItemActions i={i} owner={owner} setModal={setModal} canDelete /></Td>
    </tr>
  );
}

function ProductRows({ p, owner, open, toggle, setModal }) {
  const one = p.simple ? p.variants[0] : null;
  return (
    <>
      <tr className={!p.active ? "opacity-50" : ""} data-testid={`product-row-${p.code}`}>
        <Td>{one ? <span className="font-mono-num text-xs">{one.sku}</span> : (
          <button onClick={toggle} className="flex items-center gap-1 font-mono-num text-xs" data-testid={`product-toggle-${p.code}`}>{open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}{p.code}</button>)}</Td>
        <Td><b>{p.name}</b><div className="text-xs text-slate-500">{[p.category, p.brand].filter(Boolean).join(" · ")}{!p.active && " · Nonaktif"}</div></Td>
        {one ? <><Td className="font-mono-num">{owner ? rp(one.cost) : ""}</Td><Td className="font-mono-num">{rp(one.price)}</Td><StockCell i={one} />
          <Td>{one.warranty_days ? `${one.warranty_days} hari` : <Badge>Tanpa</Badge>}</Td></>
          : <><Td colSpan={2} className="text-xs text-slate-600">{p.variants.length} varian</Td><Td className="font-mono-num font-semibold">{p.stock_total}</Td><Td /></>}
        <Td className="whitespace-nowrap">
          <div className="flex flex-wrap items-center gap-1">
            {one && <ItemActions i={one} owner={owner} setModal={setModal} />}
            <Btn size="sm" v="outline" onClick={() => setModal({ type: "product", product: p })} data-testid={`product-edit-${p.code}`}>Ubah produk</Btn>
            <Btn size="sm" v="outline" onClick={() => setModal({ type: "variant", product: p })} data-testid={`product-add-variant-${p.code}`}><Plus className="h-3.5 w-3.5" />Varian</Btn>
            {owner && <Btn size="sm" v="ghost" className="text-red-700" onClick={() => setModal({ type: "delete-product", product: p })} data-testid={`product-delete-${p.code}`}><Trash2 className="h-3.5 w-3.5" />Hapus</Btn>}
          </div>
        </Td>
      </tr>
      {open && !one && p.variants.map((i) => <VariantRow key={i.id} i={i} owner={owner} setModal={setModal} />)}
    </>
  );
}

function ToggleItem({ item, onClose, onDone }) {
  const go = async () => { if (await act(() => api.post(`/items/${item.id}/active`, { active: !item.active }), item.active ? "Barang dinonaktifkan" : "Barang diaktifkan")) { onDone(); onClose(); } };
  return (
    <Modal open onClose={onClose} title={`${item.active ? "Nonaktifkan" : "Aktifkan"} ${item.name}?`}>
      <p className="text-sm text-slate-600">{item.active ? "Barang nonaktif tidak bisa dipilih di kasir, paket baru, atau pesanan baru. Stok dan riwayat tetap ada." : "Barang bisa dipilih lagi untuk transaksi baru."}</p>
      <Btn onClick={go} data-testid="item-toggle-confirm">{item.active ? "Nonaktifkan" : "Aktifkan"}</Btn>
    </Modal>
  );
}

function Modals({ modal, close, load }) {
  if (!modal) return null;
  const t = modal.type;
  if (t === "product") return <ProductForm product={modal.product} onClose={close} onSaved={load} />;
  if (t === "variant") return <VariantForm product={modal.product} item={modal.item} onClose={close} onSaved={load} />;
  if (t === "stock") return <StockForm item={modal.item} mode={modal.mode} onClose={close} onSaved={load} />;
  if (t === "import") return <ImportDialog onClose={close} onDone={load} />;
  if (t === "toggle-item") return <ToggleItem item={modal.item} onClose={close} onDone={load} />;
  if (t === "delete-item") return <DeleteDialog kind="item" id={modal.item.id} url={`/items/${modal.item.id}`} onClose={close} onDone={load}
    onDeactivate={modal.item.active ? () => api.post(`/items/${modal.item.id}/active`, { active: false }) : null} />;
  const p = modal.product;
  return <DeleteDialog kind="product" id={p.id} url={`/products/${p.id}`} onClose={close} onDone={load}
    onDeactivate={p.active ? () => api.post(`/products/${p.id}/active`, { active: false }) : null} />;
}

export default function Items() {
  const { user } = useAuth();
  const owner = isOwner(user);
  const [q, setQ] = useState("");
  const [prods, load] = useLoad(`/products?q=${encodeURIComponent(q)}`);
  const [open, setOpen] = useState({});
  const [modal, setModal] = useState(null);
  const template = async () => {
    const r = await api.get("/items/import/template", { responseType: "blob" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(r.data); a.download = "template-master-barang.xlsx"; a.click();
  };
  return (
    <div>
      <PageHead title="Master Barang" sub="Produk sederhana cukup satu harga & stok. Tambahkan varian (warna, ukuran, tipe) bila perlu — tiap varian punya SKU & stok sendiri."
        actions={<>
          <Btn v="outline" onClick={template} data-testid="items-template-download"><Download className="h-4 w-4" />Unduh Template Excel (.xlsx)</Btn>
          <Btn v="outline" onClick={() => setModal({ type: "import" })} data-testid="items-import-button"><Upload className="h-4 w-4" />Impor Excel</Btn>
          <Btn onClick={() => setModal({ type: "product", product: {} })} data-testid="item-new-button"><Plus className="h-4 w-4" />Produk baru</Btn>
        </>} />
      <Input className="mb-4 max-w-sm" placeholder="Cari produk / varian / SKU / merek…" value={q} onChange={(e) => setQ(e.target.value)} data-testid="items-search" />
      <Table head={["Kode / SKU", "Produk / Varian", owner ? "Modal" : "", "Harga", "Stok", "Garansi", "Aksi"]} testid="items-table" empty={prods && !prods.length && "Belum ada barang."}>
        {(prods || []).map((p) => <ProductRows key={p.id} p={p} owner={owner} open={!!open[p.id] || !!q} toggle={() => setOpen({ ...open, [p.id]: !open[p.id] })} setModal={setModal} />)}
      </Table>
      <Modals modal={modal} close={() => setModal(null)} load={load} />
    </div>
  );
}

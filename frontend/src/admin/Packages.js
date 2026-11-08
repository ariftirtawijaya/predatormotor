import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { rp } from "@/lib/fmt";
import { useAuth, isOwner } from "@/context/AuthContext";
import { Btn, Field, Input, Textarea, NumInput, Select, Card, PageHead, Modal, Badge } from "@/admin/ui";
import { useLoad, act } from "@/admin/tx";

function CompRows({ rows, set, items, testid }) {
  return (
    <div className="space-y-2">
      {rows.map((c, i) => (
        <div key={i} className="grid grid-cols-[1fr_80px_32px] gap-2">
          <Select value={c.item_id} onChange={(e) => set(rows.map((x, k) => (k === i ? { ...x, item_id: e.target.value } : x)))} data-testid={`${testid}-item-${i}`}>
            <option value="">Pilih barang…</option>{items.map((it) => <option key={it.id} value={it.id}>{it.name} ({it.sku})</option>)}
          </Select>
          <NumInput value={c.qty} min={1} onChange={(v) => set(rows.map((x, k) => (k === i ? { ...x, qty: v } : x)))} data-testid={`${testid}-qty-${i}`} />
          <button onClick={() => set(rows.filter((_, k) => k !== i))} className="text-red-700"><Trash2 className="h-4 w-4" /></button>
        </div>
      ))}
      <Btn v="outline" size="sm" onClick={() => set([...rows, { item_id: "", qty: 1 }])} data-testid={`${testid}-add`}>+ Komponen</Btn>
    </div>
  );
}

function PackageForm({ pkg, onClose, onSaved }) {
  const [items] = useLoad("/items");
  const [f, setF] = useState(pkg.id ? JSON.parse(JSON.stringify(pkg)) : { name: "", main_brand_model: "", description: "", price: 0, warranty_days: 0, active: true, components: [], options: [] });
  const clean = (r) => r.filter((c) => c.item_id).map((c) => ({ item_id: c.item_id, qty: Number(c.qty || 1) }));
  const save = async () => {
    const body = { ...f, price: Number(f.price || 0), warranty_days: Number(f.warranty_days || 0), components: clean(f.components),
      options: f.options.map((o) => ({ id: o.id, name: o.name, price: Number(o.price || 0), items: clean(o.items) })) };
    const r = await act(() => (pkg.id ? api.put(`/packages/${pkg.id}`, body) : api.post("/packages", body)), "Paket disimpan");
    if (r) { onSaved(); onClose(); }
  };
  return (
    <Modal open onClose={onClose} title={pkg.id ? `Ubah ${pkg.name}` : "Paket baru"} wide>
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Nama paket"><Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} data-testid="pkg-form-name" /></Field>
          <Field label="Merek / model barang utama"><Input value={f.main_brand_model} onChange={(e) => setF({ ...f, main_brand_model: e.target.value })} data-testid="pkg-form-brand" /></Field>
          <Field label="Harga paket (barang + jasa)"><NumInput value={f.price} onChange={(v) => setF({ ...f, price: v })} data-testid="pkg-form-price" /></Field>
          <Field label="Garansi paket (hari)"><NumInput value={f.warranty_days} onChange={(v) => setF({ ...f, warranty_days: v })} data-testid="pkg-form-warranty" /></Field>
          <Field label="Deskripsi" className="sm:col-span-2"><Textarea value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field>
        </div>
        <div><p className="mb-2 text-sm font-semibold">Komponen & jumlah pemakaian per paket</p>{items && <CompRows rows={f.components} set={(c) => setF({ ...f, components: c })} items={items} testid="pkg-comp" />}</div>
        <div>
          <p className="mb-2 text-sm font-semibold">Pilihan tambahan (mis. Shroud RGB)</p>
          {f.options.map((o, i) => (
            <div key={i} className="mb-3 rounded-md border border-slate-200 p-3">
              <div className="mb-2 grid grid-cols-[1fr_140px_32px] gap-2">
                <Input placeholder="Nama opsi" value={o.name} onChange={(e) => setF({ ...f, options: f.options.map((x, k) => (k === i ? { ...x, name: e.target.value } : x)) })} data-testid={`pkg-opt-name-${i}`} />
                <NumInput placeholder="Harga tambahan" value={o.price} onChange={(v) => setF({ ...f, options: f.options.map((x, k) => (k === i ? { ...x, price: v } : x)) })} data-testid={`pkg-opt-price-${i}`} />
                <button onClick={() => setF({ ...f, options: f.options.filter((_, k) => k !== i) })} className="text-red-700"><Trash2 className="h-4 w-4" /></button>
              </div>
              {items && <CompRows rows={o.items} set={(c) => setF({ ...f, options: f.options.map((x, k) => (k === i ? { ...x, items: c } : x)) })} items={items} testid={`pkg-opt-${i}`} />}
            </div>
          ))}
          <Btn v="outline" size="sm" onClick={() => setF({ ...f, options: [...f.options, { name: "", price: 0, items: [] }] })} data-testid="pkg-opt-add">+ Pilihan tambahan</Btn>
        </div>
        <Field label="Status"><Select value={f.active ? "1" : "0"} onChange={(e) => setF({ ...f, active: e.target.value === "1" })}><option value="1">Aktif</option><option value="0">Nonaktif</option></Select></Field>
        <Btn onClick={save} disabled={!f.name} data-testid="pkg-form-save">Simpan paket</Btn>
      </div>
    </Modal>
  );
}

export default function Packages() {
  const { user } = useAuth();
  const [pkgs, load] = useLoad("/packages");
  const [form, setForm] = useState(null);
  return (
    <div>
      <PageHead title="Paket Bengkel" sub="Harga paket sudah termasuk barang & jasa. Stok komponen berkurang saat nota Selesai. Paket di sini tidak otomatis tampil di website." actions={<Btn onClick={() => setForm({})} data-testid="pkg-new-button"><Plus className="h-4 w-4" />Paket baru</Btn>} />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {(pkgs || []).map((p) => (
          <Card key={p.id} title={p.name} actions={<><Badge>{p.active ? "Aktif" : "Nonaktif"}</Badge><Btn size="sm" v="outline" onClick={() => setForm(p)} data-testid={`pkg-edit-${p.id}`}>Ubah</Btn></>}>
            <p className="font-mono-num text-lg font-bold">{rp(p.price)}</p>
            <p className="text-sm text-slate-600">{p.main_brand_model} · garansi {p.warranty_days || 0} hari</p>
            {isOwner(user) && <p className="text-xs text-slate-500">Modal komponen: {rp(p.cost_total)}</p>}
            <ul className="mt-2 text-sm">{p.components.map((c, i) => <li key={i}>• {c.name} x{c.qty} <span className="text-xs text-slate-500">(stok {c.stock})</span></li>)}</ul>
            {p.options.map((o) => <p key={o.id} className="mt-1 text-sm text-sky-800">+ {o.name} ({rp(o.price)})</p>)}
          </Card>
        ))}
      </div>
      {form && <PackageForm pkg={form} onClose={() => setForm(null)} onSaved={load} />}
    </div>
  );
}

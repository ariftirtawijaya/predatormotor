import { useState } from "react";
import { Plus, Trash2, ArrowRightLeft, PackagePlus } from "lucide-react";
import { api } from "@/lib/api";
import { rp } from "@/lib/fmt";
import { useAuth, isOwner } from "@/context/AuthContext";
import { Btn, Field, Input, Textarea, NumInput, Select, Card, PageHead, Modal, Badge } from "@/admin/ui";
import { useLoad, act } from "@/admin/tx";
import { DeleteDialog } from "@/admin/DeleteDialog";

function CompRows({ rows, set, items, testid, addLabel = "+ Komponen" }) {
  return (
    <div className="space-y-2">
      {rows.map((c, i) => (
        <div key={i} className="grid grid-cols-[1fr_80px_32px] gap-2">
          <Select value={c.item_id} onChange={(e) => set(rows.map((x, k) => (k === i ? { ...x, item_id: e.target.value } : x)))} data-testid={`${testid}-item-${i}`}>
            <option value="">Pilih barang…</option>{items.map((it) => <option key={it.id} value={it.id}>{it.name} ({it.sku}){it.active ? "" : " — nonaktif"}</option>)}
          </Select>
          <NumInput value={c.qty} min={1} onChange={(v) => set(rows.map((x, k) => (k === i ? { ...x, qty: v } : x)))} data-testid={`${testid}-qty-${i}`} />
          <button onClick={() => set(rows.filter((_, k) => k !== i))} className="text-red-700" data-testid={`${testid}-remove-${i}`}><Trash2 className="h-4 w-4" /></button>
        </div>
      ))}
      <Btn v="outline" size="sm" onClick={() => set([...rows, { item_id: "", qty: 1 }])} data-testid={`${testid}-add`}>{addLabel}</Btn>
    </div>
  );
}

function OptionBox({ o, i, set, remove, items, base }) {
  const replace = o.mode === "replace";
  return (
    <div className={`rounded-md border p-3 ${replace ? "border-violet-200 bg-violet-50/40" : "border-emerald-200 bg-emerald-50/40"}`} data-testid={`pkg-opt-${i}`}>
      <div className="mb-2 flex items-center justify-between">
        <Badge>{replace ? "Ganti komponen / upgrade" : "Tambah barang"}</Badge>
        <button onClick={remove} className="text-red-700" data-testid={`pkg-opt-remove-${i}`}><Trash2 className="h-4 w-4" /></button>
      </div>
      <div className="mb-2 grid gap-2 sm:grid-cols-[1fr_170px]">
        <Field label="Nama opsi"><Input value={o.name} onChange={(e) => set({ ...o, name: e.target.value })} placeholder={replace ? "Mis. Upgrade Shroud RGB" : "Mis. Tambah Relay"} data-testid={`pkg-opt-name-${i}`} /></Field>
        <Field label={replace ? "Selisih harga" : "Harga tambahan"} hint={replace ? "Boleh minus bila lebih murah" : ""}>
          <Input type="number" value={o.price} onChange={(e) => set({ ...o, price: e.target.value === "" ? "" : Number(e.target.value) })} data-testid={`pkg-opt-price-${i}`} /></Field>
      </div>
      {replace && (
        <Field label="Komponen dasar yang diganti" className="mb-2">
          <Select value={o.replaces || ""} onChange={(e) => set({ ...o, replaces: e.target.value })} data-testid={`pkg-opt-replaces-${i}`}>
            <option value="">Pilih komponen dasar…</option>
            {base.filter((c) => c.item_id).map((c) => <option key={c.item_id} value={c.item_id}>{items.find((x) => x.id === c.item_id)?.name || c.item_id} x{c.qty}</option>)}
          </Select>
        </Field>
      )}
      <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-600">{replace ? "Diganti dengan" : "Barang yang ditambahkan"}</p>
      <CompRows rows={o.items} set={(c) => set({ ...o, items: c })} items={items} testid={`pkg-opt-${i}-comp`} addLabel="+ Barang" />
    </div>
  );
}

function Options({ f, setF, items }) {
  const [open, setOpen] = useState(f.options.length > 0);
  const add = (mode) => { setOpen(true); setF({ ...f, options: [...f.options, { name: "", price: 0, mode, replaces: "", items: [] }] }); };
  const setOpt = (i, o) => setF({ ...f, options: f.options.map((x, k) => (k === i ? o : x)) });
  return (
    <div className="rounded-md border border-slate-200 p-3" data-testid="pkg-options-section">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div><p className="text-sm font-semibold">Opsi Paket (opsional)</p>
          <p className="text-xs text-slate-500">Tambah barang di luar paket, atau ganti/upgrade komponen dasar dengan selisih harga. Opsi yang mengganti komponen yang sama tidak bisa dipilih bersamaan.</p></div>
        {!open && <Btn v="outline" size="sm" onClick={() => setOpen(true)} data-testid="pkg-options-open">+ Tambah opsi</Btn>}
      </div>
      {open && (
        <div className="mt-3 space-y-3">
          {f.options.map((o, i) => <OptionBox key={i} o={o} i={i} items={items} base={f.components} set={(x) => setOpt(i, x)} remove={() => setF({ ...f, options: f.options.filter((_, k) => k !== i) })} />)}
          <div className="flex flex-wrap gap-2">
            <Btn v="outline" size="sm" onClick={() => add("add")} data-testid="pkg-opt-add"><PackagePlus className="h-4 w-4" />Tambah barang</Btn>
            <Btn v="outline" size="sm" onClick={() => add("replace")} data-testid="pkg-opt-add-replace"><ArrowRightLeft className="h-4 w-4" />Ganti komponen / upgrade</Btn>
          </div>
        </div>
      )}
    </div>
  );
}

const EMPTY = { name: "", description: "", price: 0, warranty_days: 0, active: true, components: [], options: [] };

function PackageForm({ pkg, onClose, onSaved }) {
  const [items] = useLoad("/items");
  const [f, setF] = useState(pkg.id ? { ...JSON.parse(JSON.stringify(pkg)), options: pkg.options.map((o) => ({ ...o, mode: o.mode || "add" })) } : EMPTY);
  const clean = (r) => r.filter((c) => c.item_id).map((c) => ({ item_id: c.item_id, qty: Number(c.qty || 1) }));
  const save = async () => {
    const body = { name: f.name, description: f.description, active: f.active, price: Number(f.price || 0), warranty_days: Number(f.warranty_days || 0),
      components: clean(f.components),
      options: f.options.map((o) => ({ id: o.id, name: o.name, mode: o.mode, replaces: o.mode === "replace" ? o.replaces || null : null, price: Number(o.price || 0), items: clean(o.items) })) };
    const r = await act(() => (pkg.id ? api.put(`/packages/${pkg.id}`, body) : api.post("/packages", body)), "Paket disimpan");
    if (r) { onSaved(); onClose(); }
  };
  return (
    <Modal open onClose={onClose} title={pkg.id ? `Ubah ${pkg.name}` : "Paket baru"} wide>
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Nama paket" className="sm:col-span-3"><Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} data-testid="pkg-form-name" /></Field>
          <Field label="Harga paket (barang + jasa)"><NumInput value={f.price} onChange={(v) => setF({ ...f, price: v })} data-testid="pkg-form-price" /></Field>
          <Field label="Garansi paket (hari)"><NumInput value={f.warranty_days} onChange={(v) => setF({ ...f, warranty_days: v })} data-testid="pkg-form-warranty" /></Field>
          <Field label="Status"><Select value={f.active ? "1" : "0"} onChange={(e) => setF({ ...f, active: e.target.value === "1" })} data-testid="pkg-form-active"><option value="1">Aktif</option><option value="0">Nonaktif</option></Select></Field>
          <Field label="Deskripsi" className="sm:col-span-3"><Textarea value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} data-testid="pkg-form-description" /></Field>
        </div>
        <div><p className="mb-2 text-sm font-semibold">Komponen dasar & jumlah pemakaian per paket</p>{items && <CompRows rows={f.components} set={(c) => setF({ ...f, components: c })} items={items} testid="pkg-comp" />}</div>
        {items && <Options f={f} setF={setF} items={items} />}
        <Btn onClick={save} disabled={!f.name} data-testid="pkg-form-save">Simpan paket</Btn>
      </div>
    </Modal>
  );
}

function PackageCard({ p, owner, edit, del }) {
  return (
    <Card title={p.name} data-testid={`pkg-card-${p.id}`} actions={<><Badge>{p.active ? "Aktif" : "Nonaktif"}</Badge>
      <Btn size="sm" v="outline" onClick={edit} data-testid={`pkg-edit-${p.id}`}>Ubah</Btn>
      {owner && <Btn size="sm" v="ghost" className="text-red-700" onClick={del} data-testid={`pkg-delete-${p.id}`}><Trash2 className="h-3.5 w-3.5" />Hapus</Btn>}</>}>
      <p className="font-mono-num text-lg font-bold">{rp(p.price)}</p>
      <p className="text-sm text-slate-600">Garansi {p.warranty_days || 0} hari</p>
      {owner && <p className="text-xs text-slate-500">Modal komponen: {rp(p.cost_total)}</p>}
      <ul className="mt-2 text-sm">{p.components.map((c, i) => <li key={i}>• {c.name} x{c.qty} <span className="text-xs text-slate-500">(stok {c.stock})</span></li>)}</ul>
      {p.options.map((o) => (
        <p key={o.id} className="mt-1 text-sm text-sky-800" data-testid={`pkg-option-${o.id}`}>
          {o.mode === "replace" ? `⇄ ${o.name}: ${o.replaces_name || "?"} → ${o.items.map((c) => `${c.name} x${c.qty}`).join(", ")} (${o.price >= 0 ? "+" : ""}${rp(o.price)})`
            : `+ ${o.name}${o.items.length ? `: ${o.items.map((c) => `${c.name} x${c.qty}`).join(", ")}` : ""} (+${rp(o.price)})`}
        </p>
      ))}
    </Card>
  );
}

export default function Packages() {
  const { user } = useAuth();
  const owner = isOwner(user);
  const [pkgs, load] = useLoad("/packages");
  const [form, setForm] = useState(null);
  const [del, setDel] = useState(null);
  return (
    <div>
      <PageHead title="Paket Bengkel" sub="Harga paket sudah termasuk barang & jasa. Stok komponen yang benar-benar dipasang berkurang saat nota Selesai. Paket di sini tidak otomatis tampil di website." actions={<Btn onClick={() => setForm({})} data-testid="pkg-new-button"><Plus className="h-4 w-4" />Paket baru</Btn>} />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {(pkgs || []).map((p) => <PackageCard key={p.id} p={p} owner={owner} edit={() => setForm(p)} del={() => setDel(p)} />)}
      </div>
      {form && <PackageForm pkg={form} onClose={() => setForm(null)} onSaved={load} />}
      {del && <DeleteDialog kind="package" id={del.id} url={`/packages/${del.id}`} onClose={() => setDel(null)} onDone={load}
        onDeactivate={del.active ? () => api.post(`/packages/${del.id}/active`, { active: false }) : null} />}
    </div>
  );
}

import { useState } from "react";
import { ChevronUp, ChevronDown, Trash2, Plus, ChevronRight } from "lucide-react";
import { mediaUrl } from "@/lib/api";
import { Btn, Field, Input, Textarea, Select } from "@/admin/ui";
import { MediaPicker } from "@/admin/MediaLibrary";
import { SECTION_TYPES } from "@/admin/cmsSchema";
import { useLoad } from "@/admin/tx";

function ImageField({ value, onChange, tid }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="flex items-center gap-3">
      {value ? <img src={mediaUrl(value)} alt="" className="h-16 w-24 rounded border object-cover" /> : <div className="flex h-16 w-24 items-center justify-center rounded border border-dashed text-xs text-slate-400">kosong</div>}
      <Btn type="button" v="outline" size="sm" onClick={() => setOpen(true)} data-testid={`${tid}-pick`}>Pilih / unggah</Btn>
      {value && <Btn type="button" v="ghost" size="sm" onClick={() => onChange("")}>Hapus</Btn>}
      {open && <MediaPicker onClose={() => setOpen(false)} onPick={(m) => { onChange(m.url); setOpen(false); }} />}
    </div>
  );
}

const move = (arr, i, d) => { const a = [...arr]; const j = i + d; if (j < 0 || j >= a.length) return a; [a[i], a[j]] = [a[j], a[i]]; return a; };

function ListField({ f, value = [], onChange, ctx, tid }) {
  const [open, setOpen] = useState(-1);
  return (
    <div className="space-y-2">
      {f.hint && <p className="text-xs text-slate-500">{f.hint}</p>}
      {value.map((it, i) => (
        <div key={i} className="rounded-md border border-slate-200 bg-slate-50">
          <div className="flex items-center gap-2 px-3 py-2">
            <button type="button" onClick={() => setOpen(open === i ? -1 : i)} className="flex flex-1 items-center gap-1 text-left text-sm font-semibold" data-testid={`${tid}-item-${i}-toggle`}>
              <ChevronRight className={`h-4 w-4 transition-transform ${open === i ? "rotate-90" : ""}`} />{it[f.itemLabel] || `(item ${i + 1})`}
              {"visible" in it && !it.visible && <span className="ml-2 text-xs font-normal text-slate-500">· disembunyikan</span>}
            </button>
            {!f.fixed && <>
              <button type="button" onClick={() => onChange(move(value, i, -1))} data-testid={`${tid}-item-${i}-up`}><ChevronUp className="h-4 w-4" /></button>
              <button type="button" onClick={() => onChange(move(value, i, 1))} data-testid={`${tid}-item-${i}-down`}><ChevronDown className="h-4 w-4" /></button>
              <button type="button" onClick={() => window.confirm("Hapus item ini?") && onChange(value.filter((_, k) => k !== i))} className="text-red-700" data-testid={`${tid}-item-${i}-remove`}><Trash2 className="h-4 w-4" /></button>
            </>}
          </div>
          {open === i && <div className="border-t border-slate-200 bg-white p-3"><Fields fields={f.fields} value={it} onChange={(v) => onChange(value.map((x, k) => (k === i ? v : x)))} ctx={ctx} tid={`${tid}-item-${i}`} /></div>}
        </div>
      ))}
      {!f.fixed && <Btn type="button" v="outline" size="sm" onClick={() => { onChange([...value, {}]); setOpen(value.length); }} data-testid={`${tid}-add`}><Plus className="h-4 w-4" />Tambah</Btn>}
    </div>
  );
}

function SectionsField({ value = [], onChange, ctx }) {
  const [open, setOpen] = useState(-1);
  const [add, setAdd] = useState("");
  return (
    <div className="space-y-2" data-testid="cms-sections">
      {value.map((s, i) => {
        const def = SECTION_TYPES[s.type] || { label: s.type, fields: [] };
        return (
          <div key={i} className={`rounded-md border ${s.enabled ? "border-slate-300 bg-white" : "border-dashed border-slate-300 bg-slate-50"}`}>
            <div className="flex flex-wrap items-center gap-2 px-3 py-2">
              <span className="w-6 text-center font-mono-num text-xs text-slate-500">{i + 1}</span>
              <button type="button" onClick={() => setOpen(open === i ? -1 : i)} className="flex-1 text-left text-sm font-semibold" data-testid={`cms-section-${s.type}-toggle`}>{def.label}<span className="ml-2 font-normal text-slate-500">{s.title}</span></button>
              <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={!!s.enabled} onChange={(e) => onChange(value.map((x, k) => (k === i ? { ...x, enabled: e.target.checked } : x)))} data-testid={`cms-section-${s.type}-enabled`} />Tampil</label>
              <button type="button" onClick={() => onChange(move(value, i, -1))} data-testid={`cms-section-${s.type}-up`} aria-label="Naik"><ChevronUp className="h-4 w-4" /></button>
              <button type="button" onClick={() => onChange(move(value, i, 1))} data-testid={`cms-section-${s.type}-down`} aria-label="Turun"><ChevronDown className="h-4 w-4" /></button>
              <button type="button" onClick={() => window.confirm("Hapus bagian ini?") && onChange(value.filter((_, k) => k !== i))} className="text-red-700" data-testid={`cms-section-${s.type}-remove`}><Trash2 className="h-4 w-4" /></button>
            </div>
            {open === i && <div className="border-t border-slate-200 p-3">{def.hint && <p className="mb-2 text-xs text-slate-500">{def.hint}</p>}
              <Fields fields={def.fields} value={s} onChange={(v) => onChange(value.map((x, k) => (k === i ? v : x)))} ctx={ctx} tid={`cms-section-${s.type}`} /></div>}
          </div>
        );
      })}
      <div className="flex gap-2">
        <Select className="w-56" value={add} onChange={(e) => setAdd(e.target.value)} data-testid="cms-section-add-select"><option value="">Tambah bagian…</option>{Object.entries(SECTION_TYPES).map(([k, d]) => <option key={k} value={k}>{d.label}</option>)}</Select>
        <Btn type="button" v="outline" disabled={!add} onClick={() => { onChange([...value, { type: add, enabled: true, title: "", items: [] }]); setAdd(""); }} data-testid="cms-section-add">Tambah</Btn>
      </div>
    </div>
  );
}

export function Fields({ fields, value = {}, onChange, ctx, tid = "cms" }) {
  const set = (k, v) => onChange({ ...value, [k]: v });
  return (
    <div className="space-y-3">
      {fields.map((f) => {
        const id = `${tid}-${f.k}`;
        const v = value[f.k];
        let el;
        if (f.type === "text") el = <Input value={v || ""} onChange={(e) => set(f.k, e.target.value)} data-testid={id} />;
        else if (f.type === "readonly") el = <p className="text-sm font-semibold">{v}</p>;
        else if (f.type === "textarea") el = <Textarea rows={f.rows || 3} value={v || ""} onChange={(e) => set(f.k, e.target.value)} data-testid={id} />;
        else if (f.type === "number") el = <Input type="number" value={v ?? ""} onChange={(e) => set(f.k, e.target.value === "" ? null : Number(e.target.value))} data-testid={id} />;
        else if (f.type === "toggle") el = <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!v} onChange={(e) => set(f.k, e.target.checked)} data-testid={id} />{v ? "Ya" : "Tidak"}</label>;
        else if (f.type === "color") el = <div className="flex items-center gap-2"><input type="color" value={v || "#f59e0b"} onChange={(e) => set(f.k, e.target.value)} className="h-10 w-14 rounded border" data-testid={id} /><span className="font-mono-num text-sm">{v}</span></div>;
        else if (f.type === "select") el = <Select value={v || f.options[0][0]} onChange={(e) => set(f.k, e.target.value)} data-testid={id}>{f.options.map(([a, b]) => <option key={a} value={a}>{b}</option>)}</Select>;
        else if (f.type === "catref" || f.type === "albumref") { const opts = (f.type === "catref" ? ctx.categories : ctx.albums) || []; el = <Select value={v || ""} onChange={(e) => set(f.k, e.target.value)} data-testid={id}><option value="">—</option>{opts.map((o) => <option key={o.name} value={o.name}>{o.name}</option>)}</Select>; }
        else if (f.type === "itemref") el = <Select value={v || ""} onChange={(e) => set(f.k, e.target.value)} data-testid={id}><option value="">Tidak terhubung</option>{(ctx.items || []).map((i) => <option key={i.id} value={i.id}>{i.name} ({i.sku})</option>)}</Select>;
        else if (f.type === "image") el = <ImageField value={v} onChange={(x) => set(f.k, x)} tid={id} />;
        else if (f.type === "list") el = <ListField f={f} value={v} onChange={(x) => set(f.k, x)} ctx={ctx} tid={id} />;
        else if (f.type === "sections") el = <SectionsField value={v} onChange={(x) => set(f.k, x)} ctx={ctx} />;
        return <Field key={f.k} label={f.label} hint={f.type !== "list" ? f.hint : undefined}>{el}</Field>;
      })}
    </div>
  );
}

export function useCmsCtx(drafts) {
  const [items] = useLoad("/items");
  return { items, categories: drafts?.catalog?.categories, albums: drafts?.gallery?.albums };
}

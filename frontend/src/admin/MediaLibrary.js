import { useState } from "react";
import { Upload, Trash2 } from "lucide-react";
import { api, mediaUrl } from "@/lib/api";
import { Btn, Input, PageHead, Modal } from "@/admin/ui";
import { useLoad, act } from "@/admin/tx";

const MAX_MB = 5;

function Uploader({ onDone }) {
  const [busy, setBusy] = useState(false);
  const [alt, setAlt] = useState("");
  const up = async (e) => {
    const files = [...e.target.files];
    setBusy(true);
    for (const f of files) {
      if (f.size > MAX_MB * 1024 * 1024) { act(() => Promise.reject({ message: `${f.name} lebih dari ${MAX_MB} MB` })); continue; }
      const fd = new FormData();
      fd.append("file", f);
      fd.append("alt", alt);
      await act(() => api.post("/media", fd), `${f.name} diunggah`);
    }
    setBusy(false);
    e.target.value = "";
    onDone();
  };
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border border-dashed border-slate-300 bg-white p-3">
      <Upload className="h-5 w-5 text-slate-500" />
      <Input className="w-56" placeholder="Teks alternatif (deskripsi gambar)" value={alt} onChange={(e) => setAlt(e.target.value)} data-testid="media-alt-input" />
      <input type="file" accept="image/jpeg,image/png,image/webp,image/x-icon" multiple onChange={up} disabled={busy} className="text-sm" data-testid="media-upload-input" />
      <span className="text-xs text-slate-500">{busy ? "Mengunggah…" : `JPG/PNG/WEBP/ICO, maks ${MAX_MB} MB. Gambar diperkecil & metadata dibuang otomatis.`}</span>
    </div>
  );
}

function Grid({ list, onPick, onDelete, onAlt }) {
  return (
    <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
      {list.map((m) => (
        <div key={m.id} className="overflow-hidden rounded-md border border-slate-200 bg-white" data-testid={`media-item-${m.id}`}>
          <button type="button" onClick={() => onPick?.(m)} className="block w-full"><img src={mediaUrl(m.url)} alt={m.alt} className="aspect-square w-full object-cover" loading="lazy" /></button>
          <div className="space-y-1 p-2 text-xs">
            <p className="truncate text-slate-600">{m.original_name} · {m.width}×{m.height}</p>
            {onAlt && <input defaultValue={m.alt} placeholder="Teks alternatif" onBlur={(e) => e.target.value !== m.alt && onAlt(m, e.target.value)} className="w-full rounded border border-slate-200 px-1 py-0.5" />}
            {onDelete && <button onClick={() => onDelete(m)} className="flex items-center gap-1 text-red-700"><Trash2 className="h-3 w-3" />Hapus</button>}
            {onPick && <Btn size="sm" className="w-full" onClick={() => onPick(m)} data-testid={`media-pick-${m.id}`}>Pilih</Btn>}
          </div>
        </div>
      ))}
    </div>
  );
}

export function MediaPicker({ onPick, onClose }) {
  const [list, load] = useLoad("/media");
  return (
    <Modal open onClose={onClose} title="Pilih gambar" wide>
      <Uploader onDone={load} />
      <Grid list={list || []} onPick={onPick} />
    </Modal>
  );
}

export default function MediaLibrary() {
  const [list, load] = useLoad("/media");
  const del = async (m) => { if (window.confirm("Hapus gambar? Konten yang memakai gambar ini akan kehilangan gambarnya.")) { await act(() => api.delete(`/media/${m.id}`), "Dihapus"); load(); } };
  const alt = async (m, v) => { await act(() => api.patch(`/media/${m.id}`, { alt: v }), "Teks alternatif disimpan"); load(); };
  return (
    <div>
      <PageHead title="Media Library" sub="Gambar untuk website publik. Foto internal pelanggan tidak tampil di sini." />
      <Uploader onDone={load} />
      <Grid list={list || []} onDelete={del} onAlt={alt} />
    </div>
  );
}

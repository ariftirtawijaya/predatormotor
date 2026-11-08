import { useEffect, useState } from "react";
import { Eye, Save, Send, History, Undo2 } from "lucide-react";
import { api } from "@/lib/api";
import { fmtDateTime } from "@/lib/fmt";
import { Btn, PageHead, Modal, Badge } from "@/admin/ui";
import { act } from "@/admin/tx";
import { CMS_SCHEMA } from "@/admin/cmsSchema";
import { Fields, useCmsCtx } from "@/admin/SchemaForm";

function Revisions({ k, onClose, onRestored }) {
  const [rows, setRows] = useState(null);
  useEffect(() => { api.get(`/cms/${k}/revisions`).then((r) => setRows(r.data)); }, [k]);
  const restore = async (r) => { const x = await act(() => api.post(`/cms-revisions/${r.id}/restore`), "Dipulihkan ke draft — periksa lalu terbitkan"); if (x) { onRestored(x); onClose(); } };
  return (
    <Modal open onClose={onClose} title={`Riwayat: ${CMS_SCHEMA[k].label}`} wide>
      <div className="max-h-[60vh] space-y-1 overflow-y-auto text-sm" data-testid="cms-revisions">
        {(rows || []).map((r) => (
          <div key={r.id} className="flex items-center justify-between border-b border-slate-100 py-2">
            <span>{fmtDateTime(r.created_at)} · <b>{r.user_name}</b> · <Badge tone={r.kind === "publish" ? "Selesai" : "Baru"}>{r.kind === "publish" ? "diterbitkan" : "draft disimpan"}</Badge></span>
            <Btn size="sm" v="outline" onClick={() => restore(r)} data-testid={`cms-restore-${r.id}`}>Pulihkan ke draft</Btn>
          </div>
        ))}
        {rows && !rows.length && <p className="text-slate-500">Belum ada riwayat.</p>}
      </div>
    </Modal>
  );
}

export default function CMS() {
  const [docs, setDocs] = useState(null);
  const [key, setKey] = useState("home");
  const [local, setLocal] = useState({});
  const [rev, setRev] = useState(false);
  const [busy, setBusy] = useState(false);
  const load = () => api.get("/cms").then((r) => setDocs(Object.fromEntries(r.data.map((d) => [d.key, d]))));
  useEffect(() => { load(); }, []);
  const drafts = docs && Object.fromEntries(Object.entries(docs).map(([k, d]) => [k, local[k] || d.draft]));
  const ctx = useCmsCtx(drafts);
  if (!docs) return <p>Memuat…</p>;
  const doc = docs[key];
  const dirty = !!local[key];
  const upd = (d) => { setDocs({ ...docs, [d.key]: d }); setLocal((l) => { const n = { ...l }; delete n[d.key]; return n; }); };
  const save = async () => { setBusy(true); const r = await act(() => api.put(`/cms/${key}`, { data: drafts[key] }), "Draft disimpan (belum tampil ke pengunjung)"); setBusy(false); r && upd(r); return r; };
  const publish = async () => {
    if (dirty && !(await save())) return;
    if (!window.confirm("Terbitkan perubahan bagian ini ke website publik?")) return;
    const r = await act(() => api.post(`/cms/${key}/publish`), "Diterbitkan — tampil di website"); r && upd(r);
  };
  const preview = async () => { if (dirty && !(await save())) return; window.open("/?preview=1", "_blank"); };
  const discard = async () => { if (window.confirm("Buang draft dan kembali ke versi terbit?")) { const r = await act(() => api.post(`/cms/${key}/discard`), "Draft dibuang"); r && upd(r); } };
  return (
    <div>
      <PageHead title="CMS Website" sub="Ubah isi website publik. Simpan draft → pratinjau → terbitkan. Pengunjung hanya melihat versi terbit." />
      <div className="grid gap-4 lg:grid-cols-[240px_1fr]">
        <nav className="space-y-1" data-testid="cms-nav">
          {Object.entries(CMS_SCHEMA).map(([k, s]) => (
            <button key={k} onClick={() => setKey(k)} className={`flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm font-medium ${key === k ? "bg-sky-50 text-sky-900 ring-1 ring-sky-200" : "bg-white text-slate-700 hover:bg-slate-100"}`} data-testid={`cms-nav-${k}`}>
              {s.label}
              {(local[k] || docs[k].has_changes) && <span className="h-2 w-2 rounded-full bg-amber-500" title="Ada perubahan belum terbit" data-testid={`cms-dirty-${k}`} />}
            </button>
          ))}
        </nav>
        <div className="min-w-0 rounded-md border border-slate-200 bg-white">
          <div className="sticky top-14 z-10 flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-white px-4 py-3">
            <div>
              <h2 className="font-bold">{CMS_SCHEMA[key].label}</h2>
              <p className="text-xs text-slate-500" data-testid="cms-status">
                {dirty ? "Perubahan belum disimpan" : doc.has_changes ? "Draft tersimpan, belum diterbitkan" : "Sama dengan versi terbit"} · draft oleh {doc.updated_by} {fmtDateTime(doc.updated_at)} · terbit {fmtDateTime(doc.published_at)} oleh {doc.published_by}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Btn v="ghost" size="sm" onClick={() => setRev(true)} data-testid="cms-history"><History className="h-4 w-4" />Riwayat</Btn>
              {doc.has_changes && <Btn v="ghost" size="sm" onClick={discard} data-testid="cms-discard"><Undo2 className="h-4 w-4" />Buang draft</Btn>}
              <Btn v="outline" size="sm" onClick={save} disabled={!dirty || busy} data-testid="cms-save-draft"><Save className="h-4 w-4" />Simpan draft</Btn>
              <Btn v="outline" size="sm" onClick={preview} data-testid="cms-preview"><Eye className="h-4 w-4" />Pratinjau</Btn>
              <Btn size="sm" onClick={publish} disabled={!dirty && !doc.has_changes} data-testid="cms-publish"><Send className="h-4 w-4" />Terbitkan</Btn>
            </div>
          </div>
          <div className="p-4">
            <Fields key={key} fields={CMS_SCHEMA[key].fields} value={drafts[key]} onChange={(v) => setLocal({ ...local, [key]: v })} ctx={ctx} tid={`cms-${key}`} />
          </div>
        </div>
      </div>
      {rev && <Revisions k={key} onClose={() => setRev(false)} onRestored={upd} />}
    </div>
  );
}

import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Plus } from "lucide-react";
import { api, mediaUrl } from "@/lib/api";
import { rp, fmtDateTime } from "@/lib/fmt";
import { Btn, Field, Input, Textarea, Card, Table, Td, PageHead, Badge } from "@/admin/ui";
import { useLoad, act } from "@/admin/tx";

export function JobList() {
  const [status, setStatus] = useState("Masuk");
  const [q, setQ] = useState("");
  const [jobs] = useLoad(`/jobs?status=${status}&q=${encodeURIComponent(q)}`);
  return (
    <div>
      <PageHead title="Pekerjaan Bengkel" sub="Nota pekerjaan tersimpan di database — buka kembali kapan saja." actions={
        <Link to="/admin/pekerjaan/baru"><Btn data-testid="job-new-button"><Plus className="h-4 w-4" />Nota pekerjaan baru</Btn></Link>} />
      <div className="mb-4 flex flex-wrap gap-2">
        {["Masuk", "Selesai", "Batal", ""].map((s) => (
          <button key={s || "all"} onClick={() => setStatus(s)} className={`rounded-md px-3 py-1.5 text-sm font-semibold ${status === s ? "bg-slate-900 text-white" : "border border-slate-300 bg-white"}`} data-testid={`job-filter-${s || "semua"}`}>{s || "Semua"}</button>
        ))}
        <Input className="max-w-xs" placeholder="Cari no nota, plat, nama, WA…" value={q} onChange={(e) => setQ(e.target.value)} data-testid="job-search-input" />
      </div>
      <Table head={["No", "Tanggal", "Pelanggan", "Kendaraan", "Total", "Dibayar", "Status"]} testid="job-list-table" empty={jobs && !jobs.length && "Tidak ada nota."}>
        {(jobs || []).map((j) => (
          <tr key={j.id} className="hover:bg-slate-50">
            <Td><Link to={`/admin/pekerjaan/${j.id}`} className="font-semibold text-sky-800 hover:underline" data-testid={`job-link-${j.no}`}>{j.no}</Link>{j.kind === "garansi" && <div><Badge tone="Baru">Garansi</Badge></div>}</Td>
            <Td className="whitespace-nowrap">{fmtDateTime(j.created_at)}</Td>
            <Td>{j.customer.name}<div className="text-xs text-slate-500">{j.customer.phone}</div></Td>
            <Td>{j.vehicle ? <><b>{j.vehicle.plate}</b><div className="text-xs text-slate-500">{j.vehicle.brand} {j.vehicle.model}</div></> : "-"}</Td>
            <Td className="font-mono-num">{rp(j.total)}</Td>
            <Td className="font-mono-num">{rp(j.paid)}</Td>
            <Td><Badge>{j.status}</Badge></Td>
          </tr>
        ))}
      </Table>
    </div>
  );
}

export function PhotoUpload({ photos, setPhotos }) {
  const [busy, setBusy] = useState(false);
  const up = async (e) => {
    const files = [...e.target.files];
    setBusy(true);
    const urls = [];
    for (const f of files) {
      const fd = new FormData();
      fd.append("file", f);
      fd.append("private", "true");
      const r = await act(() => api.post("/media", fd));
      if (r) urls.push(r.url);
    }
    setPhotos([...photos, ...urls]);
    setBusy(false);
    e.target.value = "";
  };
  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {photos.map((p, i) => (
          <div key={i} className="relative"><img src={mediaUrl(p)} alt="foto" className="h-20 w-20 rounded-md border object-cover" />
            <button type="button" onClick={() => setPhotos(photos.filter((_, k) => k !== i))} className="absolute -right-1 -top-1 rounded-full bg-red-600 px-1.5 text-xs text-white">×</button></div>
        ))}
      </div>
      <input type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={up} disabled={busy} className="mt-2 text-sm" data-testid="photo-upload-input" />
      {busy && <span className="text-xs text-slate-500"> mengunggah…</span>}
    </div>
  );
}

export function JobNew() {
  const nav = useNavigate();
  const [sp] = useSearchParams();
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);
  const [sel, setSel] = useState(null);
  const [cust, setCust] = useState({ name: "", phone: "" });
  const [veh, setVeh] = useState({ plate: "", brand: "", model: "" });
  const [f, setF] = useState({ complaint: "", notes: "" });
  const [photos, setPhotos] = useState([]);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const vid = sp.get("vehicle");
    if (vid) api.get(`/vehicles/${vid}/history`).then((r) => setSel({ vehicle: r.data.vehicle, customer: r.data.customer }));
  }, [sp]);
  useEffect(() => {
    if (q.length < 2) { setResults([]); return; }
    const t = setTimeout(() => api.get(`/search?q=${encodeURIComponent(q)}`).then((r) => setResults(r.data)), 250);
    return () => clearTimeout(t);
  }, [q]);
  const submit = async () => {
    setBusy(true);
    const body = { complaint: f.complaint, notes: f.notes, photos,
      customer: sel ? { id: sel.customer.id } : cust,
      vehicle: sel?.vehicle ? { id: sel.vehicle.id } : veh.plate ? veh : null };
    const r = await act(() => api.post("/jobs", body), "Nota pekerjaan dibuat");
    setBusy(false);
    if (r) nav(`/admin/pekerjaan/${r.id}`);
  };
  return (
    <div className="max-w-3xl">
      <PageHead title="Nota Pekerjaan Baru" sub="Buat nota ketika pelanggan sudah cocok dengan harga. Barang/paket ditambahkan setelah nota tersimpan." />
      <Card title="Pelanggan & kendaraan" className="mb-4">
        {sel ? (
          <div className="flex items-center justify-between rounded-md bg-sky-50 p-3 text-sm" data-testid="job-selected-vehicle">
            <span><b>{sel.vehicle?.plate || "Tanpa kendaraan"}</b> {sel.vehicle?.brand} {sel.vehicle?.model} · {sel.customer?.name} {sel.customer?.phone}</span>
            <Btn v="outline" size="sm" onClick={() => setSel(null)}>Ganti</Btn>
          </div>
        ) : (
          <div className="space-y-3">
            <Field label="Cari pelanggan lama (plat / nama / WA)"><Input value={q} onChange={(e) => setQ(e.target.value)} data-testid="job-customer-search" /></Field>
            {results.map((r, i) => (
              <button key={i} onClick={() => setSel(r)} className="block w-full rounded-md border border-slate-200 p-2 text-left text-sm hover:bg-sky-50" data-testid={`job-search-result-${i}`}>
                <b>{r.vehicle?.plate || "—"}</b> {r.vehicle?.brand} {r.vehicle?.model} · {r.customer?.name} · {r.customer?.phone}
              </button>
            ))}
            <p className="pt-2 text-xs font-semibold uppercase text-slate-500">atau pelanggan baru</p>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Nama pelanggan"><Input value={cust.name} onChange={(e) => setCust({ ...cust, name: e.target.value })} data-testid="job-customer-name" /></Field>
              <Field label="No WhatsApp"><Input value={cust.phone} onChange={(e) => setCust({ ...cust, phone: e.target.value })} data-testid="job-customer-phone" /></Field>
              <Field label="Plat nomor"><Input value={veh.plate} onChange={(e) => setVeh({ ...veh, plate: e.target.value })} data-testid="job-vehicle-plate" /></Field>
              <Field label="Merek"><Input value={veh.brand} onChange={(e) => setVeh({ ...veh, brand: e.target.value })} data-testid="job-vehicle-brand" /></Field>
              <Field label="Tipe / model" className="sm:col-span-2"><Input value={veh.model} onChange={(e) => setVeh({ ...veh, model: e.target.value })} data-testid="job-vehicle-model" /></Field>
            </div>
          </div>
        )}
      </Card>
      <Card title="Keluhan & catatan" className="mb-4">
        <div className="space-y-3">
          <Field label="Keluhan"><Textarea value={f.complaint} onChange={(e) => setF({ ...f, complaint: e.target.value })} data-testid="job-complaint-input" /></Field>
          <Field label="Catatan"><Textarea value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} data-testid="job-notes-input" /></Field>
          <Field label="Foto kendaraan (internal, tidak tampil publik)"><PhotoUpload photos={photos} setPhotos={setPhotos} /></Field>
        </div>
      </Card>
      <Btn onClick={submit} disabled={busy || (!sel && !cust.name)} data-testid="job-create-submit">Simpan nota (status Masuk)</Btn>
    </div>
  );
}

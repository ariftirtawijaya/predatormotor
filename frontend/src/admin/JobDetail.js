import { useState } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { CheckCircle2 } from "lucide-react";
import { api, mediaUrl } from "@/lib/api";
import { rp, fmtDateTime, fmtDate } from "@/lib/fmt";
import { useAuth, isManager, isOwner } from "@/context/AuthContext";
import { Btn, Field, Input, Textarea, Select, NumInput, Card, PageHead, Badge, Modal } from "@/admin/ui";
import { useLoad, act, LinePicker, LinesTable, Totals, PaymentBox, PaymentsList, DiscountBox, ReturnDialog, NotaActions, ReturnsList } from "@/admin/tx";
import { PhotoUpload } from "@/admin/Jobs";

function ClaimPanel({ job, setJob }) {
  const c = job.claim;
  const [f, setF] = useState({ inspection: c.inspection, action: c.action, technician: c.technician, claim_notes: c.claim_notes,
    old_part: c.old_part || { name: c.line_name, qty: 1, condition: "rusak" } });
  const open = job.status === "Masuk";
  const save = async () => { const r = await act(() => api.patch(`/jobs/${job.id}`, { claim: f }), "Data klaim disimpan"); r && setJob(r); };
  return (
    <Card title={`Klaim garansi #${c.claim_seq} — ${c.line_name}`} className="mb-4" data-testid="claim-panel">
      <p className="mb-3 text-sm">Nota awal: <Link className="font-semibold text-sky-800 underline" to={`/admin/${c.ref_type === "job" ? "pekerjaan" : c.ref_type === "sale" ? "penjualan" : "pesanan"}/${c.ref_id}`} data-testid="claim-original-link">{c.ref_no}</Link>
        {" · "}Garansi s/d {c.warranty_until ? fmtDate(c.warranty_until) : "-"} · <b className={c.in_warranty ? "text-emerald-700" : "text-red-700"}>{c.in_warranty ? "Dalam masa garansi" : "Di luar masa garansi"}</b></p>
      <p className="mb-3 text-sm">Gejala: {c.symptom}</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Hasil pemeriksaan"><Textarea disabled={!open} value={f.inspection} onChange={(e) => setF({ ...f, inspection: e.target.value })} data-testid="claim-inspection" /></Field>
        <Field label="Tindakan">
          <Select disabled={!open} value={f.action} onChange={(e) => setF({ ...f, action: e.target.value })} data-testid="claim-action">
            <option value="">Pilih…</option><option value="perbaikan">Perbaikan (tanpa ganti barang)</option><option value="penggantian">Penggantian barang</option><option value="ditolak">Klaim ditolak</option>
          </Select>
        </Field>
        <Field label="Petugas"><Input disabled={!open} value={f.technician} onChange={(e) => setF({ ...f, technician: e.target.value })} data-testid="claim-technician" /></Field>
        <Field label="Catatan / biaya"><Input disabled={!open} value={f.claim_notes} onChange={(e) => setF({ ...f, claim_notes: e.target.value })} data-testid="claim-notes" /></Field>
      </div>
      {f.action === "penggantian" && (
        <div className="mt-3 grid gap-2 rounded-md bg-slate-50 p-3 sm:grid-cols-3">
          <Field label="Barang lama yang dilepas"><Input disabled={!open} value={f.old_part.name} onChange={(e) => setF({ ...f, old_part: { ...f.old_part, name: e.target.value } })} data-testid="claim-oldpart-name" /></Field>
          <Field label="Jumlah"><NumInput disabled={!open} value={f.old_part.qty} onChange={(v) => setF({ ...f, old_part: { ...f.old_part, qty: v } })} /></Field>
          <Field label="Kondisi fisik"><Select disabled={!open} value={f.old_part.condition} onChange={(e) => setF({ ...f, old_part: { ...f.old_part, condition: e.target.value } })} data-testid="claim-oldpart-condition">
            <option value="rusak">Rusak → catat barang rusak</option><option value="dibuang">Tidak dicatat</option></Select></Field>
          <p className="text-xs text-slate-600 sm:col-span-3">Tambahkan barang pengganti di bagian “Tambah barang” dengan centang “Pengganti garansi”. Stok berkurang saat nota Selesai. Perbaikan tanpa penggantian tidak mengurangi stok.</p>
        </div>
      )}
      {open && <Btn size="sm" className="mt-3" onClick={save} data-testid="claim-save">Simpan data klaim</Btn>}
    </Card>
  );
}

function EditLineModal({ line, job, onClose, setJob }) {
  const [f, setF] = useState({ qty: line?.qty, unit_price: line?.unit_price, reason: "" });
  if (!line) return null;
  const save = async () => { const r = await act(() => api.put(`/jobs/${job.id}/lines/${line.lid}`, f), "Baris diubah (tercatat di audit)"); if (r) { setJob(r); onClose(); } };
  return (
    <Modal open onClose={onClose} title={`Ubah ${line.name}`}>
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-2"><Field label="Qty"><NumInput value={f.qty} onChange={(v) => setF({ ...f, qty: v })} data-testid="edit-line-qty" /></Field>
          <Field label="Harga satuan"><NumInput value={f.unit_price} onChange={(v) => setF({ ...f, unit_price: v })} data-testid="edit-line-price" /></Field></div>
        <Field label="Alasan perubahan (wajib)"><Input value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} data-testid="edit-line-reason" /></Field>
        <Btn disabled={f.reason.length < 3} onClick={save} data-testid="edit-line-save">Simpan</Btn>
      </div>
    </Modal>
  );
}

export function ClaimStart({ job, onClose, kind = "job" }) {
  const nav = useNavigate();
  const [lid, setLid] = useState("");
  const [symptom, setSymptom] = useState("");
  const lines = job.lines.filter((l) => !l.removed && l.type !== "service");
  const go = async () => { const r = await act(() => api.post("/claims", { ref_type: kind, ref_id: job.id, line_lid: lid, symptom }), "Nota garansi dibuat"); if (r) nav(`/admin/pekerjaan/${r.id}`); };
  return (
    <Modal open onClose={onClose} title="Klaim garansi baru">
      <div className="space-y-3">
        <Field label="Barang bermasalah"><Select value={lid} onChange={(e) => setLid(e.target.value)} data-testid="claim-line-select">
          <option value="">Pilih item nota…</option>
          {lines.map((l) => <option key={l.lid} value={l.lid}>{l.name} {l.warranty_until ? `(garansi s/d ${fmtDate(l.warranty_until)})` : "(tanpa garansi)"}</option>)}
        </Select></Field>
        <Field label="Gejala kerusakan"><Textarea value={symptom} onChange={(e) => setSymptom(e.target.value)} data-testid="claim-symptom" /></Field>
        <Btn disabled={!lid || symptom.length < 2} onClick={go} data-testid="claim-create-submit">Buat nota garansi</Btn>
      </div>
    </Modal>
  );
}

export default function JobDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const [job, , setJob] = useLoad(`/jobs/${id}`);
  const [site] = useLoad("/public/site");
  const [edit, setEdit] = useState(null);
  const [modal, setModal] = useState("");
  const [busy, setBusy] = useState(false);
  const [info, setInfo] = useState(null);
  if (!job) return <p>Memuat…</p>;
  const open = job.status === "Masuk";
  const inf = info || { complaint: job.complaint, notes: job.notes, photos: job.photos };
  const addLine = async (l) => { setBusy(true); const r = await act(() => api.post(`/jobs/${id}/lines`, l), "Ditambahkan"); setBusy(false); r && setJob(r); };
  const remove = async (l) => { const reason = window.prompt(`Alasan menghapus ${l.name}?`); if (reason) { const r = await act(() => api.post(`/jobs/${id}/lines/${l.lid}/remove`, { reason }), "Baris dibatalkan"); r && setJob(r); } };
  const complete = async () => { if (!window.confirm("Tandai pekerjaan Selesai? Stok barang akan dikurangi.")) return; setBusy(true); const r = await act(() => api.post(`/jobs/${id}/complete`), "Pekerjaan Selesai"); setBusy(false); r && setJob(r); };
  const saveInfo = async () => { const r = await act(() => api.patch(`/jobs/${id}`, inf), "Disimpan"); if (r) { setJob(r); setInfo(null); } };
  return (
    <div>
      <PageHead title={<span data-testid="job-no">{job.no}</span>} sub={`${job.kind === "garansi" ? "Nota garansi" : "Nota pekerjaan"} · dibuat ${fmtDateTime(job.created_at)} oleh ${job.created_by}`}
        actions={<><Badge data-testid="job-status">{job.status}</Badge><NotaActions kind="job" doc={job} shopName={site?.identity?.name} /></>} />
      <div className="grid gap-4 xl:grid-cols-[1fr_380px]">
        <div className="min-w-0 space-y-4">
          <Card title="Pelanggan & kendaraan">
            <div className="text-sm">
              <p><b>{job.customer.name}</b> · {job.customer.phone || "tanpa WA"}</p>
              {job.vehicle && <p><Link to={`/admin/kendaraan/${job.vehicle_id}`} className="font-semibold text-sky-800 underline" data-testid="job-vehicle-history-link">{job.vehicle.plate}</Link> {job.vehicle.brand} {job.vehicle.model} — lihat riwayat</p>}
            </div>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <Field label="Keluhan"><Textarea disabled={!open} value={inf.complaint} onChange={(e) => setInfo({ ...inf, complaint: e.target.value })} data-testid="job-detail-complaint" /></Field>
              <Field label="Catatan"><Textarea disabled={!open} value={inf.notes} onChange={(e) => setInfo({ ...inf, notes: e.target.value })} data-testid="job-detail-notes" /></Field>
            </div>
            {open ? <div className="mt-2"><PhotoUpload photos={inf.photos} setPhotos={(p) => setInfo({ ...inf, photos: p })} /></div>
              : <div className="mt-2 flex gap-2">{job.photos.map((p, i) => <img key={i} src={mediaUrl(p)} alt="" className="h-20 w-20 rounded border object-cover" />)}</div>}
            {open && info && <Btn size="sm" className="mt-3" onClick={saveInfo} data-testid="job-info-save">Simpan perubahan</Btn>}
          </Card>
          {job.kind === "garansi" && <ClaimPanel job={job} setJob={setJob} />}
          <Card title="Rincian nota">
            <LinesTable doc={job} onEdit={open ? setEdit : null} onRemove={remove} />
          </Card>
          {open && <Card title="Tambah barang / paket / jasa"><LinePicker onAdd={addLine} garansi={job.kind === "garansi"} busy={busy} /></Card>}
          {!!job.claims?.length && (
            <Card title="Klaim garansi terkait nota ini" data-testid="job-claims">
              {job.claims.map((c) => <p key={c.id} className="text-sm"><Link className="font-semibold text-sky-800 underline" to={`/admin/pekerjaan/${c.id}`}>{c.no}</Link> · {fmtDate(c.date_local)} · {c.claim.line_name} · klaim ke-{c.claim.claim_seq} · {c.claim.action || "belum ada tindakan"} · {c.status}</p>)}
            </Card>
          )}
          <ReturnsList returns={job.returns} />
        </div>
        <div className="space-y-4">
          <Card title="Total"><Totals doc={job} /></Card>
          {open && (
            <Btn v="success" className="h-12 w-full text-base" disabled={busy} onClick={complete} data-testid="job-complete-button"><CheckCircle2 className="h-5 w-5" />Tandai Selesai</Btn>
          )}
          <Card title="Diskon"><DiscountBox kind="job" doc={job} onDone={setJob} editable={open} /></Card>
          {job.status !== "Batal" && <Card title={open ? "Pembayaran / DP" : "Pelunasan"}><PaymentBox kind="job" doc={job} onDone={setJob} /></Card>}
          <Card title="Riwayat pembayaran"><PaymentsList payments={job.payments} /></Card>
          <div className="flex flex-wrap gap-2">
            {job.status === "Selesai" && job.kind === "servis" && <Btn v="outline" onClick={() => setModal("claim")} data-testid="job-claim-button">Klaim garansi</Btn>}
            {job.status === "Selesai" && isManager(user) && <Btn v="outline" onClick={() => setModal("return")} data-testid="job-return-button">Retur / refund</Btn>}
            {open && isOwner(user) && <Btn v="danger" onClick={() => setModal("cancel")} data-testid="job-cancel-button">Batalkan nota</Btn>}
          </div>
          {job.cancel && <Card title="Pembatalan"><p className="text-sm" data-testid="job-cancel-info">{fmtDateTime(job.cancel.at)} oleh {job.cancel.by}: {job.cancel.reason}<br />Dikembalikan {rp(job.cancel.refund)} · DP ditahan {rp(job.cancel.kept)}</p></Card>}
        </div>
      </div>
      <EditLineModal key={edit?.lid} line={edit} job={job} onClose={() => setEdit(null)} setJob={setJob} />
      {modal === "claim" && <ClaimStart job={job} onClose={() => setModal("")} />}
      {modal === "return" && <ReturnDialog kind="job" doc={job} open onClose={() => setModal("")} onDone={setJob} />}
      {modal === "cancel" && <ReturnDialog kind="job" doc={job} open onClose={() => setModal("")} onDone={setJob} title="Batalkan nota (keputusan owner)" endpoint={`/jobs/${id}/cancel`}
        extra={<p className="rounded-md bg-amber-50 p-3 text-sm text-amber-900">Tentukan jumlah DP yang dikembalikan per kasus. Sisa DP yang tidak dikembalikan tercatat sebagai DP ditahan. Nota tidak dihapus.</p>} />}
    </div>
  );
}

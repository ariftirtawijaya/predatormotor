import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Plus } from "lucide-react";
import { api } from "@/lib/api";
import { rp, fmtDateTime, fmtDate } from "@/lib/fmt";
import { Btn, Input, Card, PageHead, Badge } from "@/admin/ui";
import { useLoad } from "@/admin/tx";

export function VehicleSearch() {
  const [q, setQ] = useState("");
  const [res, setRes] = useState([]);
  useEffect(() => {
    if (q.length < 2) { setRes([]); return; }
    const t = setTimeout(() => api.get(`/search?q=${encodeURIComponent(q)}`).then((r) => setRes(r.data)), 250);
    return () => clearTimeout(t);
  }, [q]);
  return (
    <div className="max-w-3xl">
      <PageHead title="Riwayat Kendaraan" sub="Cari berdasarkan plat, nama, atau nomor WhatsApp." />
      <Input autoFocus className="h-12 text-base" placeholder="Contoh: S 1234 AB / Budi / 0812…" value={q} onChange={(e) => setQ(e.target.value)} data-testid="vehicle-search-input" />
      <div className="mt-4 space-y-2">
        {res.map((r, i) => (
          r.vehicle ? (
            <Link key={i} to={`/admin/kendaraan/${r.vehicle.id}`} className="block rounded-md border border-slate-200 bg-white p-3 hover:border-sky-400" data-testid={`vehicle-result-${i}`}>
              <p className="font-mono-num text-lg font-bold">{r.vehicle.plate}</p>
              <p className="text-sm text-slate-600">{r.vehicle.brand} {r.vehicle.model} · {r.customer?.name} · {r.customer?.phone}</p>
            </Link>
          ) : (
            <Link key={i} to={`/admin/pelanggan/${r.customer.id}`} className="block rounded-md border border-slate-200 bg-white p-3 text-sm hover:border-sky-400" data-testid={`customer-result-${i}`}>{r.customer.name} · {r.customer.phone} <span className="text-slate-500">(tanpa kendaraan terdaftar)</span></Link>
          )
        ))}
        {q.length >= 2 && !res.length && <p className="text-sm text-slate-500">Tidak ditemukan.</p>}
      </div>
    </div>
  );
}

export function CustomerHistory() {
  const { id } = useParams();
  const [h] = useLoad(`/customers/${id}/history`);
  if (!h) return <p>Memuat…</p>;
  const { customer: c, vehicles, jobs, sales, orders } = h;
  const Row = ({ to, no, at, total, extra }) => <p className="flex justify-between border-b border-slate-100 py-1 text-sm"><span><Link to={to} className="text-sky-800 underline">{no}</Link> · {fmtDateTime(at)}{extra && ` · ${extra}`}</span><b className="font-mono-num">{rp(total)}</b></p>;
  return (
    <div className="max-w-4xl space-y-4" data-testid="customer-history">
      <PageHead title={c.name} sub={`${c.phone || "tanpa nomor"}${c.address ? ` · ${c.address}${c.province ? ` (${c.province})` : ""}` : ""}`} />
      <Card title={`Pesanan WhatsApp (${orders.length})`} data-testid="customer-orders">{orders.map((o) => <Row key={o.id} to={`/admin/pesanan/${o.id}`} no={o.no} at={o.created_at} total={o.total} extra={o.ship_status} />)}{!orders.length && <p className="text-sm text-slate-500">Belum ada.</p>}</Card>
      <Card title={`Pekerjaan bengkel (${jobs.length})`}>{jobs.map((j) => <Row key={j.id} to={`/admin/pekerjaan/${j.id}`} no={j.no} at={j.created_at} total={j.total} extra={j.status} />)}{!jobs.length && <p className="text-sm text-slate-500">Belum ada.</p>}</Card>
      <Card title={`Penjualan langsung (${sales.length})`}>{sales.map((s) => <Row key={s.id} to={`/admin/penjualan/${s.id}`} no={s.no} at={s.created_at} total={s.total} />)}{!sales.length && <p className="text-sm text-slate-500">Belum ada.</p>}</Card>
      <Card title={`Kendaraan (${vehicles.length})`}>{vehicles.map((v) => <p key={v.id} className="text-sm"><Link to={`/admin/kendaraan/${v.id}`} className="font-mono-num text-sky-800 underline">{v.plate}</Link> {v.brand} {v.model}</p>)}{!vehicles.length && <p className="text-sm text-slate-500">Tidak wajib untuk pelanggan pesanan WA.</p>}</Card>
    </div>
  );
}

export function VehicleHistory() {
  const { id } = useParams();
  const [h] = useLoad(`/vehicles/${id}/history`);
  if (!h) return <p>Memuat…</p>;
  const { vehicle: v, customer: c, jobs } = h;
  return (
    <div className="max-w-4xl">
      <PageHead title={<span className="font-mono-num" data-testid="history-plate">{v.plate}</span>} sub={`${v.brand} ${v.model} · ${c?.name} · ${c?.phone || "-"}`}
        actions={<Link to={`/admin/pekerjaan/baru?vehicle=${v.id}`}><Btn data-testid="history-new-job"><Plus className="h-4 w-4" />Kunjungan baru</Btn></Link>} />
      <p className="mb-4 text-sm text-slate-600">{jobs.length} kunjungan tercatat.</p>
      <ol className="relative space-y-4 border-l-2 border-slate-200 pl-5" data-testid="history-timeline">
        {jobs.map((j) => (
          <li key={j.id} className="relative">
            <span className={`absolute -left-[27px] top-4 h-3 w-3 rounded-full ${j.kind === "garansi" ? "bg-amber-500" : "bg-sky-600"}`} />
            <Card title={<span><Link to={`/admin/pekerjaan/${j.id}`} className="text-sky-800 underline" data-testid={`history-job-${j.no}`}>{j.no}</Link> · {fmtDateTime(j.created_at)}</span>}
              actions={<><Badge>{j.status}</Badge>{j.kind === "garansi" && <Badge tone="Masuk">Klaim garansi</Badge>}</>}>
              {j.complaint && <p className="text-sm"><b>Keluhan:</b> {j.complaint}</p>}
              {j.claim && <p className="text-sm"><b>Klaim atas:</b> {j.claim.line_name} (nota {j.claim.ref_no}, klaim ke-{j.claim.claim_seq}) · Pemeriksaan: {j.claim.inspection || "-"} · Tindakan: {j.claim.action || "-"}</p>}
              <ul className="mt-2 space-y-0.5 text-sm">
                {j.lines.filter((l) => !l.removed).map((l) => (
                  <li key={l.lid}>• {l.name}{l.detail && ` — ${l.detail}`}{l.options?.length ? ` + ${l.options.map((o) => o.name).join(", ")}` : ""} x{l.qty} · {rp(l.subtotal)}
                    {l.warranty_until && <span className="text-emerald-700"> · garansi s/d {fmtDate(l.warranty_until)}</span>}</li>
                ))}
              </ul>
              {j.notes && <p className="mt-2 text-sm text-slate-600">Catatan: {j.notes}</p>}
              <p className="mt-2 text-sm">Total <b className="font-mono-num">{rp(j.total)}</b> · Dibayar <span className="font-mono-num">{rp(j.paid)}</span>{j.total > j.paid && j.status !== "Batal" && <span className="text-red-700"> · Sisa {rp(j.total - j.paid)}</span>}</p>
            </Card>
          </li>
        ))}
      </ol>
    </div>
  );
}

import { useState } from "react";
import { AlertTriangle } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { Btn, Field, Input, Card, PageHead } from "@/admin/ui";
import { useLoad } from "@/admin/tx";

function Counts({ s }) {
  const rows = Object.entries(s.labels).map(([k, l]) => [l, s.counts[k] || 0]);
  rows.push(["File unggahan (foto, logo, media)", s.counts.upload_files], ["Token Fonnte", s.counts.fonnte_token ? "tersimpan → dihapus" : "tidak ada"]);
  return (
    <div className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2" data-testid="reset-counts">
      {rows.map(([l, v]) => <p key={l} className="flex justify-between border-b border-slate-100 py-1"><span>{l}</span><b className="font-mono-num">{v}</b></p>)}
    </div>
  );
}

function Result({ r }) {
  const v = r.verification;
  return (
    <div className={`rounded-md border p-3 text-sm ${v.ok ? "border-emerald-300 bg-emerald-50 text-emerald-900" : "border-red-300 bg-red-50 text-red-900"}`} data-testid="reset-result">
      <p className="font-semibold">{v.ok ? "Reset selesai. Verifikasi bersih: tidak ada data lama, akun lain, atau token Fonnte yang tersisa." : "Reset selesai dengan catatan:"}</p>
      {v.issues.map((x) => <p key={x}>• {x}</p>)}
    </div>
  );
}

export default function ResetData() {
  const [s, load] = useLoad("/admin/reset/summary");
  const [f, setF] = useState({ password: "", confirm_text: "", backup_done: false });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [res, setRes] = useState(null);
  if (!s) return <p className="text-sm text-slate-500">Memuat…</p>;
  const run = async () => {
    if (!window.confirm("Hapus permanen SEMUA data aplikasi? Tindakan ini tidak dapat dibatalkan.")) return;
    setBusy(true); setErr("");
    try { setRes((await api.post("/admin/reset", f)).data); setF({ password: "", confirm_text: "", backup_done: false }); load(); } catch (e) { setErr(errMsg(e)); }
    setBusy(false);
  };
  return (
    <div className="max-w-4xl space-y-5" data-testid="reset-page">
      <PageHead title="Reset Data Uji" sub="Mengosongkan aplikasi untuk mulai memakai data asli. Hanya owner." />
      <div className="flex gap-3 rounded-md border border-red-300 bg-red-50 p-4 text-sm text-red-900">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
        <div>
          <p className="font-semibold">Tindakan permanen.</p>
          <p>Yang tersisa hanya akun Anda (<b>{s.keep.email}</b>) dengan password yang sama. Struktur website & dashboard tetap ada, konten CMS kembali kosong, nomor WhatsApp admin dan token Fonnte dihapus. File backup tidak disentuh.</p>
        </div>
      </div>
      <Card title="1. Data yang akan dihapus"><Counts s={s} />
        {!!s.other_users.length && <p className="mt-3 text-xs text-slate-600">Akun yang akan dihapus: {s.other_users.map((u) => `${u.email} (${u.role})`).join(", ")}</p>}</Card>
      <Card title="2. Buat backup dulu">
        <ol className="list-decimal space-y-1 pl-5 text-sm">
          <li>Di server VPS, masuk ke folder aplikasi lalu jalankan <code className="rounded bg-slate-100 px-1">./scripts/backup.sh</code>.</li>
          <li>Pastikan file backup baru muncul di folder <code className="rounded bg-slate-100 px-1">backups/</code> (database + unggahan).</li>
          <li>Unduh/salin file backup itu ke komputer Anda. Jika ingin kembali, pakai <code className="rounded bg-slate-100 px-1">./scripts/restore.sh</code>.</li>
        </ol>
      </Card>
      <Card title="3. Konfirmasi">
        <div className="space-y-3">
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.backup_done} onChange={(e) => setF({ ...f, backup_done: e.target.checked })} data-testid="reset-backup-check" />Saya sudah membuat dan menyimpan backup.</label>
          <Field label={`Ketik persis: ${s.confirm_text}`}><Input value={f.confirm_text} onChange={(e) => setF({ ...f, confirm_text: e.target.value })} data-testid="reset-confirm-text" /></Field>
          <Field label="Password owner"><Input type="password" autoComplete="current-password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} data-testid="reset-password" /></Field>
          {err && <p className="rounded-md bg-red-50 p-2 text-sm text-red-800" data-testid="reset-error">{err}</p>}
          <Btn v="danger" disabled={busy || !f.backup_done || f.confirm_text !== s.confirm_text || !f.password} onClick={run} data-testid="reset-submit">{busy ? "Menghapus…" : "Reset seluruh data"}</Btn>
          {res && <Result r={res} />}
        </div>
      </Card>
    </div>
  );
}

import { useState } from "react";
import { Info, KeyRound, Phone, Send, Trash2 } from "lucide-react";
import { api, newKey } from "@/lib/api";
import { fmtDateTime, KIND_LABEL } from "@/lib/fmt";
import { normalizeWa, waStatus } from "@/lib/wa";
import { useLoad, act } from "@/admin/tx";
import { WaResult } from "@/admin/WaNota";
import { Btn, Field, Input, Card, PageHead, Table, Td } from "@/admin/ui";

function TokenCard({ s, setS }) {
  const [tok, setTok] = useState("");
  const t = s.token;
  const save = async () => { const r = await act(() => api.put("/settings/whatsapp/token", { token: tok }), "Token disimpan"); if (r) { setS(r); setTok(""); } };
  const del = async () => { if (!window.confirm("Hapus token Fonnte? Pengiriman nota akan berhenti sampai token diisi lagi.")) return; const r = await act(() => api.delete("/settings/whatsapp/token"), "Token dihapus"); r && setS(r); };
  return (
    <Card title={<span className="flex items-center gap-2"><KeyRound className="h-4 w-4" />Token API Fonnte</span>} data-testid="wa-token-card">
      <div className="space-y-3">
        <p className="text-sm" data-testid="wa-token-status">
          {t.configured ? <>Tersimpan: <b className="font-mono-num">{t.masked}</b> · diubah {t.updated_by} {fmtDateTime(t.updated_at)}</> : <span className="text-amber-800">Belum ada token.</span>}
          {t.configured && !t.readable && <span className="block text-red-700">Token tidak dapat dibaca karena kunci server berubah — isi ulang token.</span>}
        </p>
        <div className="flex flex-wrap gap-2">
          <Input type="password" autoComplete="off" className="max-w-md" placeholder={t.configured ? "Tempel token baru untuk mengganti" : "Tempel token perangkat dari dashboard Fonnte"} value={tok} onChange={(e) => setTok(e.target.value)} data-testid="wa-token-input" />
          <Btn disabled={tok.trim().length < 8} onClick={save} data-testid="wa-token-save">{t.configured ? "Ganti token" : "Simpan token"}</Btn>
          {t.configured && <Btn v="outline" onClick={del} data-testid="wa-token-delete"><Trash2 className="h-4 w-4" />Hapus</Btn>}
        </div>
        <p className="text-xs text-slate-500">Token disimpan terenkripsi di server dan tidak pernah ditampilkan utuh lagi. Ambil di dashboard Fonnte → Device → Token.</p>
      </div>
    </Card>
  );
}

function numberState(s) {
  const d = s.admin_number, p = s.published_number;
  if (!d && !p) return ["empty", "Belum diisi", "Tombol WhatsApp tidak tampil di website.", "bg-slate-100 text-slate-700"];
  if (d && d === p) return ["live", "Sudah tampil di website", `Semua tombol WhatsApp di website membuka wa.me/${p}.`, "bg-emerald-50 text-emerald-800"];
  if (d && !p) return ["draft", "Tersimpan sebagai draft", "Belum tampil di website — tombol WhatsApp masih tersembunyi sampai diterbitkan.", "bg-amber-50 text-amber-900"];
  if (!d) return ["cleared", "Dikosongkan (draft)", `Website masih menampilkan wa.me/${p} sampai bagian Kontak diterbitkan.`, "bg-amber-50 text-amber-900"];
  return ["changed", "Nomor baru masih draft", `Website masih memakai wa.me/${p}; nomor baru ${d} tampil setelah diterbitkan.`, "bg-amber-50 text-amber-900"];
}

function NumberStatus({ s, typed }) {
  const [key, title, text, cls] = numberState(s);
  return (
    <div className={`rounded-md p-3 text-sm ${cls}`} data-testid="wa-number-status" data-state={key}>
      <p className="font-bold" data-testid="wa-number-status-title">Status: {title}</p>
      <p>{text}</p>
      <p className="mt-1 text-xs" data-testid="wa-number-published">Tampil di website saat ini: <b>{s.published_number ? `+${s.published_number}` : "— (tombol WhatsApp disembunyikan)"}</b>
        {s.published_number && <> · <a href={`https://wa.me/${s.published_number}`} target="_blank" rel="noreferrer" className="underline" data-testid="wa-number-live-link">uji tautan</a></>}</p>
      {typed !== s.admin_number && <p className="mt-1 text-xs font-semibold" data-testid="wa-number-unsaved">Isian di atas belum disimpan.</p>}
    </div>
  );
}

function NumberCard({ s, setS }) {
  const [num, setNum] = useState(s.admin_number);
  const bad = num.trim() && !normalizeWa(num);
  const save = async () => { const r = await act(() => api.put("/settings/whatsapp/number", { number: num }), "Nomor disimpan sebagai draft"); if (r) { setS(r); setNum(r.admin_number); } };
  const publish = async () => {
    if (s.contact_other_changes && !window.confirm("Bagian Kontak juga punya perubahan draft lain (alamat/jam/dll). Semua akan ikut diterbitkan. Lanjutkan?")) return;
    const r = await act(() => api.post("/settings/whatsapp/publish-number"), "Bagian Kontak diterbitkan"); r && setS(r);
  };
  return (
    <Card title={<span className="flex items-center gap-2"><Phone className="h-4 w-4" />Nomor WhatsApp admin</span>} data-testid="wa-number-card">
      <div className="space-y-3">
        <Field label="Nomor admin Predator Autolight" hint={bad ? "Format 08…, 62…, atau +62…" : "Dipakai untuk tombol WhatsApp di website dan tujuan pesan percobaan. Kosongkan untuk menyembunyikan tombol WA."}>
          <div className="flex flex-wrap gap-2"><Input className="max-w-xs" value={num} onChange={(e) => setNum(e.target.value)} data-testid="wa-number-input" />
            <Btn disabled={!!bad || num === s.admin_number} onClick={save} data-testid="wa-number-save">Simpan</Btn></div>
        </Field>
        <NumberStatus s={s} typed={num} />
        {s.pending_publish && (
          <div className="flex flex-wrap items-center gap-2 rounded-md bg-amber-50 p-2 text-sm text-amber-900" data-testid="wa-number-pending">
            {s.admin_number ? "Nomor baru masih draft — cek di Pratinjau CMS, lalu terbitkan." : "Nomor sudah dikosongkan di draft — terbitkan agar tombol WhatsApp hilang dari website."}
            <Btn size="sm" onClick={publish} data-testid="wa-number-publish">Terbitkan bagian Kontak</Btn>
          </div>
        )}
      </div>
    </Card>
  );
}

function TestCard({ s }) {
  const [key, setKey] = useState(newKey());
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  const run = async () => {
    if (busy) return;
    setBusy(true); setRes(null);
    const r = await act(() => api.post("/settings/whatsapp/test", { send_key: key }));
    setBusy(false); setKey(newKey());
    if (r) setRes(r);
  };
  return (
    <Card title={<span className="flex items-center gap-2"><Send className="h-4 w-4" />Pesan percobaan</span>} data-testid="wa-test-card">
      <div className="space-y-3">
        <p className="text-sm">Mengirim pesan singkat ke nomor admin tersimpan <b>{s.admin_number || "(belum diisi)"}</b>. Hanya terkirim saat tombol ditekan.</p>
        <Btn v="success" disabled={busy || !s.admin_number || !s.token.configured} onClick={run} data-testid="wa-test-send">{busy ? "Mengirim…" : "Kirim Pesan Percobaan"}</Btn>
        <WaResult r={res} testid="wa-test-result" />
      </div>
    </Card>
  );
}

function LogTable({ logs }) {
  return (
    <Table head={["Waktu", "Jenis", "Transaksi", "Tujuan", "Petugas", "Status", "ID Fonnte", "Alasan"]} testid="wa-log-table" empty={!logs?.length && "Belum ada riwayat pengiriman."}>
      {(logs || []).map((l) => (
        <tr key={l.id} data-testid={`wa-log-${l.id}`}>
          <Td className="whitespace-nowrap">{fmtDateTime(l.created_at)}</Td>
          <Td>{l.kind === "test" ? "Percobaan" : `Nota ${KIND_LABEL[l.ref_type] || ""}`}{l.resend && <span className="block text-xs text-amber-800">kirim ulang: {l.resend_reason}</span>}</Td>
          <Td className="font-mono-num">{l.ref_no || "-"}</Td>
          <Td className="font-mono-num">{l.target}</Td>
          <Td>{l.user_name}</Td>
          <Td><span className={`rounded border px-1.5 py-0.5 text-xs font-semibold ${waStatus(l.status).cls}`}>{waStatus(l.status).label}</span></Td>
          <Td className="font-mono-num">{l.request_id || "-"}</Td>
          <Td className="text-xs">{l.reason || "-"}</Td>
        </tr>
      ))}
    </Table>
  );
}

export default function WhatsAppSettings() {
  const [s, , setS] = useLoad("/settings/whatsapp");
  const [logs, loadLogs] = useLoad("/wa/logs");
  if (!s) return <p className="text-sm text-slate-500">Memuat…</p>;
  return (
    <div className="space-y-5" data-testid="wa-settings-page">
      <PageHead title="Pengaturan → WhatsApp" sub="Integrasi Fonnte untuk mengirim nota dari sistem. Hanya owner yang dapat melihat dan mengubah halaman ini." />
      <div className="flex gap-2 rounded-md border border-sky-200 bg-sky-50 p-3 text-sm text-sky-900" data-testid="wa-sender-info">
        <Info className="mt-0.5 h-4 w-4 shrink-0" />
        <p>Pesan otomatis (nota & percobaan) dikirim dari <b>perangkat WhatsApp yang terhubung dengan token Fonnte</b>, bukan dari nomor admin di bawah. Nomor admin hanya dipakai untuk tombol WhatsApp di website dan sebagai tujuan pesan percobaan.</p>
      </div>
      <div className="grid gap-5 xl:grid-cols-2">
        <TokenCard s={s} setS={setS} />
        <NumberCard key={s.admin_number} s={s} setS={setS} />
      </div>
      <TestCard s={s} />
      <Card title="Riwayat pengiriman WhatsApp" actions={<Btn v="outline" size="sm" onClick={loadLogs} data-testid="wa-log-refresh">Muat ulang</Btn>}>
        <LogTable logs={logs} />
      </Card>
    </div>
  );
}

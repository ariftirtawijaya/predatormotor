import { useState } from "react";
import { Send } from "lucide-react";
import { api, errMsg, newKey } from "@/lib/api";
import { fmtDateTime } from "@/lib/fmt";
import { waStatus, normalizeWa, hasActiveSend } from "@/lib/wa";
import { Btn, Field, Input, Modal } from "@/admin/ui";

export function WaResult({ r, testid = "wa-result" }) {
  if (!r) return null;
  const s = waStatus(r.status);
  return (
    <div className={`rounded-md border p-3 text-sm ${s.cls}`} data-testid={testid}>
      <p className="font-semibold" data-testid={`${testid}-status`}>{s.label}{r.duplicate && " (klik ganda diabaikan)"}</p>
      {r.status === "antre" && <p className="text-xs">Fonnte menerima permintaan dan memasukkannya ke antrean. Ini belum bukti pesan sampai ke penerima.</p>}
      {r.reason && <p className="text-xs" data-testid={`${testid}-reason`}>Alasan: {r.reason}</p>}
      {r.request_id && <p className="text-xs">ID permintaan Fonnte: {r.request_id}</p>}
    </div>
  );
}

export function WaLogList({ logs }) {
  if (!logs?.length) return <p className="text-xs text-slate-500">Belum pernah dikirim lewat sistem.</p>;
  return (
    <div className="space-y-1 text-xs" data-testid="wa-nota-history">
      {logs.map((l) => (
        <div key={l.id} className="flex flex-wrap justify-between gap-2 border-b border-slate-100 py-1">
          <span>{fmtDateTime(l.created_at)} · ke {l.target} · {l.user_name}{l.resend && " · kirim ulang"}{l.reason && ` · ${l.reason}`}</span>
          <span className={`rounded border px-1.5 font-semibold ${waStatus(l.status).cls}`}>{waStatus(l.status).label}</span>
        </div>
      ))}
    </div>
  );
}

function SendForm({ kind, doc, info, onSent }) {
  const [target, setTarget] = useState("");
  const [reason, setReason] = useState("");
  const [key] = useState(newKey());
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const resend = hasActiveSend(info.logs);
  const validTarget = !info.target_editable || normalizeWa(target);
  const send = async () => {
    if (busy) return;
    setBusy(true); setErr("");
    try {
      const r = await api.post(`/wa/nota/${kind}/${doc.id}`, { send_key: key, target, resend, resend_reason: reason });
      onSent(r.data);
    } catch (e) { setErr(errMsg(e)); setBusy(false); }
  };
  return (
    <div className="space-y-3">
      {info.target_editable ? (
        <Field label="Nomor WhatsApp penerima" hint={target && !normalizeWa(target) ? "Format 08…, 62…, atau +62…" : "Nomor pembeli tidak tersimpan di nota ini."}>
          <Input value={target} onChange={(e) => setTarget(e.target.value)} placeholder="08…" data-testid="wa-nota-target-input" />
        </Field>
      ) : <p className="text-sm">Dikirim ke: <b data-testid="wa-nota-target">{info.target || "—"}</b></p>}
      {resend && <Field label="Alasan kirim ulang" hint="Nota ini sudah pernah dikirim/masuk antrean. Pelanggan bisa menerima nota ganda.">
        <Input value={reason} onChange={(e) => setReason(e.target.value)} data-testid="wa-nota-resend-reason" /></Field>}
      {err && <p className="rounded-md bg-red-50 p-2 text-sm text-red-800" data-testid="wa-nota-error">{err}</p>}
      <Btn v={resend ? "outline" : "success"} disabled={busy || !validTarget || (!info.target && !info.target_editable) || (resend && reason.trim().length < 3)} onClick={send} data-testid={resend ? "wa-nota-resend" : "wa-nota-submit"}>
        <Send className="h-4 w-4" />{busy ? "Mengirim…" : resend ? "Kirim Ulang Nota" : "Kirim Nota"}
      </Btn>
    </div>
  );
}

export function SendNotaWA({ kind, doc }) {
  const [open, setOpen] = useState(false);
  const [info, setInfo] = useState(null);
  const [result, setResult] = useState(null);
  const [round, setRound] = useState(0);
  const load = () => api.get(`/wa/nota/${kind}/${doc.id}`).then((r) => setInfo(r.data)).catch((e) => setInfo({ error: errMsg(e) }));
  const show = () => { setOpen(true); setResult(null); setInfo(null); load(); };
  const sent = (r) => { setResult(r); setRound(round + 1); load(); };
  return (
    <>
      <Btn v="success" size="sm" onClick={show} data-testid="nota-send-wa"><Send className="h-4 w-4" />Kirim Nota via WhatsApp</Btn>
      <Modal open={open} onClose={() => setOpen(false)} title={`Kirim nota ${doc.no} via WhatsApp`} wide>
        {!info ? <p className="text-sm text-slate-500">Memuat…</p> : info.error ? <p className="text-sm text-red-700">{info.error}</p> : (
          <div className="space-y-4" data-testid="wa-nota-dialog">
            {!info.token_configured && <p className="rounded-md bg-amber-50 p-2 text-sm text-amber-900" data-testid="wa-nota-no-token">Token Fonnte belum diatur. Minta owner mengisinya di Pengaturan → WhatsApp.</p>}
            <WaResult r={result} />
            <SendForm key={round} kind={kind} doc={doc} info={info} onSent={sent} />
            <div><p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-600">Isi pesan</p>
              <pre className="max-h-64 overflow-y-auto whitespace-pre-wrap rounded-md border border-slate-200 bg-slate-50 p-3 text-xs" data-testid="wa-nota-preview">{info.message}</pre></div>
            <div><p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-600">Riwayat pengiriman</p><WaLogList logs={info.logs} /></div>
          </div>
        )}
      </Modal>
    </>
  );
}

import { useState } from "react";
import { AlertTriangle } from "lucide-react";
import { api } from "@/lib/api";
import { Btn, Field, Input, Modal } from "@/admin/ui";
import { useLoad, act } from "@/admin/tx";

const LABEL = { item: "varian", product: "produk", package: "paket", user: "pengguna" };

function Blocked({ chk, onDeactivate, busy }) {
  return (
    <div className="space-y-3" data-testid="delete-blocked">
      <div className="flex gap-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
        <div><p className="font-semibold">Tidak dapat dihapus permanen:</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-4" data-testid="delete-reasons">{chk.reasons.map((r) => <li key={r}>{r}</li>)}</ul></div>
      </div>
      {onDeactivate && <Btn v="outline" disabled={busy} onClick={onDeactivate} data-testid="delete-deactivate-button">Nonaktifkan saja</Btn>}
    </div>
  );
}

export function DeleteDialog({ kind, id, url, onClose, onDone, onDeactivate }) {
  const [chk] = useLoad(`/admin/delete-check/${kind}/${id}`);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const run = async (fn, msg) => { setBusy(true); const r = await act(fn, msg); setBusy(false); if (r) { onDone(); onClose(); } };
  return (
    <Modal open onClose={onClose} title={`Hapus ${LABEL[kind]}${chk ? `: ${chk.name}` : ""}`}>
      {!chk ? <p className="text-sm text-slate-500">Memeriksa keterkaitan data…</p> : !chk.can_delete ? (
        <Blocked chk={chk} busy={busy} onDeactivate={onDeactivate && (() => run(onDeactivate, "Dinonaktifkan"))} />
      ) : (
        <div className="space-y-3" data-testid="delete-confirm">
          <p className="text-sm">Data <b>{chk.name}</b> akan dihapus permanen.
            {kind === "product" && <> Tindakan ini juga menghapus <b data-testid="delete-variant-count">{chk.variant_count} varian</b> di dalamnya.</>}
            {" "}Transaksi dan riwayat stok tidak ikut terhapus; tindakan dicatat di audit log.</p>
          <Field label={`Ketik nama untuk konfirmasi: ${chk.name}`}><Input value={typed} onChange={(e) => setTyped(e.target.value)} data-testid="delete-confirm-input" /></Field>
          <Btn v="danger" disabled={busy || typed !== chk.name} onClick={() => run(() => api.delete(url, { params: { confirm: typed } }), "Data dihapus")} data-testid="delete-submit-button">Hapus permanen</Btn>
        </div>
      )}
    </Modal>
  );
}

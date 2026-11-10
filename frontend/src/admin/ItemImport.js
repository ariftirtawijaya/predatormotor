import { useState } from "react";
import { api, errMsg } from "@/lib/api";
import { rp } from "@/lib/fmt";
import { Btn, Modal, Table, Td } from "@/admin/ui";
import { toast } from "sonner";

const ACTION = { baru: "Varian baru", perbarui: "Perbarui data", tetap: "Tidak berubah" };

function Summary({ s }) {
  return (
    <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-3" data-testid="import-summary">
      <p>Produk baru: <b>{s.products_new}</b></p><p>Produk yang sudah ada: <b>{s.products_existing}</b></p>
      <p>Varian baru: <b data-testid="import-variants-new">{s.variants_new}</b></p><p>Varian diperbarui: <b>{s.variants_update}</b></p>
      <p>Tidak berubah: <b>{s.variants_same}</b></p><p>Stok awal (varian baru): <b>{s.initial_stock_total} pcs</b></p>
    </div>
  );
}

export function ImportDialog({ onClose, onDone }) {
  const [file, setFile] = useState(null);
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const send = async (commit) => {
    const fd = new FormData();
    fd.append("file", file);
    setBusy(true); setErr("");
    try {
      const r = await api.post(`/items/import?commit=${commit}${commit ? `&plan_hash=${res?.plan_hash || ""}` : ""}`, fd);
      setRes(r.data);
      return r.data;
    } catch (e) {
      setErr(errMsg(e));
      const rows = e?.response?.data?.errors;
      if (commit && rows?.length) setRes({ ...res, errors: rows });
      return null;
    } finally { setBusy(false); }
  };
  const commit = async () => {
    const d = await send(true);
    if (d?.committed) { toast.success("Impor disimpan"); onDone(); }
  };
  return (
    <Modal open onClose={onClose} title="Impor Master Barang dari Excel" wide>
      <div className="space-y-4" data-testid="import-dialog">
        <p className="text-sm text-slate-600">Satu baris = satu varian. Baris dengan <b>kode_produk</b> sama menjadi varian dari produk yang sama; <b>nama_varian</b> kosong = produk sederhana. Stok varian yang sudah ada tidak pernah ditimpa. Impor disimpan <b>seluruhnya atau tidak sama sekali</b>, dan diperiksa ulang saat anda menekan Simpan.</p>
        <input type="file" accept=".xlsx" onChange={(e) => { setFile(e.target.files[0]); setRes(null); }} data-testid="import-file-input" />
        <Btn v="outline" disabled={!file || busy} onClick={() => send(false)} data-testid="import-preview-button">Pratinjau</Btn>
        {err && <p className="rounded-md bg-red-50 p-2 text-sm text-red-800" data-testid="import-error">{err}</p>}
        {res && (<>
          <Summary s={res.summary} />
          {!!res.errors.length && (
            <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900" data-testid="import-row-errors">
              <p className="font-semibold">{res.errors.length} baris bermasalah — perbaiki file lalu pratinjau ulang:</p>
              {res.errors.map((e, i) => <p key={i}>Baris {e.row}: {e.message}</p>)}
            </div>
          )}
          <div className="max-h-72 overflow-y-auto">
            <Table head={["Baris", "Produk", "Varian", "SKU", "Harga", "Stok awal", "Tindakan"]} testid="import-preview-table">
              {res.rows.map((r) => (
                <tr key={r.row}><Td>{r.row}</Td><Td>{r.product_name}<div className="text-xs text-slate-500">{r.product_code}</div></Td><Td>{r.variant || <span className="text-slate-500">Produk sederhana</span>}</Td>
                  <Td className="font-mono-num">{r.sku}</Td><Td className="font-mono-num">{rp(r.price)}</Td>
                  <Td>{r.action === "baru" ? r.initial_stock : <span className="text-xs text-slate-500">{r.stock_note || "-"}</span>}</Td><Td>{ACTION[r.action]}</Td></tr>
              ))}
            </Table>
          </div>
          {!res.committed && !res.transactions_ready && (
            <p className="rounded-md border border-amber-300 bg-amber-50 p-2 text-sm text-amber-900" data-testid="import-no-transactions">Server database belum mode replica set, jadi impor belum bisa disimpan di sini (pratinjau tetap berfungsi). Di VPS, ikuti README bagian Impor Excel.</p>
          )}
          {res.committed ? <p className="font-semibold text-emerald-700" data-testid="import-done">Impor selesai disimpan.</p> : (
            <Btn disabled={busy || !!res.errors.length || !res.rows.length || !res.transactions_ready || !(res.summary.variants_new + res.summary.variants_update)} onClick={commit} data-testid="import-commit-button">{res.summary.variants_new + res.summary.variants_update ? "Konfirmasi & simpan impor" : "Tidak ada perubahan untuk disimpan"}</Btn>
          )}
        </>)}
      </div>
    </Modal>
  );
}

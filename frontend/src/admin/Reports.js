import { useState } from "react";
import { Link } from "react-router-dom";
import { BACKEND } from "@/lib/api";
import { rp, fmtDate, fmtDateTime, monthStart, today, KIND_LABEL, KIND_PATH } from "@/lib/fmt";
import { Btn, Input, Card, Table, Td, PageHead, Stat } from "@/admin/ui";
import { useLoad } from "@/admin/tx";

const TxLink = ({ k, id, no }) => <Link to={`/admin/${KIND_PATH[k]}/${id}`} className="font-semibold text-sky-800 hover:underline">{no}</Link>;

export default function Reports() {
  const [r, setR] = useState({ start: monthStart(), end: today() });
  const [d] = useLoad(`/reports/summary?start=${r.start}&end=${r.end}`);
  const exp = (k) => `${BACKEND}/api/reports/export?kind=${k}&start=${r.start}&end=${r.end}`;
  return (
    <div className="print-area w-full">
      <PageHead title="Laporan" sub={`Periode ${fmtDate(r.start)} – ${fmtDate(r.end)} (WIB)`} actions={<div className="no-print flex flex-wrap items-center gap-2">
        <Input type="date" className="!w-40" value={r.start} onChange={(e) => setR({ ...r, start: e.target.value })} data-testid="report-start" />
        <Input type="date" className="!w-40" value={r.end} onChange={(e) => setR({ ...r, end: e.target.value })} data-testid="report-end" />
        <Btn v="outline" onClick={() => setR({ start: today(), end: today() })} data-testid="report-today">Hari ini</Btn>
        <Btn v="dark" onClick={() => window.print()} data-testid="report-print">Cetak / PDF</Btn></div>} />
      {!d ? <p>Memuat…</p> : (
        <div className="space-y-5">
          <div>
            <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-slate-600">1. Omzet (nilai transaksi yang diakui)</h2>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
              <Stat label="Pekerjaan bengkel" value={rp(d.omzet.job)} sub={`${d.count.job} nota selesai`} testid="rep-omzet-job" />
              <Stat label="Penjualan langsung" value={rp(d.omzet.sale)} sub={`${d.count.sale} transaksi`} testid="rep-omzet-sale" />
              <Stat label="Pesanan WA" value={rp(d.omzet.order)} sub={`${d.count.order} pesanan · ongkir ${rp(d.shipping)} terpisah`} testid="rep-omzet-order" />
              <Stat label="Total omzet" value={rp(d.omzet_total)} sub={`setelah diskon ${rp(d.discount)}`} tone="border-sky-300 bg-sky-50" testid="rep-omzet-total" />
              <Stat label="Retur (refund + COD batal)" value={rp(d.return_refund + d.write_off)} sub={`${d.returns.length} retur · omzet bersih ${rp(d.net_revenue)}`} testid="rep-refunds" />
            </div>
          </div>
          <div>
            <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-slate-600">2. Uang diterima (kas nyata)</h2>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
              <Stat label="Tunai" value={rp(d.received.tunai)} testid="rep-cash" />
              <Stat label="Transfer" value={rp(d.received.transfer)} testid="rep-transfer" />
              {!!d.received.cod && <Stat label="COD barang cair (data lama)" value={rp(d.received.cod)} testid="rep-cod-received" />}
              <Stat label="Ongkir diterima bengkel" value={rp(d.shipping)} sub={d.shipping_cod_courier ? `COD ongkir ke kurir ${rp(d.shipping_cod_courier)} (bukan uang bengkel)` : ""} testid="rep-shipping-received" />
              <Stat label="DP diterima (periode)" value={rp(d.dp_received)} testid="rep-dp" />
              <Stat label="Kas bersih (masuk − keluar)" value={rp(d.net_cash)} sub={`uang keluar/refund ${rp(d.refund_total)}`} tone="border-emerald-300 bg-emerald-50" testid="rep-net-cash" />
            </div>
          </div>
          <div>
            <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-slate-600">3. Belum menjadi uang (posisi saat ini)</h2>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              {!!d.cod_pending_total && <Stat label="COD barang data lama (belum cair)" value={rp(d.cod_pending_total)} sub={`${d.cod_pending.length} paket`} tone="border-amber-300 bg-amber-50" testid="rep-cod-pending" />}
              <Stat label="Biaya ongkir dibayar bengkel" value={rp(d.shipping_expense)} sub="dari menu Biaya" testid="rep-shipping-expense" />
              <Stat label="Piutang pekerjaan" value={rp(d.receivables_total)} sub={`${d.receivables.length} nota`} testid="rep-receivables" />
              <Stat label="DP tertahan (belum selesai)" value={rp(d.dp_held_total)} sub={`${d.dp_held.length} transaksi`} testid="rep-dp-held" />
              <Stat label="Nilai persediaan (modal)" value={rp(d.inventory_value)} sub={`${d.inventory_units} pcs`} testid="rep-inventory" />
            </div>
          </div>
          <div>
            <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-slate-600">4. Laba</h2>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
              <Stat label="HPP (modal barang terpakai)" value={rp(d.hpp)} sub={`− modal retur layak ${rp(d.return_hpp_back)}`} testid="rep-hpp" />
              <Stat label="Laba kotor" value={rp(d.gross_profit)} tone="border-sky-300 bg-sky-50" testid="rep-gross" />
              <Stat label="Biaya operasional" value={rp(d.expense_total)} testid="rep-expenses" />
              <Stat label="Kerugian rusak + internal" value={rp(d.damage_loss + d.internal_use_cost)} testid="rep-loss" />
              <Stat label="Laba bersih" value={rp(d.net_profit)} sub={d.cancel_kept ? `termasuk DP ditahan ${rp(d.cancel_kept)}` : ""} tone="border-emerald-300 bg-emerald-50" testid="rep-net" />
            </div>
            <div className="mt-3 rounded-md border border-slate-200 bg-white p-4 text-sm text-slate-700" data-testid="rep-definitions">
              <p><b>Omzet</b> = total nota pekerjaan yang Selesai + penjualan langsung + pesanan WA yang barangnya sudah keluar (tanpa ongkir), setelah diskon. Pembayaran bertahap (DP & pelunasan) tidak menggandakan omzet.</p>
              <p className="mt-1"><b>Omzet bersih</b> = Omzet − uang yang dikembalikan karena retur − tagihan COD yang batal karena paket kembali. Pengembalian DP dari pembatalan nota yang belum selesai tidak mengurangi omzet (karena memang belum pernah dihitung).</p>
              <p className="mt-1"><b>Laba kotor</b> = Omzet bersih − (HPP − modal barang retur yang kembali layak jual). HPP memakai modal yang tersimpan pada nota saat transaksi.</p>
              <p className="mt-1"><b>Laba bersih</b> = Laba kotor − Biaya operasional − Modal barang rusak dari stok − Modal pemakaian internal + DP yang ditahan dari pembatalan. Tidak termasuk biaya sewa (tempat milik sendiri).</p>
              <p className="mt-1 text-amber-800">Laba bersih hanya akurat bila modal barang dan seluruh biaya dicatat lengkap.{d.missing_cost_items > 0 && ` Saat ini ada ${d.missing_cost_items} barang aktif tanpa modal.`}</p>
            </div>
          </div>
          <Card title="Ekspor data" className="no-print">
            <div className="flex flex-wrap gap-2">
              {[["transactions", "Transaksi"], ["payments", "Pembayaran"], ["mutations", "Mutasi stok"], ["damaged", "Barang rusak"], ["expenses", "Biaya"], ["inventory", "Persediaan"]].map(([k, l]) => (
                <Btn key={k} v="outline" size="sm" onClick={() => { window.location.href = exp(k); }} data-testid={`export-${k}`}>CSV {l}</Btn>
              ))}
            </div>
          </Card>
          <Card title="Ringkasan harian">
            <Table head={["Tanggal", "Pekerjaan", "Penjualan", "Pesanan WA", "Uang masuk", "Uang keluar", "Biaya"]} testid="rep-daily-table" empty={!d.daily.length && "Tidak ada data."}>
              {d.daily.map((x) => <tr key={x.date}><Td>{fmtDate(x.date)}</Td>{["omzet_job", "omzet_sale", "omzet_order", "uang_masuk", "uang_keluar", "biaya"].map((k) => <Td key={k} className="font-mono-num">{rp(x[k])}</Td>)}</tr>)}
            </Table>
          </Card>
          <Card title={`Transaksi sumber (${d.transactions.length})`}>
            <Table head={["Tanggal", "Jenis", "No", "Pelanggan", "Diskon", "Total", "Dibayar", "Refund", "HPP"]} testid="rep-tx-table" empty={!d.transactions.length && "Tidak ada transaksi."}>
              {d.transactions.map((t) => <tr key={t.id}><Td>{fmtDate(t.date)}</Td><Td>{KIND_LABEL[t.kind]}</Td><Td><TxLink k={t.kind} id={t.id} no={t.no} /></Td><Td>{t.customer}</Td>
                {["discount", "total", "paid", "refunded", "hpp"].map((k) => <Td key={k} className="font-mono-num">{rp(t[k])}</Td>)}</tr>)}
            </Table>
          </Card>
          <div className="grid gap-4 lg:grid-cols-2">
            {!!d.cod_pending.length && <Card title="COD barang data lama (belum cair)">{d.cod_pending.map((c) => <p key={c.id} className="flex justify-between text-sm"><span><TxLink k="order" id={c.id} no={c.no} /> · {c.customer} · dikirim {fmtDateTime(c.shipped_at)}</span><b>{rp(c.amount)}</b></p>)}{!d.cod_pending.length && <p className="text-sm text-slate-500">Tidak ada.</p>}</Card>}
            <Card title="Piutang & DP tertahan">
              {d.receivables.map((c) => <p key={c.id} className="flex justify-between text-sm"><span><TxLink k="job" id={c.id} no={c.no} /> · {c.customer} (piutang)</span><b>{rp(c.amount)}</b></p>)}
              {d.dp_held.map((c) => <p key={c.id} className="flex justify-between text-sm"><span><TxLink k={c.kind} id={c.id} no={c.no} /> · {c.customer} (DP dari {rp(c.total)})</span><b>{rp(c.paid)}</b></p>)}
              {!d.receivables.length && !d.dp_held.length && <p className="text-sm text-slate-500">Tidak ada.</p>}
            </Card>
            <Card title="Retur & pembatalan">
              {d.returns.map((x, i) => <p key={i} className="text-sm"><TxLink k={x.kind} id={x.id} no={x.no} /> · {fmtDate(x.date)} · refund {rp(x.refund)} · {x.reason}</p>)}
              {d.cancels.map((x, i) => <p key={`c${i}`} className="text-sm"><TxLink k={x.kind} id={x.id} no={x.no} /> · batal {fmtDate(x.date)} · refund {rp(x.refund)} · ditahan {rp(x.kept)} · {x.reason}</p>)}
              {!d.returns.length && !d.cancels.length && <p className="text-sm text-slate-500">Tidak ada.</p>}
            </Card>
            <Card title="Biaya per kategori & barang rusak">
              {Object.entries(d.expenses).map(([k, v]) => <p key={k} className="flex justify-between text-sm"><span>{k}</span><b>{rp(v)}</b></p>)}
              <p className="mt-2 text-sm">Barang rusak periode ini: {d.damaged_count} pcs · kerugian modal dari stok {rp(d.damage_loss)} · pemakaian internal {rp(d.internal_use_cost)}</p>
              {!!d.low_stock.length && <p className="mt-2 text-sm text-red-700">Stok menipis: {d.low_stock.map((i) => `${i.name} (${i.stock})`).join(", ")}</p>}
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}

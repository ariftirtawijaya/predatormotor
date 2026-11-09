import { Link } from "react-router-dom";
import { rp } from "@/lib/fmt";
import { useAuth, isManager, isOwner } from "@/context/AuthContext";
import { PageHead, Stat, Card, Btn } from "@/admin/ui";
import { useLoad } from "@/admin/tx";

export default function Dashboard() {
  const { user } = useAuth();
  const [d] = useLoad("/dashboard");
  if (!d) return <p>Memuat…</p>;
  const t = d.today;
  return (
    <div>
      <PageHead title={`Halo, ${user.name}`} sub={`Ringkasan hari ini (${t.date}, WIB)`} actions={<>
        <Link to="/admin/pekerjaan/baru"><Btn data-testid="dash-new-job">Nota pekerjaan</Btn></Link>
        <Link to="/admin/kasir"><Btn v="dark" data-testid="dash-kasir">Kasir</Btn></Link>
        <Link to="/admin/pesanan/baru"><Btn v="outline" data-testid="dash-new-order">Pesanan WA</Btn></Link></>} />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Link to="/admin/pekerjaan"><Stat label="Pekerjaan Masuk" value={d.open_jobs} sub="belum selesai" testid="dash-open-jobs" /></Link>
        <Link to="/admin/pesanan"><Stat label="Pesanan WA baru" value={d.new_orders} testid="dash-new-orders" /></Link>
        <Stat label="Omzet pekerjaan hari ini" value={rp(t.types.job.omzet)} sub={`${t.types.job.count} nota selesai`} testid="dash-omzet-job" />
        <Stat label="Omzet penjualan hari ini" value={rp(t.types.sale.omzet)} sub={`${t.types.sale.count} transaksi`} testid="dash-omzet-sale" />
        <Stat label="Omzet pesanan WA hari ini" value={rp(t.types.order.omzet)} sub={`${t.types.order.count} pesanan diproses`} testid="dash-omzet-order" />
        <Stat label="Uang diterima tunai" value={rp(t.payments_in.tunai)} testid="dash-cash" />
        <Stat label="Uang diterima transfer" value={rp(t.payments_in.transfer)} testid="dash-transfer" />
        {!!t.payments_in.cod && <Stat label="Dana COD barang cair (data lama)" value={rp(t.payments_in.cod)} testid="dash-cod" />}
        {!!t.refunds && <Stat label="Pengembalian uang hari ini" value={rp(t.refunds)} testid="dash-refunds" />}
      </div>
      {isManager(user) && (
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <Card title="Stok menipis" data-testid="dash-low-stock">
            {!d.low_stock.length ? <p className="text-sm text-slate-500">Tidak ada stok di bawah batas minimum.</p> :
              d.low_stock.map((i) => <p key={i.id} className="flex justify-between border-b border-slate-100 py-1 text-sm"><span>{i.name} <span className="text-xs text-slate-500">{i.sku}</span></span><b className="text-red-700">{i.stock} / min {i.min_stock}</b></p>)}
          </Card>
          <Card title="Keuangan">
            <div className="grid grid-cols-2 gap-3">
              {!!d.cod_pending_total && <Stat label="COD barang data lama (belum cair)" value={rp(d.cod_pending_total)} testid="dash-cod-pending" />}
              {isOwner(user) && <Stat label="Piutang pekerjaan" value={rp(d.receivables_total)} testid="dash-receivables" />}
              {isOwner(user) && <Stat label="Nilai persediaan (modal)" value={rp(d.inventory_value)} testid="dash-inventory" />}
              {isOwner(user) && <Link to="/admin/diskon"><Stat label="Diskon menunggu" value={d.pending_discounts} tone={d.pending_discounts ? "border-amber-400 bg-amber-50" : ""} testid="dash-pending-discounts" /></Link>}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}

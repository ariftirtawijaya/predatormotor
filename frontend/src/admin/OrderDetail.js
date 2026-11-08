import { useState } from "react";
import { useParams } from "react-router-dom";
import { Truck } from "lucide-react";
import { api } from "@/lib/api";
import { rp, fmtDateTime } from "@/lib/fmt";
import { useAuth, isManager, isOwner } from "@/context/AuthContext";
import { Btn, Field, Input, Card, PageHead, Badge } from "@/admin/ui";
import { useLoad, act, LinesTable, Totals, PaymentBox, PaymentsList, DiscountBox, ReturnDialog, NotaActions, ReturnsList } from "@/admin/tx";

export default function OrderDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const [o, , setO] = useLoad(`/orders/${id}`);
  const [site] = useLoad("/public/site");
  const [resi, setResi] = useState("");
  const [modal, setModal] = useState("");
  if (!o) return <p>Memuat…</p>;
  const closed = ["Batal", "Kembali"].includes(o.ship_status);
  const cod = o.payment_type === "cod";
  const ship = async () => { const r = await act(() => api.post(`/orders/${id}/ship`, { resi }), o.delivery === "ambil" ? "Ditandai diambil" : "Ditandai dikirim"); r && setO(r); };
  const saveResi = async () => { const r = await act(() => api.patch(`/orders/${id}`, { resi }), "Resi disimpan"); r && setO(r); };
  return (
    <div>
      <PageHead title={<span data-testid="order-no">{o.no}</span>} sub={`Pesanan WA · ${fmtDateTime(o.created_at)} · ${o.created_by}`}
        actions={<><Badge data-testid="order-status">{o.ship_status}</Badge><Badge tone={cod ? "Masuk" : "Baru"} data-testid="order-payment-type-badge">{cod ? "COD" : "Prabayar"}</Badge><NotaActions kind="order" doc={o} shopName={site?.identity?.name} /></>} />
      <div className="grid gap-4 xl:grid-cols-[1fr_380px]">
        <div className="min-w-0 space-y-4">
          <Card title="Pelanggan & pengiriman">
            <div className="grid gap-1 text-sm sm:grid-cols-2">
              <p><b>{o.customer.name}</b> · {o.customer.phone}</p>
              <p>{o.delivery === "ambil" ? "Diambil langsung di bengkel" : `${o.courier} · ${o.province}${o.is_java ? " (Jawa)" : ""}`}</p>
              {o.address && <p className="sm:col-span-2">{o.address}</p>}
              {o.notes && <p className="sm:col-span-2 text-slate-600">Catatan: {o.notes}</p>}
              <p>Resi: <b data-testid="order-resi">{o.resi || "-"}</b></p>
              <p>Stok: <b data-testid="order-stock-status">{o.stock_applied ? "sudah dikurangi" : "belum dikurangi"}</b></p>
              {!cod && o.paid >= o.total && o.total > 0 && !o.stock_applied && <p className="sm:col-span-2 font-semibold text-red-700" data-testid="order-stock-pending">Pembayaran lunas tetapi stok belum terpotong — tambah stok lalu tekan Kirim/Diambil untuk memotong stok.</p>}
              {cod && <p className="sm:col-span-2">Dana COD: <b data-testid="order-cod-status">{o.cod_settled ? "sudah cair" : o.stock_applied ? "belum cair" : "paket belum dikirim"}</b></p>}
            </div>
            {o.delivery === "kurir" && !closed && (
              <div className="mt-3 flex gap-2"><Input placeholder="Nomor resi" value={resi} onChange={(e) => setResi(e.target.value)} data-testid="order-resi-input" />
                {o.ship_status !== "Baru" && <Btn v="outline" onClick={saveResi} disabled={!resi} data-testid="order-resi-save">Simpan resi</Btn>}</div>
            )}
          </Card>
          <Card title="Barang"><LinesTable doc={o} /></Card>
          <ReturnsList returns={o.returns} />
        </div>
        <div className="space-y-4">
          <Card title="Total"><Totals doc={o} /></Card>
          {o.ship_status === "Baru" && (
            <Btn className="h-12 w-full" onClick={ship} disabled={!cod && o.paid < o.total} data-testid="order-ship-button">
              <Truck className="h-5 w-5" />{o.delivery === "ambil" ? "Tandai diambil pelanggan" : cod ? "Kirim (stok dikurangi)" : "Tandai dikirim"}
            </Btn>
          )}
          {!cod && o.ship_status === "Baru" && o.paid < o.total && <p className="text-xs text-slate-600">Prabayar: stok berkurang saat pembayaran lunas diterima; setelah itu pesanan dapat dikirim.</p>}
          {o.ship_status === "Dikirim" && <Btn v="outline" className="w-full" onClick={async () => { const r = await act(() => api.post(`/orders/${id}/delivered`), "Ditandai diterima"); r && setO(r); }} data-testid="order-delivered-button">Tandai paket diterima</Btn>}
          <Card title="Diskon"><DiscountBox kind="order" doc={o} onDone={setO} editable={!o.stock_applied && !closed} /></Card>
          {!closed && (!cod || o.stock_applied) && <Card title={cod ? "Catat dana COD cair" : "Pembayaran"}><PaymentBox kind="order" doc={o} onDone={setO} cod={cod} /></Card>}
          <Card title="Riwayat pembayaran"><PaymentsList payments={o.payments} /></Card>
          <div className="flex flex-wrap gap-2">
            {o.ship_status === "Baru" && isOwner(user) && <Btn v="danger" onClick={() => setModal("cancel")} data-testid="order-cancel-button">Batalkan pesanan</Btn>}
            {["Dikirim", "Diterima", "Diambil"].includes(o.ship_status) && isManager(user) && <Btn v="outline" onClick={() => setModal("return")} data-testid="order-return-button">Paket kembali / retur</Btn>}
          </div>
          {o.cancel && <p className="text-sm" data-testid="order-cancel-info">Dibatalkan {o.cancel.by}: {o.cancel.reason} · refund {rp(o.cancel.refund)}{!!o.cancel.items_not_returned?.length && ` · saat batal ${o.cancel.items_not_returned.reduce((s, i) => s + i.qty, 0)} pcs belum kembali`}</p>}
          {["Batal", "Kembali"].includes(o.ship_status) && !!o.outstanding_items?.length && (
            <Card title="Barang belum kembali ke bengkel" data-testid="order-outstanding">
              {o.outstanding_items.map((i) => <p key={i.item_id} className="text-sm text-amber-900">{i.name}: {i.qty} pcs</p>)}
              {isManager(user) && <Btn size="sm" v="outline" className="mt-2" onClick={() => setModal("return")} data-testid="order-receive-back">Catat barang kembali</Btn>}
            </Card>
          )}
        </div>
      </div>
      {modal === "return" && <ReturnDialog kind="order" doc={o} open onClose={() => setModal("")} onDone={setO} title="Paket kembali / retur" />}
      {modal === "cancel" && <ReturnDialog kind="order" doc={o} open onClose={() => setModal("")} onDone={setO} title="Batalkan pesanan" endpoint={`/orders/${id}/cancel`} cancelMode />}
    </div>
  );
}

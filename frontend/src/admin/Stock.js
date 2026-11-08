import { useState } from "react";
import { BACKEND } from "@/lib/api";
import { fmtDateTime, monthStart, today } from "@/lib/fmt";
import { Btn, Input, Select, Table, Td, PageHead, Badge } from "@/admin/ui";
import { useLoad } from "@/admin/tx";

const KIND = { stok_awal: "Stok awal", masuk: "Barang masuk", keluar_pekerjaan: "Keluar: pekerjaan", keluar_penjualan: "Keluar: penjualan",
  keluar_pesanan_wa: "Keluar: pesanan WA", retur_masuk: "Retur masuk", rusak: "Rusak", pemakaian_internal: "Pemakaian internal",
  opname: "Stok opname", koreksi: "Koreksi", pembatalan_otomatis: "Batal otomatis" };

export function Mutations() {
  const [f, setF] = useState({ start: monthStart(), end: today(), kind: "" });
  const [rows] = useLoad(`/stock/mutations?start=${f.start}&end=${f.end}${f.kind ? `&kind=${f.kind}` : ""}`);
  return (
    <div>
      <PageHead title="Mutasi Stok" sub="Riwayat tidak dapat dihapus. Setiap perubahan stok tercatat di sini." actions={
        <a href={`${BACKEND}/api/reports/export?kind=mutations&start=${f.start}&end=${f.end}`}><Btn v="outline" data-testid="mutations-export">Ekspor CSV</Btn></a>} />
      <div className="mb-4 flex flex-wrap gap-2">
        <Input type="date" className="w-44" value={f.start} onChange={(e) => setF({ ...f, start: e.target.value })} data-testid="mutations-start" />
        <Input type="date" className="w-44" value={f.end} onChange={(e) => setF({ ...f, end: e.target.value })} data-testid="mutations-end" />
        <Select className="w-56" value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })} data-testid="mutations-kind"><option value="">Semua jenis</option>{Object.entries(KIND).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select>
      </div>
      <Table head={["Waktu", "Barang", "Jenis", "Sebelum", "Selisih", "Sesudah", "Alasan", "Referensi", "Petugas"]} testid="mutations-table" empty={rows && !rows.length && "Tidak ada mutasi."}>
        {(rows || []).map((m) => (
          <tr key={m.id}><Td className="whitespace-nowrap">{fmtDateTime(m.created_at)}</Td><Td>{m.item_name}<div className="text-xs text-slate-500">{m.sku}</div></Td>
            <Td><Badge>{KIND[m.kind] || m.kind}</Badge></Td><Td className="font-mono-num">{m.qty_before}</Td>
            <Td className={`font-mono-num font-bold ${m.delta < 0 ? "text-red-700" : "text-emerald-700"}`}>{m.delta > 0 ? "+" : ""}{m.delta}</Td>
            <Td className="font-mono-num">{m.qty_after}</Td><Td>{m.reason}</Td><Td>{m.ref_no || "-"}</Td><Td>{m.user_name}</Td></tr>
        ))}
      </Table>
    </div>
  );
}

const SRC = { stok: "Dari stok layak jual (stok −)", retur: "Retur pelanggan (tidak masuk stok)", klaim: "Barang lama klaim garansi" };

export function Damaged() {
  const [rows] = useLoad("/damaged");
  return (
    <div>
      <PageHead title="Barang Rusak" sub="Barang rusak dari stok mengurangi stok layak jual melalui mutasi. Catat lewat Master Barang → aksi “Catat barang rusak”." />
      <Table head={["Waktu", "Barang", "Jumlah", "Sumber", "Alasan", "Referensi", "Petugas"]} testid="damaged-table" empty={rows && !rows.length && "Belum ada barang rusak."}>
        {(rows || []).map((d) => (
          <tr key={d.id}><Td className="whitespace-nowrap">{fmtDateTime(d.created_at)}</Td><Td>{d.item_name}</Td><Td className="font-mono-num">{d.qty}</Td>
            <Td>{SRC[d.source]}</Td><Td>{d.reason}</Td><Td>{d.ref_no || "-"}</Td><Td>{d.user_name}</Td></tr>
        ))}
      </Table>
    </div>
  );
}

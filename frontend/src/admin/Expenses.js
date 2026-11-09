import { useState } from "react";
import { api } from "@/lib/api";
import { rp, fmtDate, monthStart, today } from "@/lib/fmt";
import { useAuth, isOwner } from "@/context/AuthContext";
import { Btn, Field, Input, NumInput, Select, Card, Table, Td, PageHead } from "@/admin/ui";
import { useLoad, act } from "@/admin/tx";

export const CATS = ["Gaji", "Listrik", "Internet", "Biaya bengkel", "Peralatan", "Transportasi", "Ongkir dibayar bengkel", "Lainnya"];

export default function Expenses() {
  const { user } = useAuth();
  const [r, setR] = useState({ start: monthStart(), end: today() });
  const [rows, load] = useLoad(`/expenses?start=${r.start}&end=${r.end}`);
  const [f, setF] = useState({ date: today(), category: "Listrik", amount: "", method: "tunai", note: "" });
  const save = async () => { const x = await act(() => api.post("/expenses", { ...f, amount: Number(f.amount) }), "Biaya dicatat"); if (x) { setF({ ...f, amount: "", note: "" }); load(); } };
  const voidIt = async (e) => { const reason = window.prompt("Alasan pembatalan biaya?"); if (reason) { await act(() => api.post(`/expenses/${e.id}/void`, { reason }), "Dibatalkan"); load(); } };
  return (
    <div>
      <PageHead title="Biaya Operasional" sub="Tempat milik sendiri — biaya sewa tidak dihitung otomatis." />
      <Card title="Catat biaya" className="mb-4">
        <div className="grid gap-2 sm:grid-cols-6 sm:items-end">
          <Field label="Tanggal"><Input type="date" value={f.date} onChange={(e) => setF({ ...f, date: e.target.value })} data-testid="expense-date" /></Field>
          <Field label="Kategori"><Select value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })} data-testid="expense-category">{CATS.map((c) => <option key={c}>{c}</option>)}</Select></Field>
          <Field label="Jumlah"><NumInput value={f.amount} onChange={(v) => setF({ ...f, amount: v })} data-testid="expense-amount" /></Field>
          <Field label="Metode"><Select value={f.method} onChange={(e) => setF({ ...f, method: e.target.value })}><option value="tunai">Tunai</option><option value="transfer">Transfer</option></Select></Field>
          <Field label="Catatan"><Input value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} data-testid="expense-note" /></Field>
          <Btn onClick={save} disabled={!f.amount} data-testid="expense-save">Simpan</Btn>
        </div>
      </Card>
      <div className="mb-3 flex gap-2">
        <Input type="date" className="w-44" value={r.start} onChange={(e) => setR({ ...r, start: e.target.value })} />
        <Input type="date" className="w-44" value={r.end} onChange={(e) => setR({ ...r, end: e.target.value })} />
        <p className="self-center text-sm">Total: <b className="font-mono-num" data-testid="expense-total">{rp((rows || []).reduce((s, e) => s + e.amount, 0))}</b></p>
      </div>
      <Table head={["Tanggal", "Kategori", "Jumlah", "Metode", "Catatan", "Petugas", ""]} testid="expense-table" empty={rows && !rows.length && "Belum ada biaya."}>
        {(rows || []).map((e) => (
          <tr key={e.id}><Td>{fmtDate(e.date)}</Td><Td>{e.category}</Td><Td className="font-mono-num">{rp(e.amount)}</Td><Td>{e.method}</Td><Td>{e.note}</Td><Td>{e.user_name}</Td>
            <Td>{isOwner(user) && <Btn size="sm" v="ghost" onClick={() => voidIt(e)} data-testid={`expense-void-${e.id}`}>Batalkan</Btn>}</Td></tr>
        ))}
      </Table>
    </div>
  );
}

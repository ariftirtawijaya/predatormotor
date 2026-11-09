import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { rp, fmtDateTime, KIND_LABEL, KIND_PATH } from "@/lib/fmt";
import { Btn, Field, Input, Select, Card, Table, Td, PageHead, Badge } from "@/admin/ui";
import { useLoad, act } from "@/admin/tx";
import { DeleteDialog } from "@/admin/DeleteDialog";
import { useAuth } from "@/context/AuthContext";
import { Trash2 } from "lucide-react";

export function Discounts() {
  const [rows, load] = useLoad("/discounts/pending");
  const decide = async (r, approve) => { await act(() => api.post(`/tx/${r.kind}/${r.id}/discount/decide`, { approve }), approve ? "Disetujui" : "Ditolak"); load(); };
  return (
    <div>
      <PageHead title="Persetujuan Diskon" sub="Diskon hanya berlaku setelah disetujui owner. Keputusan tercatat di audit log." />
      <Table head={["Jenis", "No", "Pelanggan", "Subtotal", "Diskon", "Alasan", "Diajukan", ""]} testid="discount-table" empty={rows && !rows.length && "Tidak ada permintaan diskon."}>
        {(rows || []).map((r) => (
          <tr key={r.id}><Td>{KIND_LABEL[r.kind]}</Td><Td><Link to={`/admin/${KIND_PATH[r.kind]}/${r.id}`} className="font-semibold text-sky-800 underline">{r.no}</Link></Td><Td>{r.customer}</Td>
            <Td className="font-mono-num">{rp(r.subtotal)}</Td><Td className="font-mono-num font-bold">{rp(r.discount.amount)}</Td><Td>{r.discount.reason}</Td>
            <Td>{r.discount.requested_by}<div className="text-xs text-slate-500">{fmtDateTime(r.discount.requested_at)}</div></Td>
            <Td className="whitespace-nowrap"><Btn size="sm" v="success" onClick={() => decide(r, true)} data-testid={`discount-approve-${r.no}`}>Setujui</Btn> <Btn size="sm" v="danger" onClick={() => decide(r, false)} data-testid={`discount-reject-${r.no}`}>Tolak</Btn></Td></tr>
        ))}
      </Table>
    </div>
  );
}

export function UsersPage() {
  const { user: me } = useAuth();
  const [rows, load] = useLoad("/users");
  const [del, setDel] = useState(null);
  const lastOwner = (u) => u.role === "owner" && (rows || []).filter((x) => x.role === "owner" && x.active).length <= 1;
  const [f, setF] = useState({ email: "", name: "", role: "kasir", password: "" });
  const create = async () => { const r = await act(() => api.post("/users", f), "Pengguna dibuat"); if (r) { setF({ email: "", name: "", role: "kasir", password: "" }); load(); } };
  const patch = async (u, body, msg) => { await act(() => api.patch(`/users/${u.id}`, body), msg); load(); };
  return (
    <div>
      <PageHead title="Pengguna & Hak Akses" sub="Owner: semua modul. Admin: barang, stok, paket, CMS. Kasir: pelanggan, pekerjaan, penjualan, pesanan WA, pembayaran." />
      <Card title="Tambah pengguna" className="mb-4">
        <div className="grid gap-2 sm:grid-cols-5 sm:items-end">
          <Field label="Nama"><Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} data-testid="user-form-name" /></Field>
          <Field label="Email"><Input type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} data-testid="user-form-email" /></Field>
          <Field label="Peran"><Select value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })} data-testid="user-form-role"><option value="kasir">Kasir</option><option value="admin">Admin</option><option value="owner">Owner</option></Select></Field>
          <Field label="Password (min 8)"><Input type="password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} data-testid="user-form-password" /></Field>
          <Btn onClick={create} disabled={!f.email || !f.name || f.password.length < 8} data-testid="user-form-save">Simpan</Btn>
        </div>
      </Card>
      <Table head={["Nama", "Email", "Peran", "Status", "Aksi"]} testid="users-table">
        {(rows || []).map((u) => (
          <tr key={u.id}><Td>{u.name}</Td><Td>{u.email}</Td><Td><Badge>{u.role}</Badge></Td><Td>{u.active ? "Aktif" : "Nonaktif"}</Td>
            <Td className="whitespace-nowrap">
              <Btn size="sm" v="outline" onClick={() => patch(u, { active: !u.active }, "Status diubah")} data-testid={`user-toggle-${u.email}`}>{u.active ? "Nonaktifkan" : "Aktifkan"}</Btn>{" "}
              <Btn size="sm" v="outline" onClick={() => { const p = window.prompt("Password baru (min 8 karakter)"); if (p) patch(u, { password: p }, "Password direset"); }} data-testid={`user-reset-${u.email}`}>Reset password</Btn>{" "}
              <Btn size="sm" v="ghost" className="text-red-700" onClick={() => setDel(u)} data-testid={`user-delete-${u.email}`}><Trash2 className="h-3.5 w-3.5" />Hapus</Btn>
            </Td></tr>
        ))}
      </Table>
      {del && <DeleteDialog kind="user" id={del.id} url={`/users/${del.id}`} onClose={() => setDel(null)} onDone={load}
        onDeactivate={del.active && del.id !== me.id && !lastOwner(del) ? () => api.patch(`/users/${del.id}`, { active: false }) : null} />}
    </div>
  );
}

export function AuditPage() {
  const [rows] = useLoad("/audit?limit=500");
  const [q, setQ] = useState("");
  const list = (rows || []).filter((r) => !q || JSON.stringify(r).toLowerCase().includes(q.toLowerCase()));
  const s = (o) => (o ? JSON.stringify(o).slice(0, 220) : "");
  return (
    <div>
      <PageHead title="Audit Log" sub="Catatan perubahan penting: siapa, kapan, apa, sebelum/sesudah, dan alasan." />
      <Input className="mb-4 max-w-sm" placeholder="Filter…" value={q} onChange={(e) => setQ(e.target.value)} data-testid="audit-filter" />
      <Table head={["Waktu", "Pengguna", "Tindakan", "Data", "Sebelum", "Sesudah", "Alasan"]} testid="audit-table">
        {list.map((r) => (
          <tr key={r.id}><Td className="whitespace-nowrap">{fmtDateTime(r.created_at)}</Td><Td>{r.user_name}<div className="text-xs text-slate-500">{r.role}</div></Td>
            <Td><Badge>{r.action}</Badge></Td><Td className="text-xs">{r.ref_type} {r.ref_id?.slice(0, 8)}</Td>
            <Td className="max-w-xs break-all text-xs text-slate-600">{s(r.before)}</Td><Td className="max-w-xs break-all text-xs text-slate-600">{s(r.after)}</Td><Td>{r.reason}</Td></tr>
        ))}
      </Table>
    </div>
  );
}

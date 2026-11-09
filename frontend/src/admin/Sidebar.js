import { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { LayoutDashboard, ShoppingCart, Wrench, MessageCircle, Car, Receipt, Package, Boxes, ArrowLeftRight, AlertTriangle,
  Wallet, Globe, Image, BadgePercent, BarChart3, Users, ScrollText, Settings, ChevronDown, ClipboardList, Warehouse, Briefcase } from "lucide-react";
import { isManager, isOwner } from "@/context/AuthContext";

export const GROUPS = [
  { key: "transaksi", label: "Transaksi", icon: ClipboardList, items: [
    { to: "/admin/kasir", label: "Kasir Penjualan", icon: ShoppingCart },
    { to: "/admin/pekerjaan", label: "Pekerjaan Bengkel", icon: Wrench },
    { to: "/admin/pesanan", label: "Pesanan WhatsApp", icon: MessageCircle },
    { to: "/admin/penjualan", label: "Nota Penjualan", icon: Receipt },
    { to: "/admin/diskon", label: "Persetujuan Diskon", icon: BadgePercent, owner: true }] },
  { key: "stok", label: "Data Bengkel & Stok", icon: Warehouse, items: [
    { to: "/admin/kendaraan", label: "Riwayat Kendaraan", icon: Car },
    { to: "/admin/barang", label: "Master Barang", icon: Boxes, mgr: true },
    { to: "/admin/paket", label: "Paket", icon: Package, mgr: true },
    { to: "/admin/stok", label: "Mutasi Stok", icon: ArrowLeftRight, mgr: true },
    { to: "/admin/rusak", label: "Barang Rusak", icon: AlertTriangle, mgr: true }] },
  { key: "website", label: "Website", icon: Globe, items: [
    { to: "/admin/cms", label: "CMS Website", icon: Globe, mgr: true },
    { to: "/admin/media", label: "Media", icon: Image, mgr: true }] },
  { key: "manajemen", label: "Manajemen", icon: Briefcase, items: [
    { to: "/admin/biaya", label: "Biaya Operasional", icon: Wallet, mgr: true },
    { to: "/admin/laporan", label: "Laporan", icon: BarChart3, owner: true },
    { to: "/admin/pengguna", label: "Pengguna", icon: Users, owner: true },
    { to: "/admin/audit", label: "Audit Log", icon: ScrollText, owner: true },
    { to: "/admin/pengaturan", label: "Pengaturan", icon: Settings, owner: true }] },
];

const allowed = (user) => (n) => (n.owner ? isOwner(user) : n.mgr ? isManager(user) : true);
const inPath = (path, to) => path === to || path.startsWith(`${to}/`);
const LINK = ({ isActive }) => `flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors ${isActive ? "bg-sky-50 font-semibold text-sky-800 ring-1 ring-sky-200" : "text-slate-700 hover:bg-slate-100"}`;
const slug = (to) => to.split("/")[2] || "dashboard";

function Group({ g, items, path, onNav }) {
  const active = items.some((n) => inPath(path, n.to));
  const [open, setOpen] = useState(active);
  useEffect(() => { if (active) setOpen(true); }, [active]);
  return (
    <div data-testid={`nav-group-${g.key}`}>
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
        className={`flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-xs font-bold uppercase tracking-wide transition-colors hover:bg-slate-100 ${active ? "text-sky-800" : "text-slate-500"}`}
        data-testid={`nav-group-toggle-${g.key}`}>
        <g.icon className="h-4 w-4" /><span className="flex-1 text-left">{g.label}</span>
        <ChevronDown className={`h-4 w-4 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="mb-1 ml-3 flex flex-col gap-0.5 border-l border-slate-200 pl-2">
          {items.map((n) => (
            <NavLink key={n.to} to={n.to} onClick={onNav} className={LINK} data-testid={`nav-${slug(n.to)}`}><n.icon className="h-4 w-4" />{n.label}</NavLink>
          ))}
        </div>
      )}
    </div>
  );
}

export function Sidebar({ user, onNav }) {
  const { pathname } = useLocation();
  return (
    <nav className="flex flex-col gap-1 p-3" data-testid="admin-sidebar">
      <NavLink to="/admin" end onClick={onNav} className={LINK} data-testid="nav-dashboard"><LayoutDashboard className="h-4 w-4" />Dashboard</NavLink>
      {GROUPS.map((g) => {
        const items = g.items.filter(allowed(user));
        return items.length ? <Group key={g.key} g={g} items={items} path={pathname} onNav={onNav} /> : null;
      })}
    </nav>
  );
}

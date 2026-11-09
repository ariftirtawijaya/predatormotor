import { useState } from "react";
import { Routes, Route, NavLink, Navigate, useNavigate } from "react-router-dom";
import { LayoutDashboard, ShoppingCart, Wrench, MessageCircle, Car, Receipt, Package, Boxes, ArrowLeftRight, AlertTriangle,
  Wallet, Globe, Image, BadgePercent, BarChart3, Users, ScrollText, Menu, X, LogOut, Settings } from "lucide-react";
import { useAuth, isManager, isOwner } from "@/context/AuthContext";
import Login from "@/admin/Login";
import Dashboard from "@/admin/Dashboard";
import Kasir, { SaleList, SaleDetail } from "@/admin/Sales";
import { JobList, JobNew } from "@/admin/Jobs";
import JobDetail from "@/admin/JobDetail";
import { OrderList, OrderNew } from "@/admin/Orders";
import OrderDetail from "@/admin/OrderDetail";
import { VehicleSearch, VehicleHistory, CustomerHistory } from "@/admin/Vehicles";
import ResetData from "@/admin/ResetData";
import Items from "@/admin/Items";
import Packages from "@/admin/Packages";
import { Mutations, Damaged } from "@/admin/Stock";
import Expenses from "@/admin/Expenses";
import Reports from "@/admin/Reports";
import { Discounts, UsersPage, AuditPage } from "@/admin/OwnerPages";
import CMS from "@/admin/CMS";
import MediaLibrary from "@/admin/MediaLibrary";
import PrintPage from "@/admin/PrintPage";
import WhatsAppSettings from "@/admin/WhatsAppSettings";

const NAV = [
  { to: "/admin", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/admin/kasir", label: "Kasir Penjualan", icon: ShoppingCart },
  { to: "/admin/pekerjaan", label: "Pekerjaan Bengkel", icon: Wrench },
  { to: "/admin/pesanan", label: "Pesanan WhatsApp", icon: MessageCircle },
  { to: "/admin/kendaraan", label: "Riwayat Kendaraan", icon: Car },
  { to: "/admin/penjualan", label: "Nota Penjualan", icon: Receipt },
  { to: "/admin/barang", label: "Master Barang", icon: Boxes, mgr: true },
  { to: "/admin/paket", label: "Paket", icon: Package, mgr: true },
  { to: "/admin/stok", label: "Mutasi Stok", icon: ArrowLeftRight, mgr: true },
  { to: "/admin/rusak", label: "Barang Rusak", icon: AlertTriangle, mgr: true },
  { to: "/admin/biaya", label: "Biaya Operasional", icon: Wallet, mgr: true },
  { to: "/admin/cms", label: "CMS Website", icon: Globe, mgr: true },
  { to: "/admin/media", label: "Media", icon: Image, mgr: true },
  { to: "/admin/diskon", label: "Persetujuan Diskon", icon: BadgePercent, owner: true },
  { to: "/admin/laporan", label: "Laporan", icon: BarChart3, owner: true },
  { to: "/admin/pengguna", label: "Pengguna", icon: Users, owner: true },
  { to: "/admin/audit", label: "Audit Log", icon: ScrollText, owner: true },
  { to: "/admin/pengaturan/whatsapp", label: "Pengaturan · WhatsApp", icon: Settings, owner: true },
  { to: "/admin/reset-data", label: "Pengaturan · Reset Data", icon: Settings, owner: true },
];

const ROLE = { owner: "Owner", admin: "Admin", kasir: "Kasir" };

function Sidebar({ user, onNav }) {
  const items = NAV.filter((n) => (n.owner ? isOwner(user) : n.mgr ? isManager(user) : true));
  return (
    <nav className="flex flex-col gap-0.5 p-3">
      {items.map((n) => (
        <NavLink key={n.to} to={n.to} end={n.end} onClick={onNav} data-testid={`nav-${n.to.split("/")[2] || "dashboard"}`}
          className={({ isActive }) => `flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors ${isActive ? "bg-sky-50 text-sky-800 ring-1 ring-sky-200" : "text-slate-700 hover:bg-slate-100"}`}>
          <n.icon className="h-4 w-4" />{n.label}
        </NavLink>
      ))}
    </nav>
  );
}

function Shell({ user, children }) {
  const [open, setOpen] = useState(false);
  const { logout } = useAuth();
  const nav = useNavigate();
  return (
    <div className="min-h-screen bg-slate-50 font-admin text-slate-900">
      <header className="no-print sticky top-0 z-30 flex h-14 items-center justify-between border-b border-slate-200 bg-white px-4">
        <div className="flex items-center gap-3">
          <button className="lg:hidden" onClick={() => setOpen(!open)} data-testid="sidebar-toggle">{open ? <X /> : <Menu />}</button>
          <span className="font-display text-lg font-extrabold tracking-tight">PREDATOR<span className="text-sky-700"> Autolight</span></span>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <a href="/" target="_blank" rel="noreferrer" className="hidden text-slate-600 hover:text-slate-900 sm:block" data-testid="open-public-site">Lihat website</a>
          <span className="hidden sm:block" data-testid="current-user">{user.name} · <b>{ROLE[user.role]}</b></span>
          <button onClick={async () => { await logout(); nav("/admin/login"); }} className="flex items-center gap-1 rounded-md border border-slate-300 px-2 py-1 hover:bg-slate-100" data-testid="logout-button">
            <LogOut className="h-4 w-4" /> Keluar
          </button>
        </div>
      </header>
      <div className="flex">
        <aside className={`no-print fixed inset-y-14 left-0 z-20 w-64 overflow-y-auto border-r border-slate-200 bg-white transition-transform lg:sticky lg:top-14 lg:h-[calc(100vh-3.5rem)] lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}>
          <Sidebar user={user} onNav={() => setOpen(false)} />
        </aside>
        <main className="min-w-0 flex-1 p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}

const Guard = ({ ok, children }) => (ok ? children : <div className="rounded-md border border-red-200 bg-red-50 p-6 text-red-900">Anda tidak memiliki akses ke halaman ini.</div>);

export default function AdminApp() {
  const { user } = useAuth();
  if (user === null) return <div className="p-8 font-admin text-slate-600">Memeriksa sesi…</div>;
  return (
    <Routes>
      <Route path="login" element={user ? <Navigate to="/admin" /> : <Login />} />
      <Route path="cetak/:kind/:id" element={user ? <PrintPage /> : <Navigate to="/admin/login" />} />
      <Route path="*" element={!user ? <Navigate to="/admin/login" /> : (
        <Shell user={user}>
          <Routes>
            <Route index element={<Dashboard />} />
            <Route path="kasir" element={<Kasir />} />
            <Route path="pekerjaan" element={<JobList />} />
            <Route path="pekerjaan/baru" element={<JobNew />} />
            <Route path="pekerjaan/:id" element={<JobDetail />} />
            <Route path="pesanan" element={<OrderList />} />
            <Route path="pesanan/baru" element={<OrderNew />} />
            <Route path="pesanan/:id" element={<OrderDetail />} />
            <Route path="penjualan" element={<SaleList />} />
            <Route path="penjualan/:id" element={<SaleDetail />} />
            <Route path="kendaraan" element={<VehicleSearch />} />
            <Route path="kendaraan/:id" element={<VehicleHistory />} />
            <Route path="pelanggan/:id" element={<CustomerHistory />} />
            <Route path="barang" element={<Guard ok={isManager(user)}><Items /></Guard>} />
            <Route path="paket" element={<Guard ok={isManager(user)}><Packages /></Guard>} />
            <Route path="stok" element={<Guard ok={isManager(user)}><Mutations /></Guard>} />
            <Route path="rusak" element={<Guard ok={isManager(user)}><Damaged /></Guard>} />
            <Route path="biaya" element={<Guard ok={isManager(user)}><Expenses /></Guard>} />
            <Route path="cms" element={<Guard ok={isManager(user)}><CMS /></Guard>} />
            <Route path="media" element={<Guard ok={isManager(user)}><MediaLibrary /></Guard>} />
            <Route path="diskon" element={<Guard ok={isOwner(user)}><Discounts /></Guard>} />
            <Route path="laporan" element={<Guard ok={isOwner(user)}><Reports /></Guard>} />
            <Route path="pengguna" element={<Guard ok={isOwner(user)}><UsersPage /></Guard>} />
            <Route path="audit" element={<Guard ok={isOwner(user)}><AuditPage /></Guard>} />
            <Route path="pengaturan/whatsapp" element={<Guard ok={isOwner(user)}><WhatsAppSettings /></Guard>} />
            <Route path="reset-data" element={<Guard ok={isOwner(user)}><ResetData /></Guard>} />
            <Route path="*" element={<p>Halaman tidak ditemukan.</p>} />
          </Routes>
        </Shell>
      )} />
    </Routes>
  );
}

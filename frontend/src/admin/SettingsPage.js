import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { MessageCircle, Trash2 } from "lucide-react";
import { PageHead } from "@/admin/ui";
import WhatsAppSettings from "@/admin/WhatsAppSettings";
import ResetData from "@/admin/ResetData";

const TABS = [
  { to: "whatsapp", label: "WhatsApp", icon: MessageCircle, desc: "Token Fonnte & nomor admin" },
  { to: "reset-data", label: "Reset Data", icon: Trash2, desc: "Kosongkan data uji (owner)" },
];

export default function SettingsPage() {
  return (
    <div data-testid="settings-page">
      <PageHead title="Pengaturan" sub="Pilih bagian yang ingin diatur. Hanya owner." />
      <div className="mb-6 flex flex-wrap gap-2" role="tablist">
        {TABS.map((t) => (
          <NavLink key={t.to} to={`/admin/pengaturan/${t.to}`} data-testid={`settings-tab-${t.to}`}
            className={({ isActive }) => `flex min-w-[200px] items-center gap-3 rounded-md border px-4 py-3 text-left transition-colors ${isActive ? "border-sky-300 bg-sky-50 text-sky-900" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"}`}>
            <t.icon className="h-5 w-5" /><span><b className="block text-sm">{t.label}</b><span className="text-xs text-slate-500">{t.desc}</span></span>
          </NavLink>
        ))}
      </div>
      <Routes>
        <Route index element={<Navigate to="whatsapp" replace />} />
        <Route path="whatsapp" element={<WhatsAppSettings />} />
        <Route path="reset-data" element={<ResetData />} />
        <Route path="*" element={<Navigate to="/admin/pengaturan/whatsapp" replace />} />
      </Routes>
    </div>
  );
}

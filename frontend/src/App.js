import { lazy, Suspense, useEffect } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider } from "@/context/AuthContext";
import PublicLayout from "@/public/PublicLayout";
import Home from "@/public/Home";
import { Profil, Layanan, Katalog, Galeri, Kontak, CustomPage } from "@/public/Pages";
import NotaPublic from "@/public/NotaPublic";

const AdminApp = lazy(() => import("@/admin/AdminApp"));
const SITE_TITLE = "Predator Autolight Bojonegoro";

// Admin & nota tidak punya judul CMS; halaman publik diatur useSeo (judul CMS tetap diutamakan).
function DefaultTitle() {
  const { pathname } = useLocation();
  useEffect(() => {
    if (pathname.startsWith("/admin") || pathname.startsWith("/nota/")) document.title = SITE_TITLE;
  }, [pathname]);
  return null;
}

function App() {
  return (
    <BrowserRouter>
      <DefaultTitle />
      <Toaster richColors position="top-right" />
      <Routes>
        <Route path="/admin/*" element={
          <AuthProvider>
            <Suspense fallback={<div className="p-8 text-slate-600">Memuat…</div>}><AdminApp /></Suspense>
          </AuthProvider>
        } />
        <Route path="/nota/:token" element={<NotaPublic />} />
        <Route element={<PublicLayout />}>
          <Route path="/" element={<Home />} />
          <Route path="/profil" element={<Profil />} />
          <Route path="/layanan" element={<Layanan />} />
          <Route path="/katalog" element={<Katalog />} />
          <Route path="/galeri" element={<Galeri />} />
          <Route path="/kontak" element={<Kontak />} />
          <Route path="/p/:slug" element={<CustomPage />} />
          <Route path="*" element={<CustomPage notFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;

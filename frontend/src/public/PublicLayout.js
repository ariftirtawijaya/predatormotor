import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { Menu, X, MapPin, Clock, Phone } from "lucide-react";
import { api, mediaUrl } from "@/lib/api";
import { SiteCtx, SLink, useWa, Img } from "@/public/bits";

const PAGE_SEO = { "/": "home", "/profil": "profil", "/layanan": "layanan", "/katalog": "katalog", "/galeri": "galeri", "/kontak": "kontak" };

function setMeta(name, content, prop) {
  const sel = prop ? `meta[property="${name}"]` : `meta[name="${name}"]`;
  let el = document.head.querySelector(sel);
  if (!el) {
    el = document.createElement("meta");
    el.setAttribute(prop ? "property" : "name", name);
    document.head.appendChild(el);
  }
  el.setAttribute("content", content || "");
}

function readableOn(hex) {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.3 ? "#0b1220" : "#ffffff";
}

function useSeo(site, path) {
  useEffect(() => {
    if (!site) return;
    const id = site.identity;
    const seo = (site.seo?.pages || []).find((p) => p.page === PAGE_SEO[path]) || {};
    const title = seo.title || (path === "/" ? `${id.name} — ${id.slogan}` : id.name);
    document.title = title;
    setMeta("description", seo.description || id.short_desc);
    setMeta("og:title", title, true);
    setMeta("og:description", seo.description || id.short_desc, true);
    setMeta("og:image", mediaUrl(seo.og_image || id.default_image || id.logo), true);
    setMeta("robots", seo.noindex || site.preview ? "noindex,nofollow" : "index,follow");
    document.documentElement.style.setProperty("--site-accent", id.accent_color || "#f59e0b");
    document.documentElement.style.setProperty("--site-accent-fg", readableOn(id.accent_color || "#f59e0b"));
    if (id.favicon) {
      let l = document.head.querySelector("link[rel='icon']");
      if (!l) { l = document.createElement("link"); l.rel = "icon"; document.head.appendChild(l); }
      l.href = mediaUrl(id.favicon);
    }
  }, [site, path]);
}

function Nav({ site }) {
  const [open, setOpen] = useState(false);
  const id = site.identity;
  const items = (site.navigation.items || []).filter((i) => i.enabled);
  return (
    <header className="fixed inset-x-0 top-0 z-40 border-b border-slate-200 bg-white/85 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 lg:px-8">
        <SLink href="/" className="flex min-w-0 items-center gap-2.5" testid="site-logo">
          {id.logo ? <Img src={id.logo} alt={id.name} className="h-9 max-w-[140px] object-contain" /> : <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg accent-bg font-display text-sm font-black" data-testid="site-logo-fallback">{(id.name || "P").trim()[0]}</span>}
          <span className="truncate font-display text-base font-extrabold tracking-tight text-slate-900 sm:text-lg">{id.name}</span>
        </SLink>
        <nav className="hidden items-center gap-7 lg:flex">
          {items.map((i, k) => <SLink key={k} href={i.href} className="text-sm font-medium text-slate-600 transition-colors hover:text-slate-900" testid={`site-nav-${k}`}>{i.label}</SLink>)}
          {site.navigation.cta_label && <SLink href={site.navigation.cta_href} className="rounded-full px-5 py-2 text-sm font-bold accent-bg transition-transform hover:-translate-y-0.5" testid="site-nav-cta">{site.navigation.cta_label}</SLink>}
        </nav>
        <button className="text-slate-900 lg:hidden" onClick={() => setOpen(!open)} data-testid="site-menu-toggle" aria-label="Menu">{open ? <X /> : <Menu />}</button>
      </div>
      {open && (
        <div className="border-t border-slate-200 bg-white px-5 py-4 lg:hidden" onClick={() => setOpen(false)}>
          {items.map((i, k) => <SLink key={k} href={i.href} className="block py-3 text-base font-medium text-slate-800" testid={`site-mnav-${k}`}>{i.label}</SLink>)}
        </div>
      )}
    </header>
  );
}

function Footer({ site }) {
  const { identity: id, footer: f, contact: c } = site;
  return (
    <footer className="border-t border-slate-200 bg-slate-50 text-slate-600">
      <div className="mx-auto grid max-w-7xl gap-10 px-5 py-14 md:grid-cols-3 lg:px-8">
        <div>
          <p className="font-display text-xl font-extrabold text-slate-900">{id.name}</p>
          <p className="mt-3 text-sm leading-relaxed">{f.text || id.short_desc}</p>
        </div>
        <div className="space-y-3 text-sm">
          {c.address && <p className="flex gap-2"><MapPin className="h-4 w-4 shrink-0 accent-text" />{c.address}</p>}
          {c.phone && <p className="flex gap-2"><Phone className="h-4 w-4 shrink-0 accent-text" />{c.phone}</p>}
          {(c.hours || []).map((h, i) => <p key={i} className="flex gap-2"><Clock className="h-4 w-4 shrink-0 accent-text" />{h.day}: {h.time}</p>)}
        </div>
        <div className="flex flex-col gap-2 text-sm">
          {(f.links || []).map((l, i) => <SLink key={i} href={l.href} className="hover:text-white">{l.label}</SLink>)}
          {(c.socials || []).map((s, i) => <a key={i} href={s.url} target="_blank" rel="noreferrer" className="hover:text-white">{s.platform}</a>)}
        </div>
      </div>
      <p className="border-t border-slate-200 py-5 text-center text-xs text-slate-500">© {new Date().getFullYear()} {f.copyright || id.name}</p>
    </footer>
  );
}

function WaFloat() {
  const wa = useWa();
  if (!wa) return null;
  return (
    <a href={wa} target="_blank" rel="noreferrer" data-testid="whatsapp-float-button" aria-label="Chat WhatsApp"
      className="fixed bottom-5 right-5 z-50 flex h-14 items-center gap-2 rounded-full bg-[#25D366] px-5 font-bold text-black shadow-[0_10px_40px_-10px_#25D366] transition-transform hover:-translate-y-1">
      <svg viewBox="0 0 24 24" className="h-6 w-6" fill="currentColor"><path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2Zm5.3 14.2c-.2.6-1.3 1.2-1.8 1.2-.5.1-1 .2-3.3-.7-2.8-1.1-4.6-4-4.7-4.2-.1-.2-1.1-1.5-1.1-2.9s.7-2 1-2.3c.2-.3.5-.3.7-.3h.5c.2 0 .4 0 .6.5l.8 2c.1.2.1.4 0 .5l-.3.5-.4.4c-.1.2-.3.3-.1.6.2.3.8 1.3 1.7 2.1 1.2 1 2.1 1.3 2.4 1.5.3.1.5.1.6-.1l.9-1c.2-.3.4-.2.6-.1l1.9.9c.3.1.5.2.5.3.1.2.1.7-.1 1.3Z" /></svg>
      <span className="hidden sm:inline">WhatsApp</span>
    </a>
  );
}

export default function PublicLayout() {
  const loc = useLocation();
  const preview = new URLSearchParams(loc.search).get("preview") === "1";
  const [site, setSite] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    api.get(`/public/site${preview ? "?preview=true" : ""}`).then((r) => setSite(r.data)).catch(() => setErr(preview ? "Pratinjau hanya dapat dibuka oleh admin/owner yang sedang login." : "Gagal memuat halaman."));
  }, [preview]);
  useEffect(() => { window.scrollTo(0, 0); }, [loc.pathname]);
  useSeo(site, loc.pathname);
  if (err) return <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6 text-slate-700">{err}</div>;
  if (!site) return <div className="min-h-screen bg-white" />;
  return (
    <SiteCtx.Provider value={site}>
      <div className="site-light min-h-screen bg-white font-site text-slate-800 selection:bg-[var(--site-accent)] selection:text-black">
        {preview && <div className="fixed inset-x-0 top-16 z-50 bg-amber-400 py-1.5 text-center text-xs font-bold text-black" data-testid="preview-banner">MODE PRATINJAU — menampilkan draft yang belum diterbitkan</div>}
        <Nav site={site} />
        <main className="pt-16"><Outlet /></main>
        <Footer site={site} />
        <WaFloat />
      </div>
    </SiteCtx.Provider>
  );
}

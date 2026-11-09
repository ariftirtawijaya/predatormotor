import { useState } from "react";
import { Wrench, Shield, MessageSquare, Zap, Lightbulb, Clock, Star, Award, ChevronDown, ArrowRight } from "lucide-react";
import { useSite, SLink, Img, Eyebrow, H2, Price } from "@/public/bits";

export const ICONS = { wrench: Wrench, shield: Shield, message: MessageSquare, zap: Zap, bulb: Lightbulb, clock: Clock, star: Star, award: Award };
const wrap = "mx-auto max-w-7xl px-5 lg:px-8";

function HeroVisual({ img, site }) {
  if (img) return <Img src={img} alt={site.identity.name} className="aspect-[4/3] w-full rounded-3xl object-cover shadow-xl shadow-slate-900/10 ring-1 ring-slate-200" />;
  return (
    <div className="hero-empty relative flex aspect-[4/3] w-full items-center justify-center overflow-hidden rounded-3xl ring-1 ring-slate-200" data-testid="hero-empty-visual">
      <div className="flex flex-col items-center gap-4 text-center">
        <span className="flex h-20 w-20 items-center justify-center rounded-2xl bg-white shadow-lg shadow-slate-900/5"><Lightbulb className="h-10 w-10 accent-text" /></span>
        <p className="font-display text-lg font-bold text-slate-800">{site.identity.name}</p>
        <p className="max-w-[16rem] text-sm text-slate-500">{site.identity.slogan}</p>
      </div>
    </div>
  );
}

function Hero({ s, site }) {
  const img = s.image || site.identity.default_image;
  return (
    <section className="hero-light relative overflow-hidden border-b border-slate-200" data-testid="section-hero">
      <div className={`${wrap} grid items-center gap-12 py-16 md:py-24 lg:grid-cols-[1.1fr_1fr]`}>
        <div>
          <Eyebrow>{site.identity.slogan}</Eyebrow>
          <h1 className="rise max-w-3xl font-display text-4xl font-black leading-[1.05] tracking-tight text-slate-900 sm:text-5xl lg:text-6xl" data-testid="hero-title">{s.title}</h1>
          {s.subtitle && <p className="rise mt-6 max-w-xl text-base text-slate-600 md:text-lg" style={{ animationDelay: ".1s" }} data-testid="hero-subtitle">{s.subtitle}</p>}
          <div className="rise mt-9 flex flex-wrap gap-3" style={{ animationDelay: ".2s" }}>
            {s.cta_label && <SLink href={s.cta_link} className="inline-flex items-center gap-2 rounded-full px-7 py-3.5 font-bold accent-bg shadow-lg shadow-slate-900/10 transition-transform hover:-translate-y-0.5" testid="hero-cta-primary">{s.cta_label}<ArrowRight className="h-4 w-4" /></SLink>}
            {s.cta2_label && <SLink href={s.cta2_link} className="rounded-full border border-slate-300 bg-white px-7 py-3.5 font-semibold text-slate-900 transition-colors hover:border-slate-400" testid="hero-cta-secondary">{s.cta2_label}</SLink>}
          </div>
        </div>
        <div className="rise" style={{ animationDelay: ".15s" }}><HeroVisual img={img} site={site} /></div>
      </div>
    </section>
  );
}

function Features({ s }) {
  if (!s.items?.length) return null;
  return (
    <section className={`${wrap} py-20`} data-testid="section-features">
      <H2>{s.title}</H2>
      <div className={`grid gap-5 sm:grid-cols-2 ${s.items.length % 3 === 0 || s.items.length > 4 ? "lg:grid-cols-3" : s.items.length === 4 ? "lg:grid-cols-4" : ""}`}>
        {s.items.map((f, i) => {
          const I = ICONS[f.icon] || Zap;
          return (
            <div key={i} className="group rounded-2xl border border-slate-200 bg-white p-7 shadow-sm transition-[border-color,transform] hover:-translate-y-0.5 hover:border-[var(--site-accent)]" data-testid={`feature-card-${i}`}>
              <span className="mb-5 inline-flex h-12 w-12 items-center justify-center rounded-xl accent-soft"><I className="h-6 w-6 accent-text" /></span>
              <h3 className="font-display text-lg font-bold text-slate-900">{f.title}</h3>
              <p className="mt-2 text-slate-600">{f.desc}</p>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function Stats({ s }) {
  if (!s.items?.length) return null;
  return (
    <section className="border-y border-slate-200 bg-slate-50" data-testid="section-stats">
      <div className={`${wrap} grid grid-cols-2 gap-8 py-14 md:grid-cols-4`}>
        {s.items.map((x, i) => (
          <div key={i}><p className="font-display text-4xl font-black accent-text">{x.value}</p><p className="mt-1 text-sm text-zinc-400">{x.label}</p></div>
        ))}
      </div>
    </section>
  );
}

export function ServiceCard({ s, i }) {
  return (
    <article className="flex flex-col overflow-hidden rounded-2xl border border-white/10 bg-zinc-900/70 transition-transform hover:-translate-y-1" data-testid={`service-card-${i}`}>
      {s.image && <Img src={s.image} alt={s.title} className="aspect-[16/10] w-full object-cover" />}
      <div className="flex flex-1 flex-col p-7">
        <h3 className="font-display text-xl font-bold text-white">{s.title}</h3>
        {s.description && <p className="mt-2 text-sm text-zinc-400">{s.description}</p>}
        {!!s.features?.length && <ul className="mt-5 space-y-2 text-sm text-zinc-300">{s.features.map((f, k) => <li key={k} className="flex gap-2"><span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full accent-bg" />{f.text}</li>)}</ul>}
        {!!s.addons?.length && (
          <div className="mt-5 rounded-lg border border-white/10 p-3 text-xs text-zinc-400">
            <p className="mb-1 font-semibold text-zinc-200">Tambahan pilihan</p>
            {s.addons.map((a, k) => <p key={k} className="flex justify-between gap-2"><span>{a.name}</span><span>{a.price_text}</span></p>)}
          </div>
        )}
        <div className="mt-auto flex items-end justify-between gap-3 pt-6">
          <Price s={s} />
          <SLink href="#whatsapp" waText={`Halo, saya ingin konsultasi tentang ${s.title}`} className="rounded-full border px-4 py-2 text-sm font-semibold accent-border accent-text transition-colors hover:bg-white/5" testid={`service-consult-${i}`}>Konsultasi</SLink>
        </div>
      </div>
    </article>
  );
}

function ServiceGrid({ s, site, kind }) {
  const list = (site.services.items || []).filter((x) => x.featured && (x.kind || "paket") === kind);
  if (!list.length) return null;
  return (
    <section className={`${wrap} py-20`} data-testid={`section-${kind}`}>
      <H2 sub={s.subtitle}>{s.title}</H2>
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">{list.map((x, i) => <ServiceCard key={i} s={x} i={`${kind}-${i}`} />)}</div>
      <SLink href="/layanan" className="mt-8 inline-flex items-center gap-2 font-semibold accent-text">Semua layanan & paket <ArrowRight className="h-4 w-4" /></SLink>
    </section>
  );
}

function Testimonials({ s }) {
  if (!s.items?.length) return null;
  return (
    <section className={`${wrap} py-20`} data-testid="section-testimonials">
      <H2>{s.title}</H2>
      <div className="grid gap-5 md:grid-cols-3">
        {s.items.map((t, i) => (
          <figure key={i} className="rounded-2xl border border-white/10 bg-zinc-900/60 p-7">
            <blockquote className="text-zinc-200">“{t.text}”</blockquote>
            <figcaption className="mt-4 text-sm text-zinc-400"><b className="text-white">{t.name}</b>{t.vehicle && ` · ${t.vehicle}`}</figcaption>
          </figure>
        ))}
      </div>
    </section>
  );
}

function GalleryStrip({ s, site }) {
  const items = (site.gallery.items || []).slice(0, 6);
  if (!items.length) return null;
  return (
    <section className={`${wrap} py-20`} data-testid="section-gallery">
      <H2 sub={s.subtitle}>{s.title}</H2>
      <div className="grid auto-rows-[220px] grid-cols-2 gap-3 md:grid-cols-4">
        {items.map((g, i) => (
          <div key={i} className={`relative overflow-hidden rounded-xl ${i === 0 ? "col-span-2 row-span-2" : ""}`}>
            <Img src={g.after_image || g.image} alt={g.title} className="h-full w-full object-cover transition-transform duration-500 hover:scale-105" />
            <p className="on-dark absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/75 p-3 text-sm font-semibold text-white">{g.title}</p>
          </div>
        ))}
      </div>
      <SLink href="/galeri" className="mt-8 inline-flex items-center gap-2 font-semibold accent-text">Lihat galeri <ArrowRight className="h-4 w-4" /></SLink>
    </section>
  );
}

export function Faq({ s }) {
  const [open, setOpen] = useState(0);
  if (!s.items?.length) return null;
  return (
    <section className={`${wrap} py-20`} data-testid="section-faq">
      <H2>{s.title}</H2>
      <div className="max-w-3xl space-y-3">
        {s.items.map((f, i) => (
          <div key={i} className="rounded-xl border border-slate-200 bg-white px-5 shadow-sm">
            <button onClick={() => setOpen(open === i ? -1 : i)} className="flex w-full items-center justify-between gap-4 py-4 text-left font-semibold text-slate-900" data-testid={`faq-q-${i}`}>
              {f.q}<ChevronDown className={`h-5 w-5 shrink-0 text-slate-500 transition-transform ${open === i ? "rotate-180" : ""}`} />
            </button>
            {open === i && <p className="pb-5 text-slate-600">{f.a}</p>}
          </div>
        ))}
      </div>
    </section>
  );
}

function Cta({ s }) {
  return (
    <section className={`${wrap} pb-20 pt-8`} data-testid="section-cta">
      <div className="relative overflow-hidden rounded-3xl border border-slate-200 accent-soft p-10 md:p-14">
        <h2 className="max-w-2xl font-display text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">{s.title}</h2>
        {s.text && <p className="mt-4 max-w-xl text-slate-700">{s.text}</p>}
        <SLink href="#whatsapp" className="mt-8 inline-flex rounded-full px-7 py-3.5 font-bold accent-bg shadow-lg shadow-slate-900/10" testid="cta-whatsapp">{s.button_label || "Chat WhatsApp"}</SLink>
      </div>
    </section>
  );
}

const MAP = {
  hero: Hero, features: Features, stats: Stats, testimonials: Testimonials, faq: Faq, cta: Cta, gallery: GalleryStrip,
  services: (p) => <ServiceGrid {...p} kind="layanan" />, packages: (p) => <ServiceGrid {...p} kind="paket" />,
};

export default function Home() {
  const site = useSite();
  return (
    <div data-testid="home-page">
      {(site.home.sections || []).filter((s) => s.enabled).map((s, i) => {
        const C = MAP[s.type];
        return C ? <C key={i} s={s} site={site} /> : null;
      })}
    </div>
  );
}

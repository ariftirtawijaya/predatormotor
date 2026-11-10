import { useState } from "react";
import { useParams } from "react-router-dom";
import { MapPin, Clock, Phone, Mail } from "lucide-react";
import { useSite, SLink, Img, Eyebrow, H2, Price, Empty } from "@/public/bits";
import { ServiceCard } from "@/public/Home";

const wrap = "mx-auto max-w-7xl px-5 py-20 lg:px-8";

const Chips = ({ list, val, set, testid }) => (
  <div className="mb-8 flex flex-wrap gap-2" data-testid={testid}>
    {["", ...list].map((c) => (
      <button key={c || "all"} onClick={() => set(c)} className={`rounded-full border px-4 py-1.5 text-sm font-medium transition-colors ${val === c ? "accent-bg border-transparent text-black" : "border-white/15 text-zinc-300 hover:bg-white/5"}`}>{c || "Semua"}</button>
    ))}
  </div>
);

export function Profil() {
  const { profile: p, identity } = useSite();
  return (
    <div className={wrap} data-testid="profile-page">
      <Eyebrow>{identity.name}</Eyebrow>
      <h1 className="font-display text-4xl font-black tracking-tighter text-white sm:text-5xl lg:text-6xl">{p.title}</h1>
      <div className="mt-10 grid gap-10 lg:grid-cols-2">
        <div className="space-y-4 whitespace-pre-line text-lg leading-relaxed text-zinc-300">{p.story || identity.short_desc}</div>
        {p.image && <Img src={p.image} alt={p.title} className="w-full rounded-2xl object-cover" />}
      </div>
      {!!p.highlights?.length && (
        <div className="mt-14 grid gap-4 md:grid-cols-3">
          {p.highlights.map((h, i) => <div key={i} className="rounded-2xl border border-white/10 bg-zinc-900/60 p-6"><p className="font-display text-lg font-bold text-white">{h.title}</p><p className="mt-2 text-zinc-400">{h.text}</p></div>)}
        </div>
      )}
      {!!p.team?.length && (
        <div className="mt-16"><H2>Tim Kami</H2>
          <div className="grid grid-cols-2 gap-5 md:grid-cols-4">
            {p.team.map((t, i) => <div key={i}><Img src={t.photo} alt={t.name} className="aspect-square w-full rounded-xl object-cover" /><p className="mt-3 font-semibold text-white">{t.name}</p><p className="text-sm text-zinc-400">{t.role}</p></div>)}
          </div>
        </div>
      )}
    </div>
  );
}

export function Layanan() {
  const { services } = useSite();
  const items = services.items || [];
  const groups = [["paket", "Paket"], ["layanan", "Layanan"]];
  return (
    <div className={wrap} data-testid="services-page">
      <H2 sub="Harga paket sudah termasuk barang dan jasa pemasangan. Konsultasikan kebutuhan kendaraan anda.">Layanan & Paket</H2>
      {!items.length && <Empty>Daftar layanan sedang disiapkan.</Empty>}
      {groups.map(([k, label]) => {
        const list = items.filter((x) => (x.kind || "paket") === k);
        return list.length ? (
          <div key={k} className="mb-14">
            <h3 className="mb-5 font-display text-xl font-bold text-zinc-200">{label}</h3>
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">{list.map((s, i) => <ServiceCard key={i} s={s} i={`${k}-${i}`} />)}</div>
          </div>
        ) : null;
      })}
    </div>
  );
}

export function Katalog() {
  const { catalog } = useSite();
  const [cat, setCat] = useState("");
  const products = (catalog.products || []).filter((p) => !cat || p.category === cat);
  return (
    <div className={wrap} data-testid="catalog-page">
      <H2 sub="Barang tersedia di bengkel. Tanyakan ketersediaan dan pemasangan lewat WhatsApp.">Katalog</H2>
      <Chips list={(catalog.categories || []).map((c) => c.name)} val={cat} set={setCat} testid="catalog-filter" />
      {!products.length && <Empty>Belum ada produk di kategori ini.</Empty>}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {products.map((p, i) => (
          <article key={i} className="overflow-hidden rounded-2xl border border-white/10 bg-zinc-900/70" data-testid={`catalog-item-${i}`}>
            <div className="relative aspect-square bg-zinc-800">
              <Img src={p.image} alt={p.name} className="h-full w-full object-cover" />
              {p.label && <span className="absolute left-3 top-3 rounded-full px-3 py-1 text-xs font-bold text-black accent-bg">{p.label}</span>}
            </div>
            <div className="p-5">
              <p className="text-xs uppercase tracking-wider text-zinc-500">{p.category}</p>
              <h3 className="mt-1 font-display text-lg font-bold text-white">{p.name}</h3>
              {p.description && <p className="mt-2 line-clamp-3 text-sm text-zinc-400">{p.description}</p>}
              {!!p.variants?.length && <div className="mt-3 space-y-1 text-xs text-zinc-300">{p.variants.map((v, k) => <p key={k} className="flex justify-between"><span>{v.name}</span><span>{v.price_text}</span></p>)}</div>}
              <div className="mt-4 flex items-center justify-between"><Price s={{ price_text: p.price_text }} />
                <SLink href="#whatsapp" waText={`Halo, saya ingin tanya ${p.name}`} className="text-sm font-semibold accent-text" testid={`catalog-ask-${i}`}>Tanya</SLink></div>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

function GalleryItem({ g, i }) {
  const [after, setAfter] = useState(true);
  const ba = g.before_image && g.after_image;
  const src = ba ? (after ? g.after_image : g.before_image) : g.image || g.after_image;
  return (
    <figure className="overflow-hidden rounded-2xl border border-white/10 bg-zinc-900/70" data-testid={`gallery-item-${i}`}>
      <div className="relative aspect-[4/3]">
        <Img src={src} alt={g.title} className="h-full w-full object-cover" />
        {ba && (
          <div className="on-dark absolute bottom-3 left-3 flex rounded-full bg-black/70 p-1 text-xs font-bold backdrop-blur">
            <button onClick={() => setAfter(false)} className={`rounded-full px-3 py-1 ${!after ? "accent-bg text-black" : "text-white"}`}>Sebelum</button>
            <button onClick={() => setAfter(true)} className={`rounded-full px-3 py-1 ${after ? "accent-bg text-black" : "text-white"}`}>Sesudah</button>
          </div>
        )}
      </div>
      <figcaption className="p-5"><p className="font-display font-bold text-white">{g.title}</p>{g.description && <p className="mt-1 text-sm text-zinc-400">{g.description}</p>}</figcaption>
    </figure>
  );
}

export function Galeri() {
  const { gallery } = useSite();
  const [alb, setAlb] = useState("");
  const items = (gallery.items || []).filter((g) => !alb || g.album === alb);
  return (
    <div className={wrap} data-testid="gallery-page">
      <H2 sub="Dokumentasi pekerjaan yang dipublikasikan dengan izin pelanggan.">Galeri Hasil Pekerjaan</H2>
      <Chips list={(gallery.albums || []).map((a) => a.name)} val={alb} set={setAlb} testid="gallery-filter" />
      {!items.length && <Empty>Belum ada foto yang dipublikasikan.</Empty>}
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">{items.map((g, i) => <GalleryItem key={i} g={g} i={i} />)}</div>
    </div>
  );
}

export function Kontak() {
  const { contact: c } = useSite();
  const Row = ({ icon: I, children }) => <p className="flex gap-3 text-zinc-300"><I className="mt-0.5 h-5 w-5 shrink-0 accent-text" /><span>{children}</span></p>;
  return (
    <div className={wrap} data-testid="contact-page">
      <H2>Kontak & Lokasi</H2>
      <div className="grid gap-10 lg:grid-cols-2">
        <div className="space-y-5">
          {c.address ? <Row icon={MapPin}>{c.address}</Row> : <p className="text-zinc-500">Alamat belum diisi.</p>}
          {c.phone && <Row icon={Phone}>{c.phone}</Row>}
          {c.email && <Row icon={Mail}>{c.email}</Row>}
          {!!c.hours?.length && <div className="rounded-xl border border-white/10 p-5"><p className="mb-3 flex items-center gap-2 font-semibold text-white"><Clock className="h-4 w-4 accent-text" />Jam Buka</p>
            {c.hours.map((h, i) => <p key={i} className="flex justify-between py-1 text-sm text-zinc-300"><span>{h.day}</span><span>{h.time}</span></p>)}</div>}
          <div className="flex flex-wrap gap-3">
            {c.whatsapp && <SLink href="#whatsapp" className="rounded-full px-6 py-3 font-bold text-black accent-bg" testid="contact-whatsapp">Chat WhatsApp</SLink>}
            {c.map_link && <a href={c.map_link} target="_blank" rel="noreferrer" className="rounded-full border border-white/20 px-6 py-3 font-semibold text-white" data-testid="contact-map-link">Buka di Google Maps</a>}
          </div>
          <div className="flex flex-wrap gap-4 text-sm">{(c.socials || []).map((s, i) => <a key={i} href={s.url} target="_blank" rel="noreferrer" className="text-zinc-300 underline-offset-4 hover:underline">{s.platform}</a>)}</div>
        </div>
        {c.map_embed && <iframe title="Peta lokasi" src={c.map_embed} className="h-80 w-full rounded-2xl border border-white/10 lg:h-full" loading="lazy" referrerPolicy="no-referrer-when-downgrade" />}
      </div>
    </div>
  );
}

export function CustomPage({ notFound }) {
  const { slug } = useParams();
  const { pages } = useSite();
  const p = !notFound && (pages.items || []).find((x) => x.slug === slug);
  if (!p) return <div className={wrap}><H2>Halaman tidak ditemukan</H2><SLink href="/" className="accent-text">Kembali ke beranda</SLink></div>;
  return (
    <article className={`${wrap} max-w-4xl`} data-testid="custom-page">
      <h1 className="font-display text-4xl font-black tracking-tighter text-white sm:text-5xl">{p.title}</h1>
      {p.image && <Img src={p.image} alt={p.title} className="mt-8 w-full rounded-2xl" />}
      <div className="mt-8 whitespace-pre-line text-lg leading-relaxed text-zinc-300">{p.body}</div>
    </article>
  );
}

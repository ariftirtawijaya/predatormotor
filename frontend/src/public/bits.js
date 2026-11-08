import { createContext, useContext } from "react";
import { Link, useLocation } from "react-router-dom";
import { mediaUrl } from "@/lib/api";
import { waLink } from "@/lib/fmt";

export const SiteCtx = createContext(null);
export const useSite = () => useContext(SiteCtx);

export function useWa(text) {
  const site = useSite();
  const c = site?.contact || {};
  if (!c.whatsapp) return null;
  return waLink(c.whatsapp, text || c.wa_message);
}

export function SLink({ href, children, className, testid, waText }) {
  const loc = useLocation();
  const wa = useWa(waText);
  const preview = new URLSearchParams(loc.search).get("preview") === "1";
  if (href === "#whatsapp") {
    if (!wa) return <Link to={`/kontak${preview ? "?preview=1" : ""}`} className={className} data-testid={testid}>{children}</Link>;
    return <a href={wa} target="_blank" rel="noreferrer" className={className} data-testid={testid}>{children}</a>;
  }
  if (!href || /^(https?:|mailto:|tel:)/.test(href)) {
    return <a href={href || "#"} target="_blank" rel="noreferrer" className={className} data-testid={testid}>{children}</a>;
  }
  if (href.startsWith("#")) return <a href={href} className={className} data-testid={testid}>{children}</a>;
  return <Link to={`${href}${preview ? "?preview=1" : ""}`} className={className} data-testid={testid}>{children}</Link>;
}

export const Img = ({ src, alt, className }) => (src ? <img src={mediaUrl(src)} alt={alt || ""} loading="lazy" className={className} /> : null);

export const Eyebrow = ({ children }) => <p className="mb-3 text-xs font-bold uppercase tracking-[0.25em] accent-text">{children}</p>;

export const H2 = ({ children, sub }) => (
  <div className="mb-10 max-w-2xl">
    <h2 className="font-display text-3xl font-extrabold tracking-tight text-white sm:text-4xl">{children}</h2>
    {sub && <p className="mt-3 text-base text-zinc-400 md:text-lg">{sub}</p>}
  </div>
);

export const Price = ({ s }) => (
  <p className="font-display text-xl font-bold accent-text">{s.price_text || (s.price ? "Rp" + Number(s.price).toLocaleString("id-ID") : "Hubungi kami")}</p>
);

export const Empty = ({ children }) => <p className="rounded-xl border border-dashed border-zinc-700 p-8 text-center text-zinc-400">{children}</p>;

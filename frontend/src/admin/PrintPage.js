import { useEffect, useState } from "react";
import { useParams, useSearchParams, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import Receipt, { toReceipt } from "@/components/Receipt";

const EP = { job: "jobs", sale: "sales", order: "orders" };

export default function PrintPage() {
  const { kind, id } = useParams();
  const [sp, setSp] = useSearchParams();
  const size = sp.get("size") || "80";
  const [doc, setDoc] = useState(null);
  const [site, setSite] = useState({});
  const nav = useNavigate();
  useEffect(() => {
    api.get(`/${EP[kind]}/${id}`).then((r) => setDoc(r.data));
    api.get("/public/site").then((r) => setSite(r.data));
  }, [kind, id]);
  return (
    <div className="min-h-screen bg-slate-200 py-6 font-admin">
      <style>{`@page { size: ${size === "a4" ? "A4" : "80mm auto"}; margin: ${size === "a4" ? "10mm" : "2mm"}; }`}</style>
      <div className="no-print mb-4 flex flex-wrap justify-center gap-2">
        <button onClick={() => nav(-1)} className="rounded-md border border-slate-400 bg-white px-3 py-2 text-sm" data-testid="print-back">Kembali</button>
        {["80", "a4"].map((s) => (
          <button key={s} onClick={() => setSp({ size: s })} className={`rounded-md px-3 py-2 text-sm font-semibold ${size === s ? "bg-sky-700 text-white" : "border border-slate-400 bg-white"}`} data-testid={`print-size-${s}`}>
            {s === "80" ? "Thermal 80 mm" : "A4"}
          </button>
        ))}
        <button onClick={() => window.print()} className="rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white" data-testid="print-now">Cetak / Simpan PDF</button>
      </div>
      {doc && <div className="mx-auto w-fit bg-white shadow"><Receipt d={toReceipt(kind, doc)} identity={site.identity} contact={site.contact} size={size} /></div>}
    </div>
  );
}

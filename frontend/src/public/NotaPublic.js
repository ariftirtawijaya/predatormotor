import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "@/lib/api";
import Receipt from "@/components/Receipt";

export default function NotaPublic() {
  const { token } = useParams();
  const [d, setD] = useState(null);
  const [site, setSite] = useState({});
  const [err, setErr] = useState("");
  useEffect(() => {
    document.head.querySelector("meta[name='robots']")?.setAttribute("content", "noindex,nofollow");
    api.get(`/public/nota/${token}`).then((r) => setD(r.data)).catch(() => setErr("Nota tidak ditemukan"));
    api.get("/public/site").then((r) => setSite(r.data)).catch(() => {});
  }, [token]);
  return (
    <div className="min-h-screen bg-slate-100 py-8">
      {err && <p className="text-center text-slate-700">{err}</p>}
      {d && (
        <>
          <div className="no-print mb-4 flex justify-center gap-2">
            <button onClick={() => window.print()} className="rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white" data-testid="public-nota-print">Cetak / Simpan PDF</button>
          </div>
          <Receipt d={d} identity={site.identity} contact={site.contact} size="80" />
        </>
      )}
    </div>
  );
}

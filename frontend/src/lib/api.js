import axios from "axios";

export const BACKEND = process.env.REACT_APP_BACKEND_URL;
export const api = axios.create({ baseURL: `${BACKEND}/api`, withCredentials: true });

let refreshing = null;
api.interceptors.response.use(
  (r) => r,
  async (err) => {
    const cfg = err.config || {};
    if (err.response?.status === 401 && !cfg._retry && !cfg.url?.startsWith("/auth/")) {
      cfg._retry = true;
      try {
        refreshing = refreshing || api.post("/auth/refresh");
        await refreshing;
        refreshing = null;
        return api(cfg);
      } catch (e) {
        refreshing = null;
        if (window.location.pathname.startsWith("/admin") && window.location.pathname !== "/admin/login") {
          window.location.href = "/admin/login";
        }
      }
    }
    return Promise.reject(err);
  }
);

export function errMsg(e) {
  const d = e?.response?.data?.detail;
  if (!d) return e?.message || "Terjadi kesalahan";
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x?.msg || JSON.stringify(x)).join(", ");
  return d.msg || String(d);
}

export const mediaUrl = (u) => (!u ? "" : u.startsWith("/api") ? `${BACKEND}${u}` : u);

export const newKey = () => (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`);

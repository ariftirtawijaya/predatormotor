import { createContext, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  useEffect(() => {
    api.get("/auth/me").then((r) => setUser(r.data)).catch(async () => {
      try {
        const r = await api.post("/auth/refresh");
        setUser(r.data);
      } catch {
        setUser(false);
      }
    });
  }, []);
  const logout = async () => {
    await api.post("/auth/logout");
    setUser(false);
  };
  return <AuthCtx.Provider value={{ user, setUser, logout }}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
export const isManager = (u) => u && (u.role === "owner" || u.role === "admin");
export const isOwner = (u) => u && u.role === "owner";

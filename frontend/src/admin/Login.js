import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Btn, Field, Input } from "@/admin/ui";

export default function Login() {
  const [f, setF] = useState({ email: "", password: "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const { setUser } = useAuth();
  const nav = useNavigate();
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      const r = await api.post("/auth/login", f);
      setUser(r.data);
      nav("/admin");
    } catch (e2) {
      setErr(errMsg(e2));
    }
    setBusy(false);
  };
  return (
    <div className="flex min-h-screen items-center bg-slate-50 px-4 font-admin">
      <form onSubmit={submit} className="mx-auto w-full max-w-sm rounded-md border border-slate-200 bg-white p-6" data-testid="login-form">
        <p className="font-display text-2xl font-extrabold tracking-tight text-slate-900">PREDATOR <span className="text-sky-700">Autolight</span></p>
        <p className="mb-6 mt-1 text-sm text-slate-600">Masuk ke sistem bengkel</p>
        <div className="space-y-4">
          <Field label="Email"><Input type="email" required autoComplete="username" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} data-testid="login-email-input" /></Field>
          <Field label="Password"><Input type="password" required autoComplete="current-password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} data-testid="login-password-input" /></Field>
          {err && <p className="rounded-md border border-red-200 bg-red-50 p-2 text-sm text-red-800" data-testid="login-error">{err}</p>}
          <Btn type="submit" className="w-full" disabled={busy} data-testid="login-submit-button">{busy ? "Memproses…" : "Masuk"}</Btn>
        </div>
      </form>
    </div>
  );
}

import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const BTN = {
  primary: "bg-sky-700 text-white hover:bg-sky-800",
  dark: "bg-slate-900 text-white hover:bg-slate-800",
  outline: "border border-slate-300 bg-white text-slate-800 hover:bg-slate-100",
  danger: "bg-red-700 text-white hover:bg-red-800",
  success: "bg-emerald-700 text-white hover:bg-emerald-800",
  ghost: "text-slate-700 hover:bg-slate-100",
};

export const Btn = ({ v = "primary", className = "", size = "md", ...p }) => (
  <button
    {...p}
    className={`inline-flex items-center justify-center gap-1.5 rounded-md font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${size === "sm" ? "h-8 px-2.5 text-xs" : "h-10 px-4 text-sm"} ${BTN[v]} ${className}`}
  />
);

export const Field = ({ label, children, hint, className = "" }) => (
  <label className={`block ${className}`}>
    {label && <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-600">{label}</span>}
    {children}
    {hint && <span className="mt-1 block text-xs text-slate-500">{hint}</span>}
  </label>
);

const INP = "w-full rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-900 placeholder:text-slate-400 focus:border-sky-600 focus:outline-none focus:ring-2 focus:ring-sky-100";

export const Input = ({ className = "", ...p }) => <input {...p} className={`h-10 ${INP} ${className}`} />;
export const Textarea = ({ className = "", ...p }) => <textarea rows={3} {...p} className={`py-2 ${INP} ${className}`} />;
export const Select = ({ className = "", children, ...p }) => (
  <select {...p} className={`h-10 ${INP} ${className}`}>{children}</select>
);

export const NumInput = ({ value, onChange, ...p }) => (
  <Input type="number" inputMode="numeric" min={0} value={value ?? ""} onChange={(e) => onChange(e.target.value === "" ? "" : Number(e.target.value))} {...p} />
);

export const Card = ({ title, actions, children, className = "", ...p }) => (
  <section {...p} className={`rounded-md border border-slate-200 bg-white ${className}`}>
    {(title || actions) && (
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-3">
        <h3 className="text-sm font-bold text-slate-900">{title}</h3>
        <div className="flex flex-wrap gap-2">{actions}</div>
      </div>
    )}
    <div className="p-4">{children}</div>
  </section>
);

export const PageHead = ({ title, sub, actions }) => (
  <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
    <div>
      <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">{title}</h1>
      {sub && <p className="mt-1 text-sm text-slate-600">{sub}</p>}
    </div>
    <div className="flex flex-wrap gap-2">{actions}</div>
  </div>
);

const BADGE = {
  Masuk: "bg-amber-100 text-amber-900 border-amber-300",
  Selesai: "bg-emerald-100 text-emerald-900 border-emerald-300",
  Batal: "bg-red-100 text-red-900 border-red-300",
  Lunas: "bg-emerald-100 text-emerald-900 border-emerald-300",
  Baru: "bg-sky-100 text-sky-900 border-sky-300",
  Dikirim: "bg-indigo-100 text-indigo-900 border-indigo-300",
  Diambil: "bg-emerald-100 text-emerald-900 border-emerald-300",
  Diterima: "bg-emerald-100 text-emerald-900 border-emerald-300",
  Kembali: "bg-red-100 text-red-900 border-red-300",
};

export const Badge = ({ children, tone, ...p }) => (
  <span {...p} className={`inline-flex items-center rounded border px-2 py-0.5 text-xs font-semibold ${BADGE[tone || children] || "border-slate-300 bg-slate-100 text-slate-800"}`}>{children}</span>
);

export const Table = ({ head, children, empty, testid }) => (
  <div className="overflow-x-auto rounded-md border border-slate-200 bg-white" data-testid={testid}>
    <table className="w-full text-sm">
      <thead className="bg-slate-100 text-left text-xs uppercase tracking-wide text-slate-700">
        <tr>{head.map((h, i) => <th key={i} className="whitespace-nowrap px-3 py-2.5 font-semibold">{h}</th>)}</tr>
      </thead>
      <tbody className="divide-y divide-slate-200 text-slate-800">{children}</tbody>
    </table>
    {empty && <p className="p-6 text-center text-sm text-slate-500">{empty}</p>}
  </div>
);

export const Td = ({ className = "", ...p }) => <td {...p} className={`px-3 py-2.5 align-top ${className}`} />;

export const Modal = ({ open, onClose, title, children, wide }) => (
  <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
    <DialogContent className={`max-h-[90vh] overflow-y-auto bg-white font-admin ${wide ? "sm:max-w-3xl" : "sm:max-w-lg"}`}>
      <DialogHeader><DialogTitle className="text-slate-900">{title}</DialogTitle></DialogHeader>
      {children}
    </DialogContent>
  </Dialog>
);

export const Stat = ({ label, value, sub, testid, tone = "" }) => (
  <div className={`rounded-md border border-slate-200 bg-white p-4 ${tone}`} data-testid={testid}>
    <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">{label}</p>
    <p className="mt-1 font-mono-num text-xl font-semibold text-slate-900">{value}</p>
    {sub && <p className="mt-1 text-xs text-slate-500">{sub}</p>}
  </div>
);

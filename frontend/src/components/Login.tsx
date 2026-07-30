import { FormEvent, useState } from "react";

interface LoginProps {
  apiBaseUrl: string;
  onAuthenticated: (token: string, role: string) => void;
}

export function Login({ apiBaseUrl, onAuthenticated }: LoginProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"login" | "register">("login");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      const endpoint = mode === "login" ? "/auth/login" : "/auth/register";
      const body = mode === "login" ? { email, password } : { email, password, display_name: displayName };
      const response = await fetch(`${apiBaseUrl}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload = (await response.json()) as { access_token?: string; detail?: string; user?: { role?: string } };
      if (!response.ok || !payload.access_token || !payload.user?.role) throw new Error(payload.detail ?? "Authentication failed");
      onAuthenticated(payload.access_token, payload.user.role);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Authentication failed");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="relative grid min-h-screen overflow-hidden bg-slate-950 px-5 py-8 text-slate-900 lg:grid-cols-2 lg:p-10">
      <div className="absolute -left-24 top-0 h-80 w-80 rounded-full bg-blue-600/25 blur-3xl" />
      <div className="absolute -bottom-28 right-0 h-96 w-96 rounded-full bg-cyan-400/15 blur-3xl" />
      <section className="relative mx-auto flex w-full max-w-xl flex-col justify-between py-3 text-white lg:mx-0 lg:py-10">
        <div>
          <div className="mb-12 inline-flex items-center gap-3 font-semibold tracking-tight"><span className="grid h-10 w-10 place-items-center rounded-xl bg-blue-500 shadow-lg shadow-blue-500/30">SJ</span> Smart Jira</div>
          <p className="mb-4 text-sm font-semibold uppercase tracking-[0.22em] text-blue-300">Work, made visible</p>
          <h1 className="max-w-lg text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">Keep every project moving with calm clarity.</h1>
          <p className="mt-5 max-w-md text-base leading-7 text-slate-300">Plan work, align your team, and move tasks forward in a focused, real-time workspace.</p>
        </div>
        <div className="mt-14 hidden grid-cols-3 gap-3 sm:grid lg:grid-cols-1 xl:grid-cols-3">
          {[["Live board", "Stay in sync"], ["Secure roles", "Right access"], ["AI insights", "Plan smarter"]].map(([title, text]) => <div key={title} className="rounded-xl border border-white/10 bg-white/5 p-4 backdrop-blur"><p className="font-medium">{title}</p><p className="mt-1 text-sm text-slate-400">{text}</p></div>)}
        </div>
      </section>
      <section className="relative my-auto mx-auto w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl shadow-slate-950/30 sm:p-8">
        <div className="mb-7"><p className="text-sm font-medium text-blue-600">{mode === "login" ? "Welcome back" : "Get started"}</p><h2 className="mt-1 text-2xl font-semibold tracking-tight">{mode === "login" ? "Sign in to your workspace" : "Create your developer account"}</h2><p className="mt-2 text-sm leading-6 text-slate-500">{mode === "login" ? "Use your workspace credentials to continue." : "Your account will be created with Developer access."}</p></div>
        <form onSubmit={submit} className="space-y-4">
          {mode === "register" && <label className="block text-sm font-medium text-slate-700">Display name<input required minLength={2} value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="Your name" className="mt-1.5 w-full rounded-xl border border-slate-300 px-3.5 py-3 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100" /></label>}
          <label className="block text-sm font-medium text-slate-700">Email<input required type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@company.com" className="mt-1.5 w-full rounded-xl border border-slate-300 px-3.5 py-3 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100" /></label>
          <label className="block text-sm font-medium text-slate-700">Password<input required type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} minLength={mode === "register" ? 12 : 1} value={password} onChange={(event) => setPassword(event.target.value)} placeholder="••••••••••••" className="mt-1.5 w-full rounded-xl border border-slate-300 px-3.5 py-3 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100" /></label>
          {error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">{error}</p>}
          <button disabled={isSubmitting} className="w-full rounded-xl bg-blue-600 px-4 py-3 font-semibold text-white shadow-lg shadow-blue-600/25 transition hover:bg-blue-700 focus:outline-none focus:ring-4 focus:ring-blue-200 disabled:cursor-not-allowed disabled:opacity-60">{isSubmitting ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}</button>
        </form>
        <button type="button" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(null); }} className="mt-6 w-full text-sm font-medium text-blue-600 hover:text-blue-800">{mode === "login" ? "New here? Create a developer account" : "Already have an account? Sign in"}</button>
      </section>
    </main>
  );
}

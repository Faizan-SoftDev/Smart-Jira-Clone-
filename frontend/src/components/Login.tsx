import { FormEvent, useState } from "react";

interface LoginProps {
  onAuthenticated: (token: string, role: string) => void;
}

export function Login({ onAuthenticated }: LoginProps) {
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
      const response = await fetch(`http://localhost:8000/api/v1${endpoint}`, {
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

  return <main className="grid min-h-screen place-items-center bg-slate-50 p-6"><form onSubmit={submit} className="w-full max-w-sm space-y-4 rounded-xl bg-white p-6 shadow"><h1 className="text-2xl font-bold">Smart Jira</h1>{mode === "register" && <input required minLength={2} value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="Display name" className="w-full rounded border p-3" />}<input required type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="Email" className="w-full rounded border p-3" /><input required type="password" minLength={mode === "register" ? 12 : 1} value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Password" className="w-full rounded border p-3" />{error && <p className="text-sm text-rose-600">{error}</p>}<button disabled={isSubmitting} className="w-full rounded bg-blue-600 p-3 font-semibold text-white disabled:opacity-50">{isSubmitting ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}</button><button type="button" onClick={() => setMode(mode === "login" ? "register" : "login")} className="w-full text-sm text-blue-600">{mode === "login" ? "Create a developer account" : "Already have an account? Sign in"}</button></form></main>;
}

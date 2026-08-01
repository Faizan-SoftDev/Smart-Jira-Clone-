import { FormEvent, useState } from "react";

interface LoginProps {
  apiBaseUrl: string;
  onAuthenticated: () => void;
}

const benefits = [
  ["◈", "One place for every project", "Plan requests, releases, bugs, and team priorities without losing context."],
  ["↗", "Move work at high velocity", "Give every teammate a clear view of what matters now and what comes next."],
  ["✦", "AI that helps you decide", "Turn a task into an informed estimate in seconds, right from the board."],
];

export function Login({ apiBaseUrl, onAuthenticated }: LoginProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"login" | "register">("login");
  const [displayName, setDisplayName] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      const endpoint = mode === "login" ? "/auth/login/" : "/auth/register/";
      const body = mode === "login" ? { email, password, ...(totpCode ? { totp_code: totpCode } : {}) } : { email, password, display_name: displayName };
      const response = await fetch(`${apiBaseUrl}${endpoint}`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const payload = (await response.json()) as { detail?: string };
      if (!response.ok) throw new Error(payload.detail ?? "Authentication failed");
      onAuthenticated();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Authentication failed");
    } finally {
      setIsSubmitting(false);
    }
  }

  const switchMode = (nextMode: "login" | "register") => {
    setMode(nextMode);
    setError(null);
  };

  return (
    <main className="landing-page">
      <header className="landing-nav">
        <a className="brand" href="#top" aria-label="Smart Jira home"><span className="brand-mark">▲</span><span>Smart Jira</span></a>
        <nav className="landing-links" aria-label="Main navigation"><a href="#features">Features</a><a href="#how-it-works">How it works</a><a href="#resources">Resources</a></nav>
        <div className="nav-actions"><button className="text-button" onClick={() => switchMode("login")}>Sign in</button><button className="nav-cta" onClick={() => switchMode("register")}>Get started</button></div>
      </header>

      <div className="announcement">New: AI task estimates are now available for every project. <a href="#features">Learn more →</a></div>

      <section className="hero" id="top">
        <div className="hero-copy">
          <p className="eyebrow"><span>SMART</span> PROJECT DELIVERY</p>
          <h1>Project management for <em>high-velocity</em> teams</h1>
          <p className="hero-description">Plan, track, and deliver outstanding work with a focused workspace your whole team will actually enjoy using.</p>
          <div className="hero-proof"><span className="avatars"><i>F</i><i>A</i><i>M</i></span><span>Built for teams that move together</span></div>
        </div>

        <aside className="auth-card" aria-label="Account access">
          <div className="auth-tabs"><button className={mode === "register" ? "active" : ""} onClick={() => switchMode("register")}>Get started</button><button className={mode === "login" ? "active" : ""} onClick={() => switchMode("login")}>Sign in</button></div>
          <h2>{mode === "login" ? "Welcome back" : "Start building momentum"}</h2>
          <p>{mode === "login" ? "Sign in to pick up where your team left off." : "Create your workspace and bring your team along."}</p>
          <form onSubmit={submit} className="auth-form">
            {mode === "register" && <label>Your name<input required minLength={2} value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="Ada Lovelace" /></label>}
            <label>Work email<input required type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@company.com" /></label>
            <label>Password<input required type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} minLength={mode === "register" ? 12 : 1} value={password} onChange={(event) => setPassword(event.target.value)} placeholder="••••••••••••" /></label>
            {mode === "login" && <label>Authenticator code <span className="font-normal text-slate-400">(Enterprise only)</span><input inputMode="numeric" pattern="[0-9]*" maxLength={6} value={totpCode} onChange={(event) => setTotpCode(event.target.value.replace(/\D/g, ""))} placeholder="123456" /></label>}
            {error && <p className="form-error" role="alert">{error}</p>}
            <button disabled={isSubmitting} className="primary-button">{isSubmitting ? "Please wait…" : mode === "login" ? "Sign in to Smart Jira" : "Create free account"}</button>
          </form>
          <p className="auth-footnote">{mode === "login" ? "Need an account?" : "Already have an account?"} <button onClick={() => switchMode(mode === "login" ? "register" : "login")}>{mode === "login" ? "Get started" : "Sign in"}</button></p>
        </aside>
      </section>

      <section className="trusted"><p>BUILT FOR FOCUSED, AMBITIOUS TEAMS</p><div><span>Vortex</span><span>northstar</span><span>MONO</span><span>cobalt</span><span>apex</span></div></section>

      <section className="feature-intro" id="features">
        <p className="section-kicker">ONE CALM WORKSPACE</p><h2>Everything your team needs to ship with confidence.</h2><p>Keep the work visible, the conversations useful, and the next step obvious.</p>
        <div className="feature-tabs"><button className="selected">Team workspace</button><button>Live board</button><button>AI insights</button><button>Role-based access</button></div>
        <div className="workspace-preview">
          <div className="preview-sidebar"><b>▲ Smart Jira</b><span className="preview-active">Overview</span><span>My work</span><span>Projects</span><span>Team</span><span>Reports</span></div>
          <div className="preview-main"><div className="preview-title"><span><small>PROJECT / ATLAS</small><strong>Release planning</strong></span><button>+ Create task</button></div><div className="preview-columns">{[["To do", ["Update onboarding flow", "Prepare launch notes"]], ["In progress", ["Mobile navigation", "Improve search results"]], ["Done", ["Design system audit"]]].map(([column, cards]) => <div className="mini-column" key={column as string}><p>{column as string}<b>{(cards as string[]).length}</b></p>{(cards as string[]).map((card, index) => <article key={card}><i className={index === 1 ? "purple" : "blue"} />{card}<small>•••</small></article>)}</div>)}</div></div>
        </div>
      </section>

      <section className="benefit-grid" id="how-it-works">{benefits.map(([icon, title, text]) => <article key={title}><span>{icon}</span><h3>{title}</h3><p>{text}</p><a href="#top">Explore Smart Jira →</a></article>)}</section>

      <section className="ai-section"><div><p className="section-kicker">BUILT-IN INTELLIGENCE</p><h2>Make better calls, faster.</h2><p>Smart Jira’s AI analysis turns rough work into clear estimates, helping your team plan with less guesswork.</p><a className="inline-link" href="#top">See AI insights in action →</a></div><div className="ai-card"><div className="ai-spark">✦</div><p>AI estimate ready</p><strong>8 story points</strong><span>Based on scope, complexity, and similar work</span><div className="ai-bars"><i /><i /><i /><i /></div></div></section>

      <section className="resource-section" id="resources"><p className="section-kicker">RESOURCES</p><h2>Learn how great teams get work done.</h2><div className="resource-cards">{["The guide to calmer project delivery", "How to make your delivery rhythm stick", "A practical guide to estimating work"].map((item, index) => <article key={item}><span>0{index + 1}</span><h3>{item}</h3><a href="#top">Read more →</a></article>)}</div></section>

      <section className="final-cta"><h2>Bring your best work into focus.</h2><p>Start your Smart Jira workspace today. No credit card required.</p><button onClick={() => switchMode("register")}>Get started for free</button></section>
      <footer><a className="brand" href="#top"><span className="brand-mark">▲</span><span>Smart Jira</span></a><span>© 2026 Smart Jira</span><div><a href="#top">Privacy</a><a href="#top">Terms</a><a href="#top">Support</a></div></footer>
    </main>
  );
}

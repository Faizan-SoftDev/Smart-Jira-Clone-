import { useCallback, useEffect, useMemo, useState } from "react";
import { KanbanDashboard } from "./components/KanbanDashboard";
import { Login } from "./components/Login";
import { CookieBanner } from "./components/CookieBanner";
import { useKanbanSocket } from "./hooks/useKanbanSocket";
import type { ProjectBoard } from "./types/kanban";

const api = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1").replace(/\/$/, "");
const wsBase = (import.meta.env.VITE_WS_BASE_URL ?? "ws://localhost:8000").replace(/\/$/, "");
type Workspace = { id: string; name: string }; type Project = { id: string; key: string; name: string };

export function App() {
  const [signedIn, setSignedIn] = useState<boolean | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]); const [projects, setProjects] = useState<Project[]>([]);
  const [workspaceId, setWorkspaceId] = useState(""); const [projectId, setProjectId] = useState(""); const [board, setBoard] = useState<ProjectBoard | null>(null);
  const [error, setError] = useState<string | null>(null); const [csrfToken, setCsrfToken] = useState("");
  const request = useCallback(async (path: string, init?: RequestInit) => {
    const headers = new Headers(init?.headers); if (csrfToken && init?.method && init.method !== "GET") headers.set("X-CSRFToken", csrfToken);
    const response = await fetch(`${api}${path}`, { credentials: "include", ...init, headers });
    if (response.status === 401 || response.status === 403) throw new Error("Please sign in to continue.");
    if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail ?? "Request failed."); }
    return response.status === 204 ? null : response.json();
  }, [csrfToken]);
  const loadBoard = useCallback(async () => { if (!projectId) return; setBoard(await request(`/projects/${projectId}/board/`) as ProjectBoard); }, [projectId, request]);
  useEffect(() => { void request("/auth/me/").then(() => setSignedIn(true)).catch(() => setSignedIn(false)); }, [request]);
  useEffect(() => { if (signedIn) void fetch(`${api}/auth/csrf/`, { credentials: "include" }).then((r) => r.json()).then((body) => setCsrfToken(body.csrfToken)); }, [signedIn]);
  useEffect(() => { if (!signedIn) return; void request("/workspaces/").then((items) => { setWorkspaces(items as Workspace[]); setWorkspaceId((value) => value || (items as Workspace[])[0]?.id || ""); }).catch((reason) => setError(reason.message)); }, [signedIn, request]);
  useEffect(() => { if (!workspaceId) return; void request(`/workspaces/${workspaceId}/projects/`).then((items) => { setProjects(items as Project[]); setProjectId((value) => value || (items as Project[])[0]?.id || ""); }).catch((reason) => setError(reason.message)); }, [workspaceId, request]);
  useEffect(() => { void loadBoard().catch((reason) => setError(reason.message)); }, [loadBoard]);
  const socketUrl = useMemo(() => projectId ? `${wsBase}/ws/projects/${projectId}/board/` : null, [projectId]);
  useKanbanSocket(socketUrl, () => { void loadBoard().catch(() => undefined); });
  if (signedIn === null) return <main className="grid min-h-screen place-items-center">Loading TaskCraft…</main>;
  if (!signedIn) return <><Login apiBaseUrl={api} onAuthenticated={() => setSignedIn(true)} /><CookieBanner /></>;
  return <><main className="min-h-screen bg-slate-50 text-slate-900"><header className="border-b bg-white px-6 py-4"><div className="mx-auto flex max-w-[1600px] items-center justify-between"><div><b>TaskCraft</b><span className="ml-2 text-sm text-slate-500">Live project board</span></div><button onClick={() => void request("/auth/logout/", { method: "POST" }).finally(() => setSignedIn(false))} className="text-sm text-slate-600">Sign out</button></div></header><section className="mx-auto max-w-[1600px] p-6"><div className="mb-6 flex flex-wrap gap-3"><select value={workspaceId} onChange={(e) => { setWorkspaceId(e.target.value); setProjectId(""); }} className="rounded-lg border p-2">{workspaces.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</select><select value={projectId} onChange={(e) => setProjectId(e.target.value)} className="rounded-lg border p-2">{projects.map((p) => <option key={p.id} value={p.id}>{p.key} — {p.name}</option>)}</select></div>{error && <p className="mb-4 rounded-lg bg-rose-50 p-3 text-rose-700">{error}</p>}{board ? <KanbanDashboard board={board} onMove={async (issueId, target) => { await request(`/issues/${issueId}/move/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ target_status_id: target }) }); await loadBoard(); }} /> : <p className="text-slate-500">Create a project to start its board.</p>}</section></main><CookieBanner /></>;
}

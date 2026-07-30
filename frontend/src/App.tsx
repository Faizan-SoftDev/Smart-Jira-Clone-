import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";

import { KanbanDashboard } from "./components/KanbanDashboard";
import { Login } from "./components/Login";
import type { KanbanStatus, KanbanTask } from "./types/kanban";

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1").replace(/\/$/, "");
const webSocketUrl = (import.meta.env.VITE_KANBAN_WS_URL ?? "ws://localhost:8000/ws/kanban").replace(/\/$/, "");
type Role = "Admin" | "ProjectManager" | "Developer";
interface Project { id: string; key: string; name: string; }

export function App() {
  const [token, setToken] = useState(() => localStorage.getItem("smart_jira_access_token"));
  const [role, setRole] = useState<Role | null>(() => localStorage.getItem("smart_jira_role") as Role | null);
  const [tasks, setTasks] = useState<KanbanTask[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [isComposerOpen, setIsComposerOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [taskType, setTaskType] = useState<"feature" | "bug">("feature");

  const loadTasks = useCallback(async (signal?: AbortSignal) => {
    if (!token) return;
    const projectQuery = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
    const response = await fetch(`${apiBaseUrl}/tasks${projectQuery}`, { headers: { Authorization: `Bearer ${token}` }, signal });
    if (response.status === 401) throw new Error("Your session has expired. Please sign in again.");
    if (!response.ok) throw new Error("Unable to load the workspace.");
    const payload = await response.json() as { items: KanbanTask[] };
    setTasks(payload.items);
  }, [projectId, token]);

  useEffect(() => {
    const controller = new AbortController();
    if (!token) { setIsLoading(false); return; }
    setIsLoading(true);
    void loadTasks(controller.signal).catch((reason: unknown) => !controller.signal.aborted && setError(reason instanceof Error ? reason.message : "Unable to load the workspace.")).finally(() => !controller.signal.aborted && setIsLoading(false));
    return () => controller.abort();
  }, [loadTasks, token]);

  useEffect(() => {
    if (!token) return;
    void fetch(`${apiBaseUrl}/projects`, { headers: { Authorization: `Bearer ${token}` } }).then(async (response) => response.ok ? response.json() as Promise<Project[]> : []).then((items) => { setProjects(items); if (items[0]) setProjectId((current) => current || items[0].id); });
  }, [token]);

  const authenticatedWebSocketUrl = useMemo(() => `${webSocketUrl}${webSocketUrl.includes("?") ? "&" : "?"}token=${encodeURIComponent(token ?? "")}`, [token]);
  const workspaceLabel = projects.find((project) => project.id === projectId);
  const canAnalyze = role === "Admin" || role === "ProjectManager";

  async function saveStatusChange(taskId: string, status: KanbanStatus): Promise<void> {
    const response = await fetch(`${apiBaseUrl}/tasks/${taskId}/status`, { method: "PATCH", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify({ status }) });
    if (!response.ok) throw new Error("Unable to save task status.");
  }

  async function createTask(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault(); setIsCreating(true); setError(null); setNotice(null);
    try {
      const base = { task_type: taskType, title, description, project_id: projectId || null };
      const payload = taskType === "feature" ? { ...base, acceptance_criteria: [] } : { ...base, severity: "medium", is_reproducible: true };
      const response = await fetch(`${apiBaseUrl}/tasks`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify(payload) });
      if (!response.ok) throw new Error("Unable to create the task.");
      setTitle(""); setDescription(""); setIsComposerOpen(false); setNotice("Task created and added to the board."); await loadTasks();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to create task."); } finally { setIsCreating(false); }
  }

  const analyzeTask = useCallback(async (taskId: string) => { setError(null); setNotice(null); const response = await fetch(`${apiBaseUrl}/tasks/${taskId}/analyze-ai`, { method: "POST", headers: { Authorization: `Bearer ${token}` } }); const payload = await response.json() as { estimated_story_points?: number; detail?: string }; if (!response.ok) { setError(payload.detail ?? "AI analysis failed."); return; } setNotice(`AI estimate: ${payload.estimated_story_points} story points.`); }, [token]);
  const signOut = () => { localStorage.removeItem("smart_jira_access_token"); localStorage.removeItem("smart_jira_role"); setToken(null); setRole(null); setTasks([]); setError(null); };

  if (!token) return <Login apiBaseUrl={apiBaseUrl} onAuthenticated={(accessToken, userRole) => { localStorage.setItem("smart_jira_access_token", accessToken); localStorage.setItem("smart_jira_role", userRole); setToken(accessToken); setRole(userRole as Role); }} />;
  if (isLoading) return <main className="grid min-h-screen place-items-center bg-slate-50 text-slate-600"><div className="text-center"><div className="mx-auto mb-4 h-9 w-9 animate-spin rounded-full border-4 border-blue-100 border-t-blue-600" /><p className="font-medium">Loading workspace…</p></div></main>;
  if (error && tasks.length === 0) return <main className="grid min-h-screen place-items-center bg-slate-50 p-6"><div className="max-w-md rounded-2xl border border-rose-100 bg-white p-7 text-center shadow-sm"><p className="font-semibold text-rose-700">Workspace unavailable</p><p className="mt-2 text-sm text-slate-500">{error}</p><button onClick={signOut} className="mt-5 rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white">Sign out</button></div></main>;
  return <main className="min-h-screen bg-[#f7f9fc] text-slate-900"><header className="border-b border-slate-200 bg-white/95 px-4 py-3 backdrop-blur sm:px-6"><div className="mx-auto flex max-w-[1600px] items-center justify-between gap-3"><div className="flex min-w-0 items-center gap-3"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-blue-600 to-indigo-600 text-xs font-bold text-white shadow-lg shadow-blue-200">SJ</span><div className="min-w-0"><p className="truncate text-sm font-semibold tracking-tight">Smart Jira</p><p className="truncate text-xs text-slate-500">{workspaceLabel ? `${workspaceLabel.key} · ${workspaceLabel.name}` : "All workspaces"}</p></div></div><div className="flex items-center gap-2"><span className="hidden rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700 sm:inline">{role}</span><button onClick={() => setIsComposerOpen(true)} className="rounded-lg bg-blue-600 px-3.5 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700">+ Create task</button><button onClick={signOut} className="rounded-lg px-3 py-2 text-sm font-medium text-slate-500 transition hover:bg-slate-100 hover:text-slate-900">Sign out</button></div></div></header>
    <section className="mx-auto max-w-[1600px] px-4 py-7 sm:px-6 lg:py-9"><div className="mb-7 flex flex-col justify-between gap-5 lg:flex-row lg:items-end"><div><p className="text-sm font-semibold uppercase tracking-[0.18em] text-blue-600">Project delivery</p><h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">Your work, at a glance.</h1><p className="mt-2 text-sm text-slate-500">Drag work across the board or create a task to keep momentum visible.</p></div><div className="flex flex-wrap items-center gap-3"><label className="text-sm font-medium text-slate-600">Workspace<select value={projectId} onChange={(event) => setProjectId(event.target.value)} className="ml-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-100"><option value="">All projects</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.key} — {project.name}</option>)}</select></label><span className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-500"><b className="text-slate-900">{tasks.length}</b> active tasks</span></div></div>
      {(error || notice) && <div className={`mb-5 rounded-xl border px-4 py-3 text-sm ${error ? "border-rose-200 bg-rose-50 text-rose-700" : "border-emerald-200 bg-emerald-50 text-emerald-700"}`}>{error ?? notice}</div>}
      {isComposerOpen && <form onSubmit={createTask} className="mb-6 rounded-2xl border border-blue-100 bg-white p-4 shadow-lg shadow-blue-950/5 sm:p-5"><div className="mb-4 flex items-center justify-between"><div><h2 className="font-semibold">Create a task</h2><p className="text-sm text-slate-500">Add focused work to the selected project.</p></div><button type="button" onClick={() => setIsComposerOpen(false)} className="rounded-lg px-2 py-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700">✕</button></div><div className="grid gap-3 md:grid-cols-[1fr_1.4fr_auto_auto]"><input required value={title} onChange={(event) => setTitle(event.target.value)} maxLength={255} placeholder="Task title" className="rounded-xl border border-slate-300 px-3.5 py-2.5 outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-100" /><input value={description} onChange={(event) => setDescription(event.target.value)} maxLength={20_000} placeholder="Add a concise description (optional)" className="rounded-xl border border-slate-300 px-3.5 py-2.5 outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-100" /><select value={taskType} onChange={(event) => setTaskType(event.target.value as "feature" | "bug")} className="rounded-xl border border-slate-300 bg-white px-3 py-2.5"><option value="feature">Feature</option><option value="bug">Bug</option></select><button disabled={isCreating} className="rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:opacity-60">{isCreating ? "Creating…" : "Add task"}</button></div></form>}
      <KanbanDashboard initialTasks={tasks} webSocketUrl={authenticatedWebSocketUrl} onStatusChange={saveStatusChange} onTaskCreated={() => void loadTasks()} onAnalyzeTask={analyzeTask} canAnalyze={canAnalyze} />
    </section></main>;
}

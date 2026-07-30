import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";

import { KanbanDashboard } from "./components/KanbanDashboard";
import { Login } from "./components/Login";
import type { KanbanStatus, KanbanTask } from "./types/kanban";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
const webSocketUrl = import.meta.env.VITE_KANBAN_WS_URL ?? "ws://localhost:8000/ws/kanban";
type Role = "Admin" | "ProjectManager" | "Developer";
interface Project { id: string; key: string; name: string; description: string; }

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
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [taskType, setTaskType] = useState<"feature" | "bug">("feature");

  const loadTasks = useCallback(async (signal?: AbortSignal) => {
    if (!token) return;
    const projectQuery = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
    const response = await fetch(`${apiBaseUrl}/tasks${projectQuery}`, { headers: { Authorization: `Bearer ${token}` }, signal });
    if (!response.ok) throw new Error("Unable to load tasks");
    const payload = await response.json() as { items: KanbanTask[] };
    setTasks(payload.items);
  }, [projectId, token]);

  useEffect(() => {
    const controller = new AbortController();
    if (!token) { setIsLoading(false); return; }
    setIsLoading(true);
    void loadTasks(controller.signal)
      .catch((reason: unknown) => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Unable to load tasks"); })
      .finally(() => { if (!controller.signal.aborted) setIsLoading(false); });
    return () => controller.abort();
  }, [loadTasks, token]);

  useEffect(() => {
    if (!token) return;
    void fetch(`${apiBaseUrl}/projects`, { headers: { Authorization: `Bearer ${token}` } })
      .then(async (response) => response.ok ? response.json() as Promise<Project[]> : [])
      .then((items) => { setProjects(items); if (items[0]) setProjectId((current) => current || items[0].id); });
  }, [token]);

  const authenticatedWebSocketUrl = useMemo(() => {
    if (!token) return webSocketUrl;
    const separator = webSocketUrl.includes("?") ? "&" : "?";
    return `${webSocketUrl}${separator}token=${encodeURIComponent(token)}`;
  }, [token]);

  async function saveStatusChange(taskId: string, status: KanbanStatus): Promise<void> {
    const response = await fetch(`${apiBaseUrl}/tasks/${taskId}/status`, {
      method: "PATCH", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify({ status }),
    });
    if (!response.ok) throw new Error("Unable to save task status");
  }

  async function createTask(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setIsCreating(true); setError(null); setNotice(null);
    try {
      const payload = taskType === "feature"
        ? { task_type: taskType, title, description, project_id: projectId || null, acceptance_criteria: [] }
        : { task_type: taskType, title, description, project_id: projectId || null, severity: "medium", is_reproducible: true };
      const response = await fetch(`${apiBaseUrl}/tasks`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify(payload) });
      if (!response.ok) throw new Error("Unable to create task");
      setTitle(""); setDescription(""); setNotice("Task created.");
      await loadTasks();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to create task"); }
    finally { setIsCreating(false); }
  }

  const analyzeTask = useCallback(async (taskId: string) => {
    setError(null); setNotice(null);
    const response = await fetch(`${apiBaseUrl}/tasks/${taskId}/analyze-ai`, { method: "POST", headers: { Authorization: `Bearer ${token}` } });
    const payload = await response.json() as { estimated_story_points?: number; detail?: string };
    if (!response.ok) { setError(payload.detail ?? "AI analysis failed"); return; }
    setNotice(`AI estimate: ${payload.estimated_story_points} story points.`);
  }, [token]);

  const refreshAfterTaskCreated = useCallback(() => { void loadTasks(); }, [loadTasks]);

  if (!token) return <Login onAuthenticated={(accessToken, userRole) => { localStorage.setItem("smart_jira_access_token", accessToken); localStorage.setItem("smart_jira_role", userRole); setToken(accessToken); setRole(userRole as Role); }} />;
  if (isLoading) return <main className="grid min-h-screen place-items-center p-6 text-slate-600">Loading board…</main>;
  if (error && tasks.length === 0) return <main className="grid min-h-screen place-items-center p-6 text-rose-700">{error}</main>;
  return <>
    <main className="bg-slate-50 px-4 pt-6 sm:px-6 lg:px-8">
      <form onSubmit={createTask} className="mx-auto max-w-screen-2xl rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap gap-3">
          <input required value={title} onChange={(event) => setTitle(event.target.value)} maxLength={255} placeholder="New task title" className="min-w-52 flex-1 rounded border border-slate-300 px-3 py-2" />
          <input value={description} onChange={(event) => setDescription(event.target.value)} maxLength={20_000} placeholder="Description" className="min-w-52 flex-[2] rounded border border-slate-300 px-3 py-2" />
          <select value={projectId} onChange={(event) => setProjectId(event.target.value)} className="rounded border border-slate-300 px-3 py-2"><option value="">No project</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.key} — {project.name}</option>)}</select>
          <select value={taskType} onChange={(event) => setTaskType(event.target.value as "feature" | "bug")} className="rounded border border-slate-300 px-3 py-2"><option value="feature">Feature</option><option value="bug">Bug</option></select>
          <button disabled={isCreating} className="rounded bg-blue-600 px-4 py-2 font-semibold text-white disabled:opacity-50">{isCreating ? "Creating…" : "Create task"}</button>
        </div>
        {(error || notice) && <p className={`mt-3 text-sm ${error ? "text-rose-700" : "text-emerald-700"}`}>{error ?? notice}</p>}
      </form>
    </main>
    <KanbanDashboard initialTasks={tasks} webSocketUrl={authenticatedWebSocketUrl} onStatusChange={saveStatusChange} onTaskCreated={refreshAfterTaskCreated} onAnalyzeTask={analyzeTask} canAnalyze={role === "Admin" || role === "ProjectManager"} />
  </>;
}

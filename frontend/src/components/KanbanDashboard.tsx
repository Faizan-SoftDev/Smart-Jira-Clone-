import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent } from "react";

import { useKanbanSocket } from "../hooks/useKanbanSocket";
import { KANBAN_STATUSES, type KanbanStatus, type KanbanTask, type TaskStatusChangedEvent } from "../types/kanban";

interface KanbanDashboardProps {
  initialTasks: KanbanTask[];
  webSocketUrl: string;
  onStatusChange?: (taskId: string, status: KanbanStatus) => Promise<void> | void;
  onTaskCreated?: () => void;
  onAnalyzeTask?: (taskId: string) => Promise<void>;
  canAnalyze?: boolean;
}

const columns: ReadonlyArray<{ status: KanbanStatus; label: string; description: string; accent: string; count: string }> = [
  { status: "todo", label: "To do", description: "Ready to start", accent: "bg-slate-400", count: "bg-slate-200 text-slate-600" },
  { status: "in_progress", label: "In progress", description: "Being worked on", accent: "bg-blue-500", count: "bg-blue-100 text-blue-700" },
  { status: "in_review", label: "In review", description: "Awaiting feedback", accent: "bg-amber-500", count: "bg-amber-100 text-amber-700" },
  { status: "done", label: "Done", description: "Completed work", accent: "bg-emerald-500", count: "bg-emerald-100 text-emerald-700" },
];

const priorityClasses: Record<KanbanTask["priority"], string> = {
  low: "bg-slate-100 text-slate-600 ring-slate-200",
  medium: "bg-blue-50 text-blue-700 ring-blue-100",
  high: "bg-amber-50 text-amber-700 ring-amber-100",
  critical: "bg-rose-50 text-rose-700 ring-rose-100",
};

export function KanbanDashboard({ initialTasks, webSocketUrl, onStatusChange, onTaskCreated, onAnalyzeTask, canAnalyze = false }: KanbanDashboardProps) {
  const [tasks, setTasks] = useState<KanbanTask[]>(initialTasks);
  const [draggedTaskId, setDraggedTaskId] = useState<string | null>(null);
  const [activeDropStatus, setActiveDropStatus] = useState<KanbanStatus | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const tasksRef = useRef(tasks);

  useEffect(() => { setTasks(initialTasks); tasksRef.current = initialTasks; }, [initialTasks]);
  const updateTasks = useCallback((updater: (currentTasks: KanbanTask[]) => KanbanTask[]) => {
    setTasks((currentTasks) => { const nextTasks = updater(currentTasks); tasksRef.current = nextTasks; return nextTasks; });
  }, []);
  const handleSocketStatusChange = useCallback((event: TaskStatusChangedEvent) => {
    updateTasks((currentTasks) => currentTasks.map((task) => task.id === event.task_id ? { ...task, status: event.status } : task));
  }, [updateTasks]);
  useKanbanSocket({ url: webSocketUrl, onTaskStatusChanged: handleSocketStatusChange, onTaskCreated });

  const tasksByStatus = useMemo(() => KANBAN_STATUSES.reduce<Record<KanbanStatus, KanbanTask[]>>((grouped, status) => {
    grouped[status] = tasks.filter((task) => task.status === status); return grouped;
  }, { todo: [], in_progress: [], in_review: [], done: [] }), [tasks]);

  function onDragStart(event: DragEvent<HTMLElement>, taskId: string): void {
    event.dataTransfer.effectAllowed = "move"; event.dataTransfer.setData("text/plain", taskId); setDraggedTaskId(taskId); setErrorMessage(null);
  }
  function onDragOver(event: DragEvent<HTMLElement>, status: KanbanStatus): void { event.preventDefault(); event.dataTransfer.dropEffect = "move"; setActiveDropStatus(status); }
  async function onDrop(event: DragEvent<HTMLElement>, nextStatus: KanbanStatus): Promise<void> {
    event.preventDefault(); const taskId = event.dataTransfer.getData("text/plain") || draggedTaskId; setActiveDropStatus(null); setDraggedTaskId(null);
    const task = tasksRef.current.find((candidate) => candidate.id === taskId);
    if (!task || task.status === nextStatus) return;
    const previousStatus = task.status;
    updateTasks((current) => current.map((candidate) => candidate.id === task.id ? { ...candidate, status: nextStatus } : candidate));
    try { await onStatusChange?.(task.id, nextStatus); } catch {
      updateTasks((current) => current.map((candidate) => candidate.id === task.id ? { ...candidate, status: previousStatus } : candidate));
      setErrorMessage("The task status could not be saved. Please try again.");
    }
  }

  return (
    <section aria-label="Kanban board">
      {errorMessage && <div className="mb-5 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700" role="alert"><span aria-hidden="true">!</span>{errorMessage}</div>}
      <div className="kanban-scroll -mx-4 overflow-x-auto px-4 pb-4 sm:-mx-6 sm:px-6">
        <div className="grid min-w-[1120px] grid-cols-4 gap-4 xl:min-w-0">
          {columns.map((column) => {
            const columnTasks = tasksByStatus[column.status];
            return <section key={column.status} aria-label={column.label} className={`min-h-[28rem] rounded-2xl border p-3 transition-all duration-200 ${activeDropStatus === column.status ? "border-blue-400 bg-blue-50/80 shadow-lg shadow-blue-950/5" : "border-slate-200/80 bg-slate-100/70"}`} onDragOver={(event) => onDragOver(event, column.status)} onDragLeave={() => setActiveDropStatus(null)} onDrop={(event) => void onDrop(event, column.status)}>
              <header className="mb-3 flex items-start justify-between gap-3 px-1 pt-1">
                <div className="flex items-start gap-2.5"><span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${column.accent}`} /><div><h2 className="text-sm font-semibold text-slate-800">{column.label}</h2><p className="mt-0.5 text-xs text-slate-500">{column.description}</p></div></div>
                <span className={`grid h-6 min-w-6 place-items-center rounded-full px-1.5 text-xs font-semibold ${column.count}`}>{columnTasks.length}</span>
              </header>
              <div className="space-y-3">
                {columnTasks.map((task) => <article key={task.id} draggable className={`group cursor-grab rounded-xl border bg-white p-4 shadow-sm transition duration-200 hover:-translate-y-0.5 hover:border-blue-200 hover:shadow-md active:cursor-grabbing ${draggedTaskId === task.id ? "opacity-50" : "border-slate-200/90"}`} onDragStart={(event) => onDragStart(event, task.id)} onDragEnd={() => { setDraggedTaskId(null); setActiveDropStatus(null); }}>
                  <div className="mb-3 flex items-center justify-between gap-3"><span className="text-[11px] font-bold uppercase tracking-[0.14em] text-slate-400">{task.task_type}</span><span className={`rounded-md px-2 py-1 text-[11px] font-semibold capitalize ring-1 ring-inset ${priorityClasses[task.priority]}`}>{task.priority}</span></div>
                  <h3 className="text-sm font-semibold leading-5 text-slate-800">{task.title}</h3>
                  {task.description && <p className="mt-2 line-clamp-3 text-sm leading-5 text-slate-500">{task.description}</p>}
                  <footer className="mt-4 flex items-center justify-between border-t border-slate-100 pt-3 text-xs text-slate-400"><span className="font-medium">#{task.id.slice(0, 8)}</span><span className={task.assignee_id ? "text-slate-500" : "text-slate-400"}>{task.assignee_id ? "Assigned" : "Unassigned"}</span></footer>
                  {canAnalyze && onAnalyzeTask && <button type="button" onClick={() => void onAnalyzeTask(task.id)} className="mt-3 text-xs font-semibold text-blue-600 transition hover:text-blue-800 focus:outline-none focus:ring-2 focus:ring-blue-200">✦ Analyze with AI</button>}
                </article>)}
                {columnTasks.length === 0 && <div className="grid min-h-32 place-items-center rounded-xl border border-dashed border-slate-300 bg-white/45 px-4 text-center"><p className="text-xs leading-5 text-slate-400">Drop a task here<br />to update its status</p></div>}
              </div>
            </section>;
          })}
        </div>
      </div>
      <p className="mt-1 text-center text-xs text-slate-400 xl:hidden">Swipe horizontally to view every workflow column.</p>
    </section>
  );
}

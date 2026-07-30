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

const columns: ReadonlyArray<{ status: KanbanStatus; label: string; accent: string }> = [
  { status: "todo", label: "To Do", accent: "bg-slate-400" },
  { status: "in_progress", label: "In Progress", accent: "bg-blue-500" },
  { status: "in_review", label: "In Review", accent: "bg-amber-500" },
  { status: "done", label: "Done", accent: "bg-emerald-500" },
];

const priorityClasses: Record<KanbanTask["priority"], string> = {
  low: "bg-slate-100 text-slate-700",
  medium: "bg-blue-50 text-blue-700",
  high: "bg-amber-50 text-amber-700",
  critical: "bg-rose-50 text-rose-700",
};

export function KanbanDashboard({ initialTasks, webSocketUrl, onStatusChange, onTaskCreated, onAnalyzeTask, canAnalyze = false }: KanbanDashboardProps) {
  const [tasks, setTasks] = useState<KanbanTask[]>(initialTasks);
  const [draggedTaskId, setDraggedTaskId] = useState<string | null>(null);
  const [activeDropStatus, setActiveDropStatus] = useState<KanbanStatus | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const tasksRef = useRef(tasks);

  useEffect(() => {
    setTasks(initialTasks);
    tasksRef.current = initialTasks;
  }, [initialTasks]);

  const updateTasks = useCallback((updater: (currentTasks: KanbanTask[]) => KanbanTask[]) => {
    setTasks((currentTasks) => {
      const nextTasks = updater(currentTasks);
      tasksRef.current = nextTasks;
      return nextTasks;
    });
  }, []);

  const handleSocketStatusChange = useCallback((event: TaskStatusChangedEvent) => {
    updateTasks((currentTasks) =>
      currentTasks.map((task) => (task.id === event.task_id ? { ...task, status: event.status } : task)),
    );
  }, [updateTasks]);

  useKanbanSocket({ url: webSocketUrl, onTaskStatusChanged: handleSocketStatusChange, onTaskCreated });

  const tasksByStatus = useMemo(
    () =>
      KANBAN_STATUSES.reduce<Record<KanbanStatus, KanbanTask[]>>(
        (groupedTasks, status) => {
          groupedTasks[status] = tasks.filter((task) => task.status === status);
          return groupedTasks;
        },
        { todo: [], in_progress: [], in_review: [], done: [] },
      ),
    [tasks],
  );

  function onDragStart(event: DragEvent<HTMLElement>, taskId: string): void {
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", taskId);
    setDraggedTaskId(taskId);
    setErrorMessage(null);
  }

  function onDragOver(event: DragEvent<HTMLElement>, status: KanbanStatus): void {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    setActiveDropStatus(status);
  }

  async function onDrop(event: DragEvent<HTMLElement>, nextStatus: KanbanStatus): Promise<void> {
    event.preventDefault();
    const taskId = event.dataTransfer.getData("text/plain") || draggedTaskId;
    setActiveDropStatus(null);
    setDraggedTaskId(null);

    const task = tasksRef.current.find((candidate) => candidate.id === taskId);
    if (!task || task.status === nextStatus) {
      return;
    }

    const previousStatus = task.status;
    updateTasks((currentTasks) =>
      currentTasks.map((candidate) => (candidate.id === task.id ? { ...candidate, status: nextStatus } : candidate)),
    );

    try {
      await onStatusChange?.(task.id, nextStatus);
    } catch {
      updateTasks((currentTasks) =>
        currentTasks.map((candidate) =>
          candidate.id === task.id ? { ...candidate, status: previousStatus } : candidate,
        ),
      );
      setErrorMessage("The task status could not be saved. Please try again.");
    }
  }

  return (
    <section className="min-h-screen bg-slate-50 px-4 py-8 text-slate-900 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-screen-2xl">
        <header className="mb-8 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-widest text-blue-600">Smart Jira</p>
            <h1 className="mt-1 text-3xl font-bold tracking-tight">Kanban Board</h1>
          </div>
          <p className="text-sm text-slate-500">Drag a task card to update its workflow status.</p>
        </header>

        {errorMessage && (
          <div className="mb-5 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700" role="alert">
            {errorMessage}
          </div>
        )}

        <div className="grid gap-5 lg:grid-cols-4">
          {columns.map((column) => (
            <section
              key={column.status}
              aria-label={column.label}
              className={`min-h-[32rem] rounded-xl border p-3 transition-colors ${
                activeDropStatus === column.status ? "border-blue-400 bg-blue-50" : "border-slate-200 bg-slate-100/70"
              }`}
              onDragOver={(event) => onDragOver(event, column.status)}
              onDragLeave={() => setActiveDropStatus(null)}
              onDrop={(event) => void onDrop(event, column.status)}
            >
              <div className="mb-3 flex items-center justify-between px-1">
                <div className="flex items-center gap-2">
                  <span className={`h-2.5 w-2.5 rounded-full ${column.accent}`} />
                  <h2 className="font-semibold text-slate-800">{column.label}</h2>
                </div>
                <span className="rounded-full bg-white px-2 py-0.5 text-xs font-medium text-slate-500">
                  {tasksByStatus[column.status].length}
                </span>
              </div>

              <div className="space-y-3">
                {tasksByStatus[column.status].map((task) => (
                  <article
                    key={task.id}
                    draggable
                    className="cursor-grab rounded-lg border border-slate-200 bg-white p-4 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md active:cursor-grabbing"
                    onDragStart={(event) => onDragStart(event, task.id)}
                    onDragEnd={() => {
                      setDraggedTaskId(null);
                      setActiveDropStatus(null);
                    }}
                  >
                    <div className="mb-3 flex items-start justify-between gap-3">
                      <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">{task.task_type}</span>
                      <span className={`rounded-full px-2 py-1 text-xs font-medium capitalize ${priorityClasses[task.priority]}`}>
                        {task.priority}
                      </span>
                    </div>
                    <h3 className="font-semibold leading-5 text-slate-800">{task.title}</h3>
                    {task.description && <p className="mt-2 line-clamp-3 text-sm leading-5 text-slate-500">{task.description}</p>}
                    <footer className="mt-4 flex items-center justify-between text-xs text-slate-400">
                      <span>#{task.id.slice(0, 8)}</span>
                      <span>{task.assignee_id ? "Assigned" : "Unassigned"}</span>
                    </footer>
                    {canAnalyze && onAnalyzeTask && <button type="button" onClick={() => void onAnalyzeTask(task.id)} className="mt-3 text-xs font-semibold text-blue-600 hover:text-blue-800">Analyze with AI</button>}
                  </article>
                ))}
              </div>
            </section>
          ))}
        </div>
      </div>
    </section>
  );
}

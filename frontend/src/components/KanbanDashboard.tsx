import { useState, type DragEvent } from "react";
import type { ProjectBoard } from "../types/kanban";

interface Props { board: ProjectBoard; onMove: (issueId: string, targetStatusId: string) => Promise<void>; }
const priority: Record<string, string> = { highest: "bg-rose-100 text-rose-700", high: "bg-amber-100 text-amber-700", medium: "bg-blue-100 text-blue-700", low: "bg-slate-100 text-slate-600", lowest: "bg-slate-100 text-slate-500" };

export function KanbanDashboard({ board, onMove }: Props) {
  const [dragged, setDragged] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function drop(event: DragEvent<HTMLElement>, statusId: string) {
    event.preventDefault(); const issueId = event.dataTransfer.getData("text/plain") || dragged;
    setDragged(null); if (!issueId || busy) return;
    setBusy(true); setError(null); try { await onMove(issueId, statusId); } catch (reason) { setError(reason instanceof Error ? reason.message : "Move could not be saved."); } finally { setBusy(false); }
  }
  return <section aria-label="Kanban board">
    {error && <p className="mb-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
    <div className="kanban-scroll overflow-x-auto pb-5"><div className="grid min-w-[900px] gap-4" style={{ gridTemplateColumns: `repeat(${Math.max(board.columns.length, 1)}, minmax(250px, 1fr))` }}>
      {board.columns.map((column) => <section key={column.id} onDragOver={(event) => event.preventDefault()} onDrop={(event) => void drop(event, column.id)} className="min-h-[28rem] rounded-2xl border border-slate-200 bg-slate-100/80 p-3">
        <header className="mb-3 flex items-center justify-between px-1"><div><h2 className="font-semibold text-slate-800">{column.name}</h2><p className="text-xs capitalize text-slate-500">{column.category.replace("_", " ")}</p></div><span className="rounded-full bg-white px-2.5 py-1 text-xs font-bold text-slate-600">{column.issues.length}</span></header>
        <div className="space-y-3">{column.issues.map((issue) => <article key={issue.id} draggable onDragStart={(event) => { event.dataTransfer.setData("text/plain", issue.id); setDragged(issue.id); }} className={`cursor-grab rounded-xl border border-slate-200 bg-white p-4 shadow-sm ${dragged === issue.id ? "opacity-50" : ""}`}>
          <div className="mb-2 flex justify-between gap-2"><span className="text-xs font-bold text-slate-400">{issue.key}</span><span className={`rounded px-2 py-0.5 text-[11px] font-semibold ${priority[issue.priority]}`}>{issue.priority}</span></div>
          <h3 className="text-sm font-semibold text-slate-800">{issue.title}</h3>{issue.description && <p className="mt-2 line-clamp-3 text-sm text-slate-500">{issue.description}</p>}
          <p className="mt-3 text-xs text-slate-400">{issue.issue_type} · {issue.assignee_user_id ? "Assigned" : "Unassigned"}</p>
        </article>)}{column.issues.length === 0 && <div className="rounded-xl border border-dashed border-slate-300 p-6 text-center text-xs text-slate-400">Drop an issue here</div>}</div>
      </section>)}</div></div>{busy && <p className="text-center text-sm text-slate-500">Saving board move…</p>}
  </section>;
}

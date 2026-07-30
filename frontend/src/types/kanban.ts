export const KANBAN_STATUSES = ["todo", "in_progress", "in_review", "done"] as const;

export type KanbanStatus = (typeof KANBAN_STATUSES)[number];

export interface KanbanTask {
  id: string;
  title: string;
  description: string;
  status: KanbanStatus;
  priority: "low" | "medium" | "high" | "critical";
  task_type: "feature" | "bug";
  assignee_id: string | null;
}

export interface TaskStatusChangedEvent {
  event: "task.status_changed";
  task_id: string;
  previous_status: KanbanStatus;
  status: KanbanStatus;
  occurred_at: string;
}

export interface TaskCreatedEvent {
  event: "task.created";
  task_id: string;
  occurred_at: string;
}

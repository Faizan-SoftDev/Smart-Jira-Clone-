import { useEffect, useRef } from "react";

import type { KanbanStatus, TaskCreatedEvent, TaskStatusChangedEvent } from "../types/kanban";

const validStatuses = new Set<KanbanStatus>(["todo", "in_progress", "in_review", "done"]);

function isTaskStatusChangedEvent(value: unknown): value is TaskStatusChangedEvent {
  if (!value || typeof value !== "object") {
    return false;
  }

  const event = value as Partial<TaskStatusChangedEvent>;
  return (
    event.event === "task.status_changed" &&
    typeof event.task_id === "string" &&
    typeof event.previous_status === "string" &&
    validStatuses.has(event.previous_status as KanbanStatus) &&
    typeof event.status === "string" &&
    validStatuses.has(event.status as KanbanStatus) &&
    typeof event.occurred_at === "string"
  );
}

interface UseKanbanSocketOptions {
  url: string;
  onTaskStatusChanged: (event: TaskStatusChangedEvent) => void;
  onTaskCreated?: (event: TaskCreatedEvent) => void;
  reconnectDelayMs?: number;
}

export function useKanbanSocket({
  url,
  onTaskStatusChanged,
  onTaskCreated,
  reconnectDelayMs = 3_000,
}: UseKanbanSocketOptions): void {
  const callbackRef = useRef(onTaskStatusChanged);

  useEffect(() => {
    callbackRef.current = onTaskStatusChanged;
  }, [onTaskStatusChanged]);

  useEffect(() => {
    let socket: WebSocket | undefined;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
    let isDisposed = false;

    const connect = () => {
      socket = new WebSocket(url);

      socket.onmessage = (messageEvent: MessageEvent<string>) => {
        try {
          const event: unknown = JSON.parse(messageEvent.data);
          if (isTaskStatusChangedEvent(event)) {
            callbackRef.current(event);
          } else if (
            event && typeof event === "object" &&
            (event as Partial<TaskCreatedEvent>).event === "task.created" &&
            typeof (event as Partial<TaskCreatedEvent>).task_id === "string"
          ) {
            onTaskCreated?.(event as TaskCreatedEvent);
          }
        } catch {
          return;
        }
      };

      socket.onclose = () => {
        if (!isDisposed) {
          reconnectTimer = setTimeout(connect, reconnectDelayMs);
        }
      };
    };

    connect();

    return () => {
      isDisposed = true;
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
      }
      socket?.close();
    };
  }, [onTaskCreated, reconnectDelayMs, url]);
}

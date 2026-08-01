import { useEffect, useRef } from "react";

interface BoardEvent { event: string; issue_id?: string; }

export function useKanbanSocket(url: string | null, onEvent: (event: BoardEvent) => void): void {
  const callback = useRef(onEvent);
  useEffect(() => { callback.current = onEvent; }, [onEvent]);
  useEffect(() => {
    if (!url) return;
    let socket: WebSocket | undefined;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let closed = false;
    const connect = () => {
      socket = new WebSocket(url);
      socket.onmessage = ({ data }) => {
        try { const event = JSON.parse(data) as BoardEvent; if (event.event) callback.current(event); } catch { /* ignore malformed frames */ }
      };
      socket.onclose = () => { if (!closed) retry = setTimeout(connect, 3000); };
    };
    connect();
    return () => { closed = true; if (retry) clearTimeout(retry); socket?.close(); };
  }, [url]);
}

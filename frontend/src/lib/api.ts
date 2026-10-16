export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export type StreamEvent =
  | { type: "meta"; thread_id: string }
  | { type: "agent"; agent: string; status: "running" | "done" | "failed"; ms?: number }
  | { type: "plan"; allowed: boolean; mode: string; selected_agents: string[]; trip_constraints: Record<string, unknown>; reasoning: string }
  | { type: "provider"; node: string; provider: string }
  | { type: "token"; node: string; content: string }
  | { type: "reset"; node: string }
  | { type: "interrupt"; thread_id: string; approval_request: string; draft: string }
  | { type: "done"; result: Record<string, unknown> }
  | { type: "status"; message: string }
  | { type: "error"; message: string };

async function streamPost(path: string, body: unknown, onEvent: (e: StreamEvent) => void, signal?: AbortSignal) {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail || `Request failed (${res.status})`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let index;
    while ((index = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, index);
      buffer = buffer.slice(index + 2);
      for (const line of block.split("\n")) {
        if (line.startsWith("data: ")) {
          try {
            onEvent(JSON.parse(line.slice(6)) as StreamEvent);
          } catch {}
        }
      }
    }
  }
}

export const streamChat = (message: string, threadId: string | null, onEvent: (e: StreamEvent) => void, signal?: AbortSignal) =>
  streamPost("/api/chat/stream", { message, thread_id: threadId }, onEvent, signal);

export const streamReview = (threadId: string, approved: boolean, feedback: string, onEvent: (e: StreamEvent) => void, signal?: AbortSignal) =>
  streamPost("/api/chat/approve/stream", { thread_id: threadId, approved, feedback }, onEvent, signal);

export async function pingHealth(timeoutMs = 60000): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}/health`, { signal: AbortSignal.timeout(timeoutMs) });
    return res.ok;
  } catch {
    return false;
  }
}

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { pingHealth, streamChat, streamReview, type StreamEvent } from "./api";

export type AgentStatus = "running" | "done" | "failed";

export type AgentStep = { agent: string; status: AgentStatus; ms?: number };

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  kind?: "draft" | "final" | "answer" | "blocked" | "error";
  steps?: AgentStep[];
  provider?: string;
  constraints?: Record<string, unknown>;
  awaitingReview?: boolean;
  streaming?: boolean;
  notice?: string;
};

export type ServerState = "checking" | "waking" | "ready" | "offline";

const STORAGE_KEY = "tripgraph.chat.v1";

const uid = () => Math.random().toString(36).slice(2, 10) + Date.now().toString(36);

function load(): { threadId: string | null; messages: ChatMessage[] } {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { threadId: null, messages: [] };
    const parsed = JSON.parse(raw);
    const messages: ChatMessage[] = (parsed.messages ?? []).map((m: ChatMessage) => ({
      ...m,
      streaming: false,
      steps: m.steps?.map((s) => (s.status === "running" ? { ...s, status: "failed" as const } : s)),
    }));
    return { threadId: parsed.threadId ?? null, messages };
  } catch {
    return { threadId: null, messages: [] };
  }
}

export function useTripChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [server, setServer] = useState<ServerState>("checking");
  const [hydrated, setHydrated] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const threadRef = useRef<string | null>(null);
  const busyRef = useRef(false);

  useEffect(() => {
    const saved = load();
    setMessages(saved.messages);
    setThreadId(saved.threadId);
    threadRef.current = saved.threadId;
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated || busy) return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ threadId, messages: messages.slice(-40) }));
    } catch {}
  }, [messages, threadId, busy, hydrated]);

  useEffect(() => {
    let cancelled = false;
    const slow = setTimeout(() => !cancelled && setServer((s) => (s === "checking" ? "waking" : s)), 2500);
    pingHealth(75000).then((ok) => {
      if (!cancelled) setServer(ok ? "ready" : "offline");
    });
    return () => {
      cancelled = true;
      clearTimeout(slow);
    };
  }, []);

  const patch = useCallback((id: string, update: (m: ChatMessage) => ChatMessage) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? update(m) : m)));
  }, []);

  const run = useCallback(
    async (start: (onEvent: (e: StreamEvent) => void, signal: AbortSignal) => Promise<void>, assistantId: string) => {
      controller.current?.abort();
      const abort = new AbortController();
      controller.current = abort;
      busyRef.current = true;
      setBusy(true);

      let pending = "";
      let pendingKind: ChatMessage["kind"];
      let frame = 0;
      const flush = () => {
        if (frame) cancelAnimationFrame(frame);
        frame = 0;
        if (!pending) return;
        const text = pending;
        const kind = pendingKind;
        pending = "";
        patch(assistantId, (m) => ({ ...m, content: m.content + text, kind: kind ?? m.kind, notice: undefined }));
      };

      const handle = (event: StreamEvent) => {
        if (event.type === "token") {
          pending += event.content;
          if (event.node === "itinerary_agent") pendingKind = "draft";
          else if (event.node === "guardrail_blocked") pendingKind = "blocked";
          if (!frame) frame = requestAnimationFrame(flush);
          return;
        }
        flush();
        switch (event.type) {
          case "meta":
            threadRef.current = event.thread_id;
            setThreadId(event.thread_id);
            break;
          case "plan":
            patch(assistantId, (m) => ({ ...m, constraints: event.trip_constraints }));
            break;
          case "agent":
            patch(assistantId, (m) => {
              const steps = [...(m.steps ?? [])];
              const index = steps.findIndex((s) => s.agent === event.agent && s.status === "running");
              const step = { agent: event.agent, status: event.status, ms: event.ms };
              if (index >= 0) steps[index] = step;
              else steps.push(step);
              return { ...m, steps };
            });
            break;
          case "provider":
            patch(assistantId, (m) => ({ ...m, provider: event.provider }));
            break;
          case "status":
            patch(assistantId, (m) => ({ ...m, notice: event.message }));
            break;
          case "reset":
            patch(assistantId, (m) => ({ ...m, content: "" }));
            break;
          case "interrupt":
            patch(assistantId, (m) => ({ ...m, kind: "draft", awaitingReview: true }));
            break;
          case "done": {
            const result = event.result as { mode?: string; requires_approval?: boolean; answer?: string };
            patch(assistantId, (m) => ({
              ...m,
              content: m.content || result.answer || "",
              kind: result.requires_approval ? "draft" : m.kind === "blocked" ? "blocked" : result.mode === "plan" ? "final" : "answer",
              awaitingReview: Boolean(result.requires_approval),
            }));
            break;
          }
          case "error":
            patch(assistantId, (m) => ({ ...m, kind: "error", content: m.content || event.message }));
            break;
        }
      };

      try {
        await start(handle, abort.signal);
        flush();
        setServer("ready");
      } catch (error) {
        flush();
        if (abort.signal.aborted) {
          patch(assistantId, (m) => ({ ...m, content: m.content || "Stopped.", kind: m.kind ?? "answer" }));
        } else {
          const offline = error instanceof TypeError;
          if (offline) setServer("offline");
          patch(assistantId, (m) => ({
            ...m,
            kind: "error",
            content: offline
              ? "I couldn't reach the planning server. It may be waking up - please try again in a few seconds."
              : (error as Error).message,
          }));
        }
      } finally {
        patch(assistantId, (m) => ({
          ...m,
          streaming: false,
          notice: undefined,
          steps: m.steps?.map((s) => (s.status === "running" ? { ...s, status: "failed" } : s)),
        }));
        if (controller.current === abort) controller.current = null;
        busyRef.current = false;
        setBusy(false);
      }
    },
    [patch]
  );

  const send = useCallback(
    (text: string) => {
      const message = text.trim();
      if (!message || busyRef.current) return;
      busyRef.current = true;
      const assistantId = uid();
      setMessages((prev) => [
        ...prev.map((m) => ({ ...m, awaitingReview: false })),
        { id: uid(), role: "user", content: message },
        { id: assistantId, role: "assistant", content: "", steps: [], streaming: true },
      ]);
      void run((onEvent, signal) => streamChat(message, threadRef.current, onEvent, signal), assistantId);
    },
    [run]
  );

  const review = useCallback(
    (approved: boolean, feedback = "") => {
      const thread = threadRef.current;
      if (!thread || busyRef.current) return;
      busyRef.current = true;
      const assistantId = uid();
      setMessages((prev) => [
        ...prev.map((m) => ({ ...m, awaitingReview: false })),
        {
          id: uid(),
          role: "user",
          content: approved ? "Looks good - approve this plan." : `Please change: ${feedback.trim()}`,
        },
        { id: assistantId, role: "assistant", content: "", steps: [], streaming: true },
      ]);
      void run((onEvent, signal) => streamReview(thread, approved, feedback, onEvent, signal), assistantId);
    },
    [run]
  );

  const stop = useCallback(() => controller.current?.abort(), []);

  const reset = useCallback(() => {
    controller.current?.abort();
    setMessages([]);
    setThreadId(null);
    threadRef.current = null;
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {}
  }, []);

  return { messages, threadId, busy, server, hydrated, send, review, stop, reset };
}

import { vi } from "vitest";

export function sseBody(events: object[], { split = false } = {}) {
  const text = ": connected\n\n" + events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");
  const encoder = new TextEncoder();
  const chunks = split ? text.match(/[\s\S]{1,7}/g) ?? [] : [text];
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
}

export function sseResponse(events: object[], options?: { split?: boolean }) {
  return new Response(sseBody(events, options), {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });
}

export function jsonResponse(status: number, body: object) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

export function mockFetch(...responses: (Response | Error)[]) {
  const fetchMock = vi.fn();
  fetchMock.mockImplementation((url: string) => {
    if (String(url).endsWith("/health")) return Promise.resolve(jsonResponse(200, { status: "ok" }));
    const next = responses.shift();
    if (!next) return Promise.reject(new Error("unexpected fetch"));
    return next instanceof Error ? Promise.reject(next) : Promise.resolve(next);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

export const planEvents = [
  { type: "meta", thread_id: "thread-1" },
  { type: "agent", agent: "supervisor", status: "running" },
  {
    type: "plan",
    allowed: true,
    mode: "plan",
    selected_agents: ["flight_agent"],
    trip_constraints: { destination: "Kuala Lumpur", duration_days: 3 },
    reasoning: "",
  },
  { type: "agent", agent: "supervisor", status: "done", ms: 600 },
  { type: "agent", agent: "itinerary_agent", status: "running" },
  { type: "provider", node: "itinerary_agent", provider: "groq" },
  { type: "token", node: "itinerary_agent", content: "## Draft: KL" },
  { type: "token", node: "itinerary_agent", content: " Food Trip" },
  { type: "agent", agent: "itinerary_agent", status: "done", ms: 1200 },
  { type: "interrupt", thread_id: "thread-1", approval_request: "Review", draft: "## Draft: KL Food Trip" },
  { type: "done", result: { mode: "plan", requires_approval: true, answer: "## Draft: KL Food Trip" } },
];

export const finalEvents = [
  { type: "meta", thread_id: "thread-1" },
  { type: "agent", agent: "final_agent", status: "running" },
  { type: "token", node: "final_agent", content: "## Trip Summary" },
  { type: "agent", agent: "final_agent", status: "done", ms: 900 },
  { type: "done", result: { mode: "plan", requires_approval: false, answer: "## Trip Summary" } },
];

import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useTripChat } from "./useTripChat";
import { finalEvents, jsonResponse, mockFetch, planEvents, sseResponse } from "@/test/sse";

async function setup() {
  const hook = renderHook(() => useTripChat());
  await waitFor(() => expect(hook.result.current.hydrated).toBe(true));
  await waitFor(() => expect(hook.result.current.server).toBe("ready"));
  return hook;
}

describe("useTripChat", () => {
  it("streams a draft, tracks agents and waits for review", async () => {
    mockFetch(sseResponse(planEvents));
    const { result } = await setup();

    act(() => result.current.send("Plan KL"));
    await waitFor(() => expect(result.current.busy).toBe(false));

    const [user, assistant] = result.current.messages;
    expect(user).toMatchObject({ role: "user", content: "Plan KL" });
    expect(assistant).toMatchObject({
      role: "assistant",
      content: "## Draft: KL Food Trip",
      kind: "draft",
      awaitingReview: true,
      provider: "groq",
      streaming: false,
      constraints: { destination: "Kuala Lumpur", duration_days: 3 },
    });
    expect(assistant.steps).toEqual([
      { agent: "supervisor", status: "done", ms: 600 },
      { agent: "itinerary_agent", status: "done", ms: 1200 },
    ]);
    expect(result.current.threadId).toBe("thread-1");
  });

  it("approves on the same thread and produces the final plan", async () => {
    const fetchMock = mockFetch(sseResponse(planEvents), sseResponse(finalEvents));
    const { result } = await setup();

    act(() => result.current.send("Plan KL"));
    await waitFor(() => expect(result.current.busy).toBe(false));
    act(() => result.current.review(true));
    await waitFor(() => expect(result.current.busy).toBe(false));

    const reviewCall = fetchMock.mock.calls.find(([url]) => String(url).includes("/approve/stream"));
    expect(JSON.parse(reviewCall![1].body)).toEqual({ thread_id: "thread-1", approved: true, feedback: "" });
    const last = result.current.messages.at(-1)!;
    expect(last).toMatchObject({ kind: "final", content: "## Trip Summary", awaitingReview: false });
    expect(result.current.messages.filter((m) => m.awaitingReview)).toHaveLength(0);
  });

  it("continues the conversation on the existing thread", async () => {
    const fetchMock = mockFetch(sseResponse(planEvents), sseResponse(finalEvents));
    const { result } = await setup();
    act(() => result.current.send("first"));
    await waitFor(() => expect(result.current.busy).toBe(false));
    act(() => result.current.send("second"));
    await waitFor(() => expect(result.current.busy).toBe(false));
    const bodies = fetchMock.mock.calls
      .filter(([url]) => String(url).endsWith("/api/chat/stream"))
      .map(([, init]) => JSON.parse(init.body));
    expect(bodies).toEqual([
      { message: "first", thread_id: null },
      { message: "second", thread_id: "thread-1" },
    ]);
  });

  it("drops partial text when the server switches provider mid-answer", async () => {
    mockFetch(
      sseResponse([
        { type: "meta", thread_id: "t" },
        { type: "token", node: "final_agent", content: "broken half" },
        { type: "reset", node: "final_agent" },
        { type: "token", node: "final_agent", content: "Clean answer" },
        { type: "done", result: { mode: "answer", requires_approval: false } },
      ])
    );
    const { result } = await setup();
    act(() => result.current.send("hi"));
    await waitFor(() => expect(result.current.busy).toBe(false));
    expect(result.current.messages[1]).toMatchObject({ content: "Clean answer", kind: "answer" });
  });

  it("shows server errors and rate limits to the user", async () => {
    mockFetch(
      sseResponse([{ type: "meta", thread_id: "t" }, { type: "error", message: "All AI providers are unavailable" }]),
      jsonResponse(429, { detail: "You're sending requests too quickly." })
    );
    const { result } = await setup();

    act(() => result.current.send("one"));
    await waitFor(() => expect(result.current.busy).toBe(false));
    expect(result.current.messages[1]).toMatchObject({ kind: "error", content: "All AI providers are unavailable" });

    act(() => result.current.send("two"));
    await waitFor(() => expect(result.current.busy).toBe(false));
    expect(result.current.messages[3]).toMatchObject({ kind: "error", content: "You're sending requests too quickly." });
  });

  it("marks the server offline when the network fails", async () => {
    mockFetch(new TypeError("Failed to fetch"));
    const { result } = await setup();
    act(() => result.current.send("hi"));
    await waitFor(() => expect(result.current.busy).toBe(false));
    expect(result.current.server).toBe("offline");
    expect(result.current.messages[1].content).toMatch(/couldn't reach the planning server/);
  });

  it("ignores empty messages and messages sent while busy", async () => {
    const fetchMock = mockFetch(sseResponse(planEvents));
    const { result } = await setup();
    act(() => result.current.send("   "));
    expect(result.current.messages).toHaveLength(0);
    act(() => {
      result.current.send("Plan KL");
      result.current.send("again");
    });
    await waitFor(() => expect(result.current.busy).toBe(false));
    expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith("/api/chat/stream"))).toHaveLength(1);
  });

  it("persists the conversation and restores it after reload", async () => {
    mockFetch(sseResponse(planEvents));
    const first = await setup();
    act(() => first.result.current.send("Plan KL"));
    await waitFor(() => expect(first.result.current.busy).toBe(false));
    await waitFor(() => expect(localStorage.getItem("tripgraph.chat.v1")).toContain("thread-1"));
    first.unmount();

    const second = await setup();
    expect(second.result.current.threadId).toBe("thread-1");
    expect(second.result.current.messages).toHaveLength(2);

    act(() => second.result.current.reset());
    expect(second.result.current.messages).toHaveLength(0);
    await waitFor(() =>
      expect(JSON.parse(localStorage.getItem("tripgraph.chat.v1") ?? "{}")).toEqual({ threadId: null, messages: [] })
    );
  });

  it("recovers gracefully from corrupted saved state", async () => {
    localStorage.setItem("tripgraph.chat.v1", "{not json");
    mockFetch();
    const { result } = await setup();
    expect(result.current.messages).toEqual([]);
  });

  it("shows a waiting notice while providers are busy and clears it when text arrives", async () => {
    let push: (chunk: string) => void = () => {};
    let close: () => void = () => {};
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        push = (chunk) => controller.enqueue(new TextEncoder().encode(chunk));
        close = () => controller.close();
      },
    });
    mockFetch(new Response(body, { status: 200 }));
    const { result } = await setup();
    act(() => result.current.send("hi"));
    push('data: {"type":"meta","thread_id":"t"}\n\ndata: {"type":"status","message":"High demand"}\n\n');
    await waitFor(() => expect(result.current.messages[1].notice).toBe("High demand"));
    push('data: {"type":"token","node":"final_agent","content":"Hi!"}\n\n');
    close();
    await waitFor(() => expect(result.current.busy).toBe(false));
    expect(result.current.messages[1]).toMatchObject({ content: "Hi!", notice: undefined });
  });
});

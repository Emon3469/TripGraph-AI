import { describe, expect, it, vi } from "vitest";
import { API_URL, pingHealth, streamChat, streamReview, type StreamEvent } from "./api";
import { jsonResponse, mockFetch, planEvents, sseResponse } from "@/test/sse";

describe("streaming client", () => {
  it("parses every event even when chunks split lines mid-way", async () => {
    mockFetch(sseResponse(planEvents, { split: true }));
    const received: StreamEvent[] = [];
    await streamChat("Plan KL", null, (e) => received.push(e));
    expect(received).toEqual(planEvents);
  });

  it("posts the message and thread id as JSON", async () => {
    const fetchMock = mockFetch(sseResponse([{ type: "meta", thread_id: "t" }]));
    await streamChat("hello", "t", () => {});
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${API_URL}/api/chat/stream`);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ message: "hello", thread_id: "t" });
  });

  it("sends review decisions to the approval endpoint", async () => {
    const fetchMock = mockFetch(sseResponse([]));
    await streamReview("t", false, "more food", () => {});
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${API_URL}/api/chat/approve/stream`);
    expect(JSON.parse(init.body)).toEqual({ thread_id: "t", approved: false, feedback: "more food" });
  });

  it("ignores comments, pings and malformed lines", async () => {
    const body = new ReadableStream({
      start(c) {
        c.enqueue(new TextEncoder().encode(': ping\n\ndata: {broken\n\ndata: {"type":"reset","node":"x"}\n\n'));
        c.close();
      },
    });
    mockFetch(new Response(body, { status: 200 }));
    const received: StreamEvent[] = [];
    await streamChat("x", null, (e) => received.push(e));
    expect(received).toEqual([{ type: "reset", node: "x" }]);
  });

  it("surfaces the server's error detail", async () => {
    mockFetch(jsonResponse(429, { detail: "Please wait 30 seconds and try again." }));
    await expect(streamChat("x", null, () => {})).rejects.toThrow("Please wait 30 seconds");
  });

  it("falls back to a generic message for non-JSON errors", async () => {
    mockFetch(new Response("Bad gateway", { status: 502 }));
    await expect(streamChat("x", null, () => {})).rejects.toThrow("Request failed (502)");
  });

  it("reports server health", async () => {
    mockFetch();
    await expect(pingHealth()).resolves.toBe(true);
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    await expect(pingHealth()).resolves.toBe(false);
  });
});

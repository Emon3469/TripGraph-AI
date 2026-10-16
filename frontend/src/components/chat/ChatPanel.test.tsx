import { render, renderHook, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { useTripChat } from "@/lib/useTripChat";
import { finalEvents, mockFetch, planEvents, sseResponse } from "@/test/sse";
import ChatPanel from "./ChatPanel";

function Harness() {
  const chat = useTripChat();
  return <ChatPanel chat={chat} />;
}

describe("ChatPanel", () => {
  it("shows suggestions and sends one when clicked", async () => {
    const fetchMock = mockFetch(sseResponse(planEvents));
    render(<Harness />);
    const suggestion = await screen.findByRole("button", { name: /Kuala Lumpur for 2/ });
    await userEvent.click(suggestion);
    expect(await screen.findByText("Draft itinerary - awaiting your review")).toBeInTheDocument();
    const body = JSON.parse(fetchMock.mock.calls.find(([u]) => String(u).endsWith("/stream"))![1].body);
    expect(body.message).toContain("Kuala Lumpur");
  });

  it("renders markdown, agent chips and the provider", async () => {
    mockFetch(sseResponse(planEvents));
    render(<Harness />);
    await userEvent.type(await screen.findByPlaceholderText(/describe your dream trip/), "Plan KL{Enter}");
    expect(await screen.findByRole("heading", { name: "Draft: KL Food Trip" })).toBeInTheDocument();
    expect(screen.getByText("Supervisor")).toBeInTheDocument();
    expect(screen.getByText("0.6s")).toBeInTheDocument();
    expect(screen.getByText("Answered via groq")).toBeInTheDocument();
  });

  it("approves a draft from the review bar", async () => {
    mockFetch(sseResponse(planEvents), sseResponse(finalEvents));
    render(<Harness />);
    await userEvent.type(await screen.findByPlaceholderText(/describe your dream trip/), "Plan KL{Enter}");
    await userEvent.click(await screen.findByRole("button", { name: /Approve plan/ }));
    expect(await screen.findByText("Final travel plan")).toBeInTheDocument();
    expect(screen.getByText("Looks good - approve this plan.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Approve plan/ })).not.toBeInTheDocument();
  });

  it("sends requested changes from the review bar", async () => {
    const fetchMock = mockFetch(sseResponse(planEvents), sseResponse(planEvents));
    render(<Harness />);
    await userEvent.type(await screen.findByPlaceholderText(/describe your dream trip/), "Plan KL{Enter}");
    await userEvent.click(await screen.findByRole("button", { name: /Request changes/ }));
    const send = screen.getByRole("button", { name: "Send changes" });
    expect(send).toBeDisabled();
    await userEvent.type(screen.getByPlaceholderText(/Swap day 2/), "Add Malacca{Enter}");
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([u]) => String(u).includes("/approve/stream"))).toBe(true)
    );
    const call = fetchMock.mock.calls.find(([u]) => String(u).includes("/approve/stream"))!;
    expect(JSON.parse(call[1].body)).toEqual({ thread_id: "thread-1", approved: false, feedback: "Add Malacca" });
    expect(await screen.findByText("Please change: Add Malacca")).toBeInTheDocument();
  });

  it("keeps the send button disabled for empty input and allows multi-line with shift+enter", async () => {
    mockFetch();
    render(<Harness />);
    const input = await screen.findByPlaceholderText(/describe your dream trip/);
    expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled();
    await userEvent.type(input, "line one{Shift>}{Enter}{/Shift}line two");
    expect(input).toHaveValue("line one\nline two");
    expect(screen.getByRole("button", { name: "Send message" })).toBeEnabled();
  });

  it("shows a stop button while streaming", async () => {
    let release: () => void = () => {};
    const body = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode('data: {"type":"meta","thread_id":"t"}\n\n'));
        release = () => controller.close();
      },
    });
    mockFetch(new Response(body, { status: 200 }));
    render(<Harness />);
    await userEvent.type(await screen.findByPlaceholderText(/describe your dream trip/), "hi{Enter}");
    const stop = await screen.findByRole("button", { name: "Stop generating" });
    await userEvent.click(stop);
    release();
    expect(await screen.findByRole("button", { name: "Send message" })).toBeInTheDocument();
  });

  it("restores history for the drawer and planner from storage", async () => {
    mockFetch(sseResponse(planEvents));
    const { result } = renderHook(() => useTripChat());
    await waitFor(() => expect(result.current.hydrated).toBe(true));
    result.current.send("Plan KL");
    await waitFor(() => expect(localStorage.getItem("tripgraph.chat.v1")).toContain("Draft"));

    render(<Harness />);
    const log = await screen.findByText("Plan KL");
    expect(within(log.parentElement!).getByText("Plan KL")).toBeInTheDocument();
  });
});

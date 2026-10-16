"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import clsx from "clsx";
import { ArrowUp, Loader2, Square, Sparkles, WifiOff } from "lucide-react";
import { suggestions, traveller } from "@/lib/data";
import type { ChatMessage, useTripChat } from "@/lib/useTripChat";
import AgentSteps from "./AgentSteps";
import Markdown from "./Markdown";
import ReviewBar from "./ReviewBar";

type Chat = ReturnType<typeof useTripChat>;

const KIND_LABEL: Partial<Record<NonNullable<ChatMessage["kind"]>, string>> = {
  draft: "Draft itinerary - awaiting your review",
  final: "Final travel plan",
};

function BotAvatar() {
  return (
    <span className="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-brand-400 to-brand-600 text-white shadow-brand">
      <Sparkles size={15} />
    </span>
  );
}

function Thinking() {
  return (
    <span className="inline-flex items-center gap-1 py-1">
      {[0, 150, 300].map((delay) => (
        <span
          key={delay}
          className="h-1.5 w-1.5 animate-bounce rounded-full bg-brand-400"
          style={{ animationDelay: `${delay}ms` }}
        />
      ))}
    </span>
  );
}

function Message({ message, chat }: { message: ChatMessage; chat: Chat }) {
  if (message.role === "user") {
    return (
      <div className="flex animate-fade-up justify-end gap-2.5">
        <div className="max-w-[85%] rounded-2xl rounded-tr-md bg-gradient-to-br from-brand-400 to-brand-600 px-4 py-2.5 text-[13.5px] whitespace-pre-wrap text-white shadow-brand">
          {message.content}
        </div>
        <span className="relative h-8 w-8 shrink-0 overflow-hidden rounded-xl bg-brand-50">
          <Image src={traveller.avatar} alt="" fill sizes="32px" />
        </span>
      </div>
    );
  }

  const label = message.kind ? KIND_LABEL[message.kind] : undefined;

  return (
    <div className="flex animate-fade-up gap-2.5">
      <BotAvatar />
      <div className="min-w-0 flex-1">
        {!!message.steps?.length && (
          <div className="mb-2">
            <AgentSteps steps={message.steps} />
          </div>
        )}
        <div
          className={clsx(
            "rounded-2xl rounded-tl-md border px-4 py-3",
            message.kind === "error" && "border-rose-100 bg-rose-50 text-[13.5px] text-rose-600",
            message.kind === "blocked" && "border-amber-100 bg-amber-50",
            message.kind === "final" && "border-emerald-100 bg-white shadow-card",
            !["error", "blocked", "final"].includes(message.kind ?? "") && "border-ink-200 bg-white shadow-card"
          )}
        >
          {label && (
            <p
              className={clsx(
                "mb-2 inline-flex rounded-full px-2.5 py-0.5 text-[10.5px] font-semibold tracking-wide uppercase",
                message.kind === "final" ? "bg-emerald-50 text-emerald-700" : "bg-violet-50 text-violet-brand"
              )}
            >
              {label}
            </p>
          )}
          {message.content ? (
            message.kind === "error" ? (
              <p>{message.content}</p>
            ) : (
              <Markdown content={message.content} />
            )
          ) : (
            message.streaming && (
              <div className="flex items-center gap-2">
                <Thinking />
                {message.notice && <span className="text-[12px] text-amber-600">{message.notice}</span>}
              </div>
            )
          )}
          {message.streaming && message.content && (
            <span className="ml-0.5 inline-block h-4 w-[2px] translate-y-0.5 animate-blink bg-brand-500" />
          )}
        </div>
        {message.provider && !message.streaming && message.kind !== "error" && (
          <p className="mt-1.5 pl-1 text-[10.5px] text-ink-400">Answered via {message.provider}</p>
        )}
        {message.awaitingReview && !message.streaming && (
          <ReviewBar disabled={chat.busy} onReview={chat.review} />
        )}
      </div>
    </div>
  );
}

export default function ChatPanel({ chat, compact = false }: { chat: Chat; compact?: boolean }) {
  const [input, setInput] = useState("");
  const scroller = useRef<HTMLDivElement>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const pinned = useRef(true);

  const last = chat.messages[chat.messages.length - 1];

  useEffect(() => {
    const el = scroller.current;
    if (el && pinned.current) el.scrollTop = el.scrollHeight;
  }, [chat.messages, last?.content]);

  useEffect(() => {
    const el = textarea.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [input]);

  const submit = (text = input) => {
    if (!text.trim() || chat.busy) return;
    chat.send(text);
    setInput("");
    pinned.current = true;
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      {chat.server !== "ready" && chat.server !== "checking" && (
        <div
          className={clsx(
            "mx-4 mt-3 flex items-center gap-2 rounded-xl px-3 py-2 text-[12px]",
            chat.server === "waking" ? "bg-amber-50 text-amber-700" : "bg-rose-50 text-rose-600"
          )}
        >
          {chat.server === "waking" ? (
            <>
              <Loader2 size={13} className="animate-spin" /> Waking up the planning server - the first request can take up to a minute.
            </>
          ) : (
            <>
              <WifiOff size={13} /> Planning server is unreachable right now. Messages will retry when you send.
            </>
          )}
        </div>
      )}

      <div
        ref={scroller}
        onScroll={(e) => {
          const el = e.currentTarget;
          pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
        }}
        className="flex-1 space-y-5 overflow-y-auto px-4 py-5 scrollbar-thin sm:px-5"
      >
        {chat.hydrated && chat.messages.length === 0 && (
          <div className={clsx("mx-auto flex max-w-xl flex-col items-center text-center", compact ? "pt-4" : "pt-10")}>
            <span className="grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-brand-400 to-brand-600 text-white shadow-brand">
              <Sparkles size={24} />
            </span>
            <h2 className="mt-4 text-[18px] font-bold">Where to next, {traveller.firstName}?</h2>
            <p className="mt-1.5 text-[13px] text-ink-500">
              Specialist agents check flights, hotels, live weather and your budget, then draft an itinerary for you to approve.
            </p>
            <div className={clsx("mt-5 grid w-full gap-2", !compact && "sm:grid-cols-2")}>
              {suggestions.map((text) => (
                <button
                  key={text}
                  type="button"
                  onClick={() => submit(text)}
                  className="rounded-2xl border border-ink-200 bg-white px-4 py-3 text-left text-[12.5px] font-medium text-ink-700 shadow-card transition hover:-translate-y-0.5 hover:border-brand-200 hover:text-ink-900"
                >
                  {text}
                </button>
              ))}
            </div>
          </div>
        )}
        {chat.messages.map((message) => (
          <Message key={message.id} message={message} chat={chat} />
        ))}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className="border-t border-ink-100 bg-white px-4 pt-3 pb-4 sm:px-5"
      >
        <div className="flex items-end gap-2 rounded-2xl border border-ink-200 bg-ink-50 p-1.5 pl-4 transition focus-within:border-brand-300 focus-within:bg-white focus-within:ring-4 focus-within:ring-brand-50">
          <textarea
            ref={textarea}
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                submit();
              }
            }}
            maxLength={4000}
            placeholder="Ask anything or describe your dream trip..."
            className="max-h-40 flex-1 resize-none bg-transparent py-2 text-[13.5px] outline-none placeholder:text-ink-400"
          />
          {chat.busy ? (
            <button
              type="button"
              onClick={chat.stop}
              aria-label="Stop generating"
              className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-ink-900 text-white"
            >
              <Square size={13} className="fill-white" />
            </button>
          ) : (
            <button
              type="submit"
              disabled={!input.trim()}
              aria-label="Send message"
              className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-brand-400 to-brand-600 text-white shadow-brand transition disabled:from-ink-300 disabled:to-ink-300 disabled:shadow-none"
            >
              <ArrowUp size={17} strokeWidth={2.5} />
            </button>
          )}
        </div>
        <p className="mt-2 text-center text-[10.5px] text-ink-400">
          Prices and forecasts are estimates - confirm before booking.
        </p>
      </form>
    </div>
  );
}

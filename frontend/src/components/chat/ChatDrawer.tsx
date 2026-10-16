"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import clsx from "clsx";
import { Maximize2, MessageCircle, Sparkles, X } from "lucide-react";
import { useTripChat } from "@/lib/useTripChat";
import ChatPanel from "./ChatPanel";

export default function ChatDrawer() {
  const [open, setOpen] = useState(false);
  const chat = useTripChat();

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Open trip assistant"
        className={clsx(
          "fixed right-5 bottom-5 z-30 flex items-center gap-2 rounded-full bg-gradient-to-r from-brand-400 to-brand-600 py-3 pr-5 pl-4 text-[13px] font-semibold text-white shadow-brand transition hover:-translate-y-0.5 animate-pulse-ring",
          open && "pointer-events-none opacity-0"
        )}
      >
        <MessageCircle size={18} /> Ask TripGraph
      </button>

      <div
        className={clsx(
          "fixed inset-0 z-40 bg-ink-900/20 backdrop-blur-[2px] transition-opacity",
          open ? "opacity-100" : "pointer-events-none opacity-0"
        )}
        onClick={() => setOpen(false)}
      />

      <div
        role="dialog"
        aria-label="Trip assistant"
        className={clsx(
          "fixed inset-y-0 right-0 z-50 flex w-full flex-col bg-white shadow-2xl transition-transform duration-300 sm:inset-y-3 sm:right-3 sm:w-[440px] sm:rounded-3xl sm:border sm:border-ink-200",
          open ? "translate-x-0" : "translate-x-[calc(100%+24px)]"
        )}
      >
        <div className="flex items-center gap-3 border-b border-ink-100 px-4 py-3">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-brand-400 to-brand-600 text-white">
            <Sparkles size={16} />
          </span>
          <div className="flex-1">
            <p className="text-[14px] font-bold">TripGraph Assistant</p>
            <p className="text-[11px] text-ink-400">Flights, stays, weather and budgets</p>
          </div>
          <Link
            href="/planner"
            aria-label="Open full planner"
            className="grid h-8 w-8 place-items-center rounded-lg text-ink-500 transition hover:bg-ink-50"
          >
            <Maximize2 size={15} />
          </Link>
          <button
            type="button"
            onClick={() => setOpen(false)}
            aria-label="Close assistant"
            className="grid h-8 w-8 place-items-center rounded-lg text-ink-500 transition hover:bg-ink-50"
          >
            <X size={17} />
          </button>
        </div>
        <div className="min-h-0 flex-1">{open && <ChatPanel chat={chat} compact />}</div>
      </div>
    </>
  );
}

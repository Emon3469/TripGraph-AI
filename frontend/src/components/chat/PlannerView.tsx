"use client";

import { useEffect, useMemo, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { BedDouble, CloudSun, Map, Plane, RotateCcw, ShieldCheck, UserCheck, Wallet } from "lucide-react";
import { useTripChat } from "@/lib/useTripChat";
import ChatPanel from "./ChatPanel";

const PIPELINE = [
  { icon: ShieldCheck, title: "Supervisor & guardrail", text: "Validates the request and picks the specialists it needs." },
  { icon: Plane, title: "Flight agent", text: "Live route search for airlines, durations and fares." },
  { icon: BedDouble, title: "Hotel agent", text: "Finds stays across price levels in the right area." },
  { icon: CloudSun, title: "Weather agent", text: "Current conditions and a 5-day forecast via MCP." },
  { icon: Wallet, title: "Budget agent", text: "Breaks down costs and checks feasibility." },
  { icon: Map, title: "Itinerary agent", text: "Drafts a day-by-day plan from every finding." },
  { icon: UserCheck, title: "Your review", text: "Approve the draft or ask for changes before the final plan." },
];

const LABELS: Record<string, string> = {
  destination: "Destination",
  origin: "From",
  duration_days: "Days",
  dates: "Dates",
  travelers: "Travellers",
  budget: "Budget",
  travel_style: "Style",
};

export default function PlannerView() {
  const chat = useTripChat();
  const params = useSearchParams();
  const router = useRouter();
  const handled = useRef(false);

  useEffect(() => {
    if (!chat.hydrated || handled.current) return;
    const query = params.get("q");
    const fresh = params.get("new");
    if (!query && !fresh) return;
    handled.current = true;
    if (fresh || query) chat.reset();
    if (query) setTimeout(() => chat.send(query), 0);
    router.replace("/planner", { scroll: false });
  }, [chat, chat.hydrated, params, router]);

  const constraints = useMemo(() => {
    for (let i = chat.messages.length - 1; i >= 0; i--) {
      const c = chat.messages[i].constraints;
      if (c && Object.values(c).some((v) => v !== null && v !== "" && !(Array.isArray(v) && !v.length))) return c;
    }
    return null;
  }, [chat.messages]);

  return (
    <div className="flex h-dvh flex-col px-4 pt-16 pb-4 sm:px-6 lg:px-8 lg:pt-7">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-[22px] font-bold tracking-tight sm:text-[24px]">AI Trip Planner</h1>
          <p className="mt-1 text-[13px] text-ink-500">Chat with your multi-agent travel team. Answers stream in real time.</p>
        </div>
        <button
          type="button"
          onClick={chat.reset}
          className="inline-flex items-center gap-1.5 rounded-full border border-ink-200 bg-white px-4 py-2 text-[12.5px] font-semibold text-ink-700 transition hover:bg-ink-50"
        >
          <RotateCcw size={14} /> New chat
        </button>
      </header>

      <div className="mt-5 grid min-h-0 flex-1 gap-5 xl:grid-cols-[1fr_300px]">
        <section className="min-h-0 overflow-hidden rounded-3xl border border-ink-200 bg-ink-50/40 shadow-card">
          <ChatPanel chat={chat} />
        </section>

        <aside className="hidden min-h-0 space-y-4 overflow-y-auto scrollbar-thin xl:block">
          <div className="rounded-3xl border border-ink-200 bg-white p-4 shadow-card">
            <h2 className="text-[14px] font-bold">Trip snapshot</h2>
            {constraints ? (
              <dl className="mt-3 space-y-2">
                {Object.entries(LABELS).map(([key, label]) => {
                  const value = constraints[key];
                  if (value === null || value === undefined || value === "") return null;
                  return (
                    <div key={key} className="flex justify-between gap-3 text-[12.5px]">
                      <dt className="text-ink-400">{label}</dt>
                      <dd className="text-right font-semibold">{String(value)}</dd>
                    </div>
                  );
                })}
                {Array.isArray(constraints.interests) && constraints.interests.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {(constraints.interests as string[]).map((interest) => (
                      <span key={interest} className="rounded-full bg-brand-50 px-2.5 py-0.5 text-[11px] font-medium text-brand-600">
                        {interest}
                      </span>
                    ))}
                  </div>
                )}
              </dl>
            ) : (
              <p className="mt-2 text-[12.5px] text-ink-400">Details about your trip will appear here as you chat.</p>
            )}
          </div>

          <div className="rounded-3xl border border-ink-200 bg-white p-4 shadow-card">
            <h2 className="text-[14px] font-bold">How your plan is built</h2>
            <ol className="mt-3 space-y-3">
              {PIPELINE.map(({ icon: Icon, title, text }) => (
                <li key={title} className="flex gap-3">
                  <span className="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-brand-50 text-brand-600">
                    <Icon size={15} />
                  </span>
                  <span>
                    <span className="block text-[12.5px] font-semibold">{title}</span>
                    <span className="block text-[11.5px] leading-snug text-ink-400">{text}</span>
                  </span>
                </li>
              ))}
            </ol>
          </div>
        </aside>
      </div>
    </div>
  );
}

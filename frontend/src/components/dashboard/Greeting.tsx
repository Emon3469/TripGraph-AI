"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Bell, Search } from "lucide-react";
import { traveller } from "@/lib/data";

function greetingFor(hour: number) {
  if (hour < 12) return "Good Morning";
  if (hour < 17) return "Good Afternoon";
  return "Good Evening";
}

function AppleIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-[15px] w-[15px]" fill="currentColor" aria-hidden>
      <path d="M16.37 1.43c0 1.14-.42 2.2-1.13 2.98-.85.94-2.03 1.49-3.17 1.4-.14-1.1.43-2.27 1.14-3.03.8-.86 2.15-1.48 3.16-1.35ZM20.5 17.1c-.55 1.27-.82 1.84-1.53 2.96-.99 1.56-2.39 3.5-4.12 3.51-1.54.02-1.94-1-4.03-.99-2.09.01-2.53 1.01-4.07.99-1.73-.02-3.05-1.77-4.04-3.33C-.07 15.88-.36 10.8 1.38 8.12c1.23-1.9 3.18-3.02 5.01-3.02 1.86 0 3.03 1.02 4.57 1.02 1.5 0 2.41-1.02 4.57-1.02 1.63 0 3.36.89 4.59 2.42-4.03 2.21-3.38 7.97.38 9.58Z" />
    </svg>
  );
}

function WindowsIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-[14px] w-[14px]" fill="#1e90ff" aria-hidden>
      <path d="M0 3.45 9.75 2.1v9.45H0V3.45Zm10.95-1.5L24 0v11.4H10.95V1.95ZM0 12.6h9.75v9.45L0 20.7v-8.1Zm10.95 0H24V24l-13.05-1.8V12.6Z" />
    </svg>
  );
}

export default function Greeting() {
  const [greeting, setGreeting] = useState("Good Morning");

  useEffect(() => setGreeting(greetingFor(new Date().getHours())), []);

  return (
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 className="text-[24px] font-bold tracking-tight sm:text-[26px]">
          {greeting}, {traveller.firstName} <span className="inline-block origin-[70%_70%] animate-wave">👋</span>
        </h1>
        <p className="mt-1 text-[13.5px] text-ink-500">Plan your itinerary with us</p>
      </div>

      <div className="flex items-center gap-2.5">
        <Link
          href="/planner"
          aria-label="Ask the trip planner"
          className="grid h-10 w-10 place-items-center rounded-full border border-ink-200 bg-white transition hover:bg-ink-50"
        >
          <Search size={17} />
        </Link>
        <button
          type="button"
          aria-label="Notifications"
          className="relative grid h-10 w-10 place-items-center rounded-full border border-ink-200 bg-white transition hover:bg-ink-50"
        >
          <Bell size={17} />
          <span className="absolute top-2.5 right-[11px] h-2 w-2 rounded-full bg-rose-500 ring-2 ring-white" />
        </button>
        <div className="hidden items-center gap-2 rounded-full border border-ink-200 bg-ink-50 px-3.5 py-2.5 text-[12.5px] font-medium text-ink-700 sm:flex">
          Get Apps:
          <AppleIcon />
          <WindowsIcon />
        </div>
      </div>
    </header>
  );
}

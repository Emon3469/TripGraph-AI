"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import {
  BookOpen,
  CalendarDays,
  Compass,
  Home,
  LogOut,
  PanelLeftClose,
  Plus,
  Users,
} from "lucide-react";
import { traveller, trips } from "@/lib/data";

const general = [
  { href: "/", label: "Dashboard", icon: Home },
  { href: "/planner", label: "Itinerary", icon: CalendarDays, badge: "NEW!" },
];

const discover = [
  { href: "/#explore", label: "Explore", icon: Compass },
  { href: "/#guide", label: "Guide", icon: BookOpen },
  { href: "/#friends", label: "Friends", icon: Users },
];

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="mb-2 px-1 text-[10.5px] font-semibold tracking-wider text-ink-400 uppercase">
      {children}
    </p>
  );
}

export default function Sidebar({ onClose }: { onClose?: () => void }) {
  const pathname = usePathname();

  return (
    <aside className="flex h-full w-[248px] flex-col border-r border-ink-200 bg-white px-4 py-5 lg:w-[228px]">
      <div className="flex items-center gap-3">
        <div className="relative h-10 w-10 overflow-hidden rounded-xl bg-brand-50">
          <Image src={traveller.avatar} alt={traveller.name} fill sizes="40px" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[13.5px] font-semibold">{traveller.name}</p>
          <p className="truncate text-[11px] text-ink-400">{traveller.role}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Collapse sidebar"
          className="grid h-8 w-8 place-items-center rounded-lg border border-ink-200 text-ink-700 transition hover:bg-ink-50"
        >
          <PanelLeftClose size={15} />
        </button>
      </div>

      <Link
        href="/planner?new=1"
        onClick={onClose}
        className="mt-6 flex items-center justify-center gap-2 rounded-full bg-gradient-to-r from-brand-400 to-brand-600 py-3 text-[13.5px] font-semibold text-white shadow-brand transition hover:brightness-105 active:scale-[0.98]"
      >
        <Plus size={16} strokeWidth={2.5} /> New Trip
      </Link>

      <div className="mt-6">
        <SectionLabel>Trips</SectionLabel>
        <div className="space-y-0.5 rounded-2xl bg-white p-1.5 shadow-card ring-1 ring-ink-100">
          {trips.map((trip) => (
            <Link
              key={trip.id}
              href={`/planner?q=${encodeURIComponent(`Plan a ${trip.days} day trip to ${trip.city} starting ${trip.date}`)}`}
              onClick={onClose}
              className="flex items-center gap-3 rounded-xl px-2 py-2 transition hover:bg-ink-50"
            >
              <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-ink-50">
                <Image src={trip.flag} alt="" width={20} height={14} className="rounded-[3px] shadow-sm" />
              </span>
              <span className="min-w-0">
                <span className="block truncate text-[12.5px] font-semibold">{trip.city}</span>
                <span className="block truncate text-[10.5px] text-ink-400">
                  {trip.days} Days, {trip.date}
                </span>
              </span>
            </Link>
          ))}
        </div>
      </div>

      <nav className="mt-6 flex-1 space-y-6 overflow-y-auto no-scrollbar">
        <div>
          <SectionLabel>General</SectionLabel>
          <ul className="space-y-1">
            {general.map(({ href, label, icon: Icon, badge }) => {
              const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
              return (
                <li key={href}>
                  <Link
                    href={href}
                    onClick={onClose}
                    className={clsx(
                      "flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] transition",
                      active ? "bg-ink-100 font-semibold text-ink-900" : "text-ink-500 hover:bg-ink-50 hover:text-ink-900"
                    )}
                  >
                    <Icon size={16} strokeWidth={active ? 2.4 : 2} />
                    <span className="flex-1">{label}</span>
                    {badge && (
                      <span className="rounded-md bg-violet-brand px-1.5 py-0.5 text-[9px] font-bold tracking-wide text-white">
                        {badge}
                      </span>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>

        <div>
          <SectionLabel>Discover</SectionLabel>
          <ul className="space-y-1">
            {discover.map(({ href, label, icon: Icon }) => (
              <li key={href}>
                <Link
                  href={href}
                  onClick={onClose}
                  className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] text-ink-500 transition hover:bg-ink-50 hover:text-ink-900"
                >
                  <Icon size={16} />
                  {label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </nav>

      <button
        type="button"
        className="mt-4 flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium text-rose-500 transition hover:bg-rose-50"
      >
        <LogOut size={16} /> Logout
      </button>
    </aside>
  );
}

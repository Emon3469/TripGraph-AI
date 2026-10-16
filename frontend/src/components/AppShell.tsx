"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { Menu } from "lucide-react";
import clsx from "clsx";
import Sidebar from "./Sidebar";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();

  useEffect(() => setOpen(false), [pathname]);

  return (
    <div className="flex min-h-dvh bg-white">
      <div
        className={clsx(
          "sticky top-0 hidden h-dvh shrink-0 transition-[margin] duration-300 lg:block",
          collapsed && "-ml-[228px]"
        )}
      >
        <Sidebar onClose={() => setCollapsed(true)} />
      </div>

      <div
        className={clsx(
          "fixed inset-0 z-40 bg-ink-900/30 backdrop-blur-[2px] transition-opacity lg:hidden",
          open ? "opacity-100" : "pointer-events-none opacity-0"
        )}
        onClick={() => setOpen(false)}
      />
      <div
        className={clsx(
          "fixed inset-y-0 left-0 z-50 transition-transform duration-300 lg:hidden",
          open ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <Sidebar onClose={() => setOpen(false)} />
      </div>

      <main className="min-w-0 flex-1">
        <button
          type="button"
          aria-label="Open menu"
          onClick={() => (window.innerWidth >= 1024 ? setCollapsed(false) : setOpen(true))}
          className={clsx(
            "fixed top-4 left-4 z-30 grid h-10 w-10 place-items-center rounded-xl border border-ink-200 bg-white shadow-card",
            collapsed ? "lg:grid" : "lg:hidden"
          )}
        >
          <Menu size={18} />
        </button>
        {children}
      </main>
    </div>
  );
}

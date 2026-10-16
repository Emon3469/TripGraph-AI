import Image from "next/image";
import Link from "next/link";
import clsx from "clsx";
import { upcomingTrips } from "@/lib/data";
import { AvatarStack, PillLink, SectionHeading } from "@/components/ui";

export default function UpcomingTrips() {
  return (
    <section>
      <SectionHeading
        title="Upcoming Trip"
        subtitle="Remember your upcoming trips!"
        action={<PillLink href="/planner">Details</PillLink>}
      />
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {upcomingTrips.map((trip) => (
          <Link
            key={trip.id}
            href={`/planner?q=${encodeURIComponent(trip.prompt)}`}
            className="group rounded-2xl border border-ink-200 bg-white p-3.5 shadow-card transition hover:-translate-y-0.5 hover:shadow-float"
          >
            <div className="flex items-start justify-between">
              <div className="relative h-11 w-11 overflow-hidden rounded-xl">
                <Image src={trip.image} alt={trip.title} fill sizes="44px" className="object-cover" />
              </div>
              <div
                className={clsx(
                  "flex overflow-hidden rounded-lg text-center",
                  trip.highlight ? "bg-gradient-to-br from-brand-400 to-brand-600 text-white" : "bg-ink-50 text-ink-700"
                )}
              >
                {[
                  [trip.day, trip.month],
                  [trip.duration, "Days"],
                ].map(([value, label], index) => (
                  <div
                    key={label}
                    className={clsx(
                      "px-2.5 py-1",
                      index === 1 && (trip.highlight ? "border-l border-white/30" : "border-l border-ink-200")
                    )}
                  >
                    <p className="text-[11.5px] leading-tight font-semibold">{value}</p>
                    <p className={clsx("text-[9px]", trip.highlight ? "text-white/80" : "text-ink-400")}>{label}</p>
                  </div>
                ))}
              </div>
            </div>
            <p className="mt-3 text-[13.5px] font-semibold">{trip.title}</p>
            <p className="text-[11.5px] text-ink-400">{trip.country}</p>
            <div className="mt-3 flex items-center justify-between border-t border-ink-100 pt-3">
              <p className="text-[12px] text-ink-500">
                Budget: <span className="font-bold text-ink-900">${trip.budget.toLocaleString("en-US")}</span>
              </p>
              <AvatarStack avatars={trip.companions} />
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}

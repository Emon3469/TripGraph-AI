import Image from "next/image";
import Link from "next/link";
import { Sparkles } from "lucide-react";
import { featuredItinerary as itinerary } from "@/lib/data";
import { Card } from "@/components/ui";

export default function ItineraryCard() {
  const stats = [
    { label: "Budget", value: `$${itinerary.budget.toLocaleString("en-US")}` },
    { label: "Person", value: itinerary.persons },
    { label: "Durations", value: itinerary.duration },
  ];

  return (
    <Card className="p-4" >
      <h2 id="guide" className="scroll-mt-6 truncate text-[17px] font-bold tracking-tight">
        {itinerary.title}
      </h2>
      <p className="mt-2 flex items-center gap-1.5 text-[12px] text-ink-500">
        Traveler:
        <span className="relative inline-block h-5 w-5 overflow-hidden rounded-full bg-ink-100">
          <Image src={itinerary.traveller.avatar} alt="" fill sizes="20px" />
        </span>
        <span className="font-semibold text-ink-900">{itinerary.traveller.name}</span>
      </p>

      <div className="relative mt-3 aspect-[16/10] overflow-hidden rounded-2xl">
        <Image
          src={itinerary.image}
          alt="Christ Church in Malacca"
          fill
          sizes="(max-width: 1280px) 100vw, 320px"
          className="object-cover"
        />
      </div>

      <p className="mt-4 text-[12px] font-medium text-ink-500">Details:</p>
      <div className="mt-2 grid grid-cols-3 gap-2">
        {stats.map((stat) => (
          <div key={stat.label} className="rounded-2xl bg-ink-50 px-2 py-3 text-center">
            <p className="text-[10.5px] text-ink-400">{stat.label}</p>
            <p className="mt-0.5 text-[14px] font-bold">{stat.value}</p>
          </div>
        ))}
      </div>

      <Link
        href={`/planner?q=${encodeURIComponent(itinerary.prompt)}`}
        className="mt-4 flex items-center justify-center gap-2 rounded-full border border-brand-200 bg-brand-50 py-2.5 text-[12.5px] font-semibold text-brand-600 transition hover:bg-brand-100"
      >
        <Sparkles size={14} /> Build a plan like this
      </Link>
    </Card>
  );
}

"use client";

import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import clsx from "clsx";
import { ArrowUpRight, Heart, Star } from "lucide-react";
import { places } from "@/lib/data";
import { PillLink } from "@/components/ui";

export default function PlacesSection() {
  const [liked, setLiked] = useState<Record<string, boolean>>(
    Object.fromEntries(places.map((place) => [place.id, place.liked]))
  );

  return (
    <section id="explore" className="scroll-mt-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="flex flex-wrap items-center gap-1.5 text-[19px] font-bold tracking-tight">
            For your
            <span className="bg-gradient-to-r from-violet-brand to-rose-500 bg-clip-text text-transparent">Malaysia</span>
            <span className="relative inline-block h-5 w-8 overflow-hidden rounded-md">
              <Image src="/images/places/malacca.jpg" alt="" fill sizes="32px" className="object-cover" />
            </span>
            <span className="text-ink-300">Trip</span>
          </h2>
          <p className="mt-1 text-[12.5px] text-ink-500">These can&apos;t be missed places</p>
        </div>
        <PillLink href={`/planner?q=${encodeURIComponent("What are the must-visit places in Malaysia?")}`}>
          Details
        </PillLink>
      </div>

      <div className="mt-4 space-y-3">
        {places.map((place, index) => (
          <article
            key={place.id}
            className="group flex flex-col gap-4 rounded-2xl p-1 transition hover:bg-ink-50 sm:flex-row"
          >
            <div className="relative h-40 w-full shrink-0 overflow-hidden rounded-2xl sm:h-[92px] sm:w-[118px]">
              <Image
                src={place.image}
                alt={place.title}
                fill
                sizes="(max-width: 640px) 100vw, 118px"
                className="object-cover transition duration-500 group-hover:scale-105"
              />
            </div>
            <div className="min-w-0 flex-1 py-0.5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="truncate text-[14.5px] font-semibold">{place.title}</h3>
                  <p className="mt-0.5 line-clamp-1 text-[12px] text-ink-500">{place.description}</p>
                  <p className="mt-1 flex items-center gap-1 text-[12px] font-semibold">
                    <Star size={13} className="fill-amber-400 text-amber-400" />
                    {place.rating}
                    <span className="font-normal text-ink-400">({place.reviews})</span>
                  </p>
                </div>
                <div className="flex shrink-0 gap-2">
                  <button
                    type="button"
                    aria-label={liked[place.id] ? "Remove from favourites" : "Add to favourites"}
                    onClick={() => setLiked((prev) => ({ ...prev, [place.id]: !prev[place.id] }))}
                    className="grid h-8 w-8 place-items-center rounded-full border border-ink-200 bg-white transition hover:scale-105"
                  >
                    <Heart
                      size={14}
                      className={clsx(liked[place.id] ? "fill-rose-500 text-rose-500" : "text-ink-700")}
                    />
                  </button>
                  <Link
                    href={`/planner?q=${encodeURIComponent(`Tell me about visiting ${place.title}: best time, tickets and tips`)}`}
                    aria-label={`Plan a visit to ${place.title}`}
                    className={clsx(
                      "grid h-8 w-8 place-items-center rounded-full transition hover:scale-105",
                      index === 0
                        ? "bg-gradient-to-br from-brand-400 to-brand-600 text-white shadow-brand"
                        : "border border-ink-200 bg-white text-ink-700"
                    )}
                  >
                    <ArrowUpRight size={15} />
                  </Link>
                </div>
              </div>
              <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                <p className="flex items-center gap-1.5 text-[11.5px] text-ink-400">
                  Guide by:
                  <span className="relative inline-block h-5 w-5 overflow-hidden rounded-full bg-ink-100">
                    <Image src={place.guide.avatar} alt="" fill sizes="20px" />
                  </span>
                  <span className="font-medium text-ink-700">{place.guide.name}</span>
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {place.tags.map((tag) => (
                    <span key={tag.label} className={clsx("rounded-full px-2.5 py-0.5 text-[10.5px] font-medium", tag.tone)}>
                      {tag.label}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

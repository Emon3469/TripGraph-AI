import Image from "next/image";
import Link from "next/link";
import clsx from "clsx";
import { stories } from "@/lib/data";

export default function StoryStrip() {
  return (
    <div className="-mx-1 flex gap-2.5 overflow-x-auto px-1 pt-1 pb-4 no-scrollbar">
      {stories.map((story) => (
        <Link
          key={story.id}
          href={`/planner?q=${encodeURIComponent(`Give me a travel guide for ${story.label}`)}`}
          className="group relative shrink-0"
          title={story.label}
        >
          <div
            className={clsx(
              "relative h-[60px] w-[46px] overflow-hidden rounded-xl ring-2 ring-offset-2 transition group-hover:-translate-y-0.5 sm:h-[62px] sm:w-[48px]",
              story.ring,
              story.seen && "opacity-80"
            )}
          >
            <Image
              src={story.image}
              alt={story.label}
              fill
              sizes="60px"
              className="object-cover transition duration-500 group-hover:scale-110"
            />
          </div>
          <div className="absolute -bottom-2.5 left-1/2 h-6 w-6 -translate-x-1/2 overflow-hidden rounded-full bg-white ring-2 ring-white">
            <Image src={story.avatar} alt="" fill sizes="24px" />
          </div>
        </Link>
      ))}
    </div>
  );
}

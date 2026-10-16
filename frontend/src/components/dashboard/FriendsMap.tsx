import Image from "next/image";
import DottedMap from "dotted-map";
import { friends } from "@/lib/data";
import { Card, PillLink } from "@/components/ui";

const map = new DottedMap({ height: 70, grid: "diagonal" });

const svg = map.getSVG({
  radius: 0.24,
  color: "#d9d9e1",
  shape: "circle",
  backgroundColor: "transparent",
});

const viewBox = svg.match(/viewBox="([^"]+)"/)?.[1].split(" ").map(Number) ?? [0, 0, 1, 1];
const [, , width, height] = viewBox;
const mapSrc = `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;

const pins = friends.map((friend) => {
  const point = map.getPin({ lat: friend.lat, lng: friend.lng });
  return {
    ...friend,
    left: ((point?.x ?? 0) / width) * 100,
    top: ((point?.y ?? 0) / height) * 100,
  };
});

export default function FriendsMap() {
  return (
    <Card className="flex h-full flex-col p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-[19px] font-bold tracking-tight">Friends Location</h2>
          <p className="mt-1 text-[12.5px] text-ink-500">Check on your friend live location</p>
        </div>
        <PillLink href="/#friends">Expand</PillLink>
      </div>

      <div className="relative mt-4 flex-1">
        <div className="relative mx-auto aspect-[2/1] w-full">
          <Image src={mapSrc} alt="World map" fill unoptimized className="object-contain select-none" priority />
          {pins.map((pin) => (
            <div
              key={pin.name}
              className="absolute -translate-x-1/2 -translate-y-full"
              style={{ left: `${pin.left}%`, top: `${pin.top}%` }}
            >
              <div className="flex flex-col items-center">
                <div className="flex items-center gap-2">
                  <span className="relative block h-8 w-8 overflow-hidden rounded-full bg-white shadow-float ring-2 ring-white sm:h-9 sm:w-9">
                    <Image src={pin.avatar} alt={pin.name} fill sizes="36px" />
                  </span>
                  {pin.showLabel && (
                    <span className="hidden rounded-xl bg-white/95 px-2.5 py-1.5 whitespace-nowrap shadow-float backdrop-blur sm:block">
                      <span className="block text-[12.5px] leading-tight font-semibold">{pin.name}</span>
                      <span className="block text-[10.5px] text-ink-400">{pin.country}</span>
                    </span>
                  )}
                </div>
                <span className="mt-1 flex gap-[3px]">
                  {[0, 1, 2].map((dot) => (
                    <span key={dot} className="h-[5px] w-[5px] rounded-full bg-brand-500" style={{ opacity: 1 - dot * 0.25 }} />
                  ))}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

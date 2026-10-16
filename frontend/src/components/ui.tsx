import Image from "next/image";
import Link from "next/link";
import clsx from "clsx";

export function SectionHeading({
  title,
  subtitle,
  action,
}: {
  title: React.ReactNode;
  subtitle?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div>
        <h2 className="text-[19px] font-bold tracking-tight">{title}</h2>
        {subtitle && <p className="mt-1 text-[12.5px] text-ink-500">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function PillLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="shrink-0 rounded-full bg-brand-50 px-4 py-2 text-[12px] font-semibold text-brand-600 transition hover:bg-brand-100"
    >
      {children}
    </Link>
  );
}

export function AvatarStack({ avatars, size = 22 }: { avatars: string[]; size?: number }) {
  return (
    <div className="flex -space-x-1.5">
      {avatars.map((src) => (
        <span
          key={src}
          className="relative overflow-hidden rounded-full bg-ink-100 ring-2 ring-white"
          style={{ width: size, height: size }}
        >
          <Image src={src} alt="" fill sizes={`${size}px`} />
        </span>
      ))}
    </div>
  );
}

export function Card({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <div className={clsx("rounded-3xl border border-ink-200 bg-white shadow-card", className)}>{children}</div>
  );
}

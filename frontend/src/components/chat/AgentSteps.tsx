import clsx from "clsx";
import {
  BedDouble,
  Check,
  CloudSun,
  Loader2,
  Map,
  PenLine,
  Plane,
  ShieldCheck,
  Wallet,
  X,
  type LucideIcon,
} from "lucide-react";
import type { AgentStep } from "@/lib/useTripChat";

const AGENTS: Record<string, { label: string; icon: LucideIcon }> = {
  supervisor: { label: "Supervisor", icon: ShieldCheck },
  guardrail_blocked: { label: "Guardrail", icon: ShieldCheck },
  flight_agent: { label: "Flights", icon: Plane },
  hotel_agent: { label: "Hotels", icon: BedDouble },
  weather_agent: { label: "Weather", icon: CloudSun },
  budget_agent: { label: "Budget", icon: Wallet },
  itinerary_agent: { label: "Itinerary", icon: Map },
  final_agent: { label: "Writing", icon: PenLine },
};

export default function AgentSteps({ steps }: { steps: AgentStep[] }) {
  if (!steps.length) return null;

  return (
    <div className="flex flex-wrap gap-1.5">
      {steps.map((step, index) => {
        const meta = AGENTS[step.agent] ?? { label: step.agent, icon: Check };
        const Icon = meta.icon;
        return (
          <span
            key={`${step.agent}-${index}`}
            className={clsx(
              "inline-flex animate-fade-up items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium",
              step.status === "running" && "border-brand-200 bg-brand-50 text-brand-700",
              step.status === "done" && "border-emerald-100 bg-emerald-50 text-emerald-700",
              step.status === "failed" && "border-rose-100 bg-rose-50 text-rose-600"
            )}
          >
            <Icon size={12} />
            {meta.label}
            {step.status === "running" && <Loader2 size={11} className="animate-spin" />}
            {step.status === "done" && (
              <>
                <Check size={11} strokeWidth={3} />
                {step.ms !== undefined && step.ms > 0 && (
                  <span className="text-emerald-600/70">{(step.ms / 1000).toFixed(1)}s</span>
                )}
              </>
            )}
            {step.status === "failed" && <X size={11} strokeWidth={3} />}
          </span>
        );
      })}
    </div>
  );
}

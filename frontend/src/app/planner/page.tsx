import { Suspense } from "react";
import type { Metadata } from "next";
import AppShell from "@/components/AppShell";
import PlannerView from "@/components/chat/PlannerView";

export const metadata: Metadata = {
  title: "AI Trip Planner",
};

export default function PlannerPage() {
  return (
    <AppShell>
      <Suspense>
        <PlannerView />
      </Suspense>
    </AppShell>
  );
}

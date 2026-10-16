import AppShell from "@/components/AppShell";
import ChatDrawer from "@/components/chat/ChatDrawer";
import FriendsMap from "@/components/dashboard/FriendsMap";
import Greeting from "@/components/dashboard/Greeting";
import ItineraryCard from "@/components/dashboard/ItineraryCard";
import PlacesSection from "@/components/dashboard/PlacesSection";
import StoryStrip from "@/components/dashboard/StoryStrip";
import UpcomingTrips from "@/components/dashboard/UpcomingTrips";

export default function DashboardPage() {
  return (
    <AppShell>
      <div className="mx-auto max-w-[1240px] px-4 pt-16 pb-24 sm:px-6 lg:px-8 lg:pt-7">
        <Greeting />

        <div className="mt-7 grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
          <div className="min-w-0">
            <StoryStrip />
            <div className="mt-3">
              <UpcomingTrips />
            </div>
          </div>
          <div id="friends" className="min-h-[300px] scroll-mt-6">
            <FriendsMap />
          </div>
        </div>

        <div className="mt-8 grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
          <PlacesSection />
          <ItineraryCard />
        </div>
      </div>
      <ChatDrawer />
    </AppShell>
  );
}

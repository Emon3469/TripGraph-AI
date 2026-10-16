import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { friends, places, trips, upcomingTrips } from "@/lib/data";
import FriendsMap from "./FriendsMap";
import ItineraryCard from "./ItineraryCard";
import PlacesSection from "./PlacesSection";
import StoryStrip from "./StoryStrip";
import UpcomingTrips from "./UpcomingTrips";

const pathname = vi.hoisted(() => ({ value: "/" }));
vi.mock("next/navigation", () => ({ usePathname: () => pathname.value }));

const { default: Sidebar } = await import("../Sidebar");

function plannerQuery(link: HTMLElement) {
  const url = new URL(link.getAttribute("href")!, "http://x");
  expect(url.pathname).toBe("/planner");
  return url.searchParams.get("q");
}

describe("Sidebar", () => {
  it("lists trips that open the planner with a prompt", () => {
    render(<Sidebar />);
    for (const trip of trips) {
      const link = screen.getByRole("link", { name: new RegExp(trip.city) });
      expect(plannerQuery(link)).toContain(trip.city);
    }
    expect(screen.getByRole("link", { name: /New Trip/ })).toHaveAttribute("href", "/planner?new=1");
  });

  it("highlights the active page", () => {
    pathname.value = "/planner";
    render(<Sidebar />);
    expect(screen.getByRole("link", { name: /Itinerary/ }).className).toContain("bg-ink-100");
    expect(screen.getByRole("link", { name: /Dashboard/ }).className).not.toContain("bg-ink-100");
    pathname.value = "/";
  });

  it("calls onClose when a link is followed", async () => {
    const onClose = vi.fn();
    render(<Sidebar onClose={onClose} />);
    await userEvent.click(screen.getByRole("button", { name: "Collapse sidebar" }));
    expect(onClose).toHaveBeenCalled();
  });
});

describe("Dashboard sections", () => {
  it("renders upcoming trips with budgets and planner links", () => {
    render(<UpcomingTrips />);
    for (const trip of upcomingTrips) {
      const card = screen.getByRole("link", { name: new RegExp(trip.title) });
      expect(within(card).getByText(`$${trip.budget.toLocaleString("en-US")}`)).toBeInTheDocument();
      expect(plannerQuery(card)).toBe(trip.prompt);
    }
  });

  it("renders the story strip", () => {
    render(<StoryStrip />);
    expect(screen.getAllByRole("link")).toHaveLength(6);
  });

  it("places every friend on the world map inside its bounds", () => {
    const { container } = render(<FriendsMap />);
    expect(screen.getByAltText("World map").getAttribute("src")).toMatch(/^data:image\/svg\+xml/);
    for (const friend of friends) {
      const pin = screen.getByAltText(friend.name).closest('div[style*="left"]') as HTMLElement;
      const left = parseFloat(pin.style.left);
      const top = parseFloat(pin.style.top);
      expect(left).toBeGreaterThan(0);
      expect(left).toBeLessThan(100);
      expect(top).toBeGreaterThan(0);
      expect(top).toBeLessThan(100);
    }
    expect(container.textContent).toContain("Shelly A.");
  });

  it("toggles favourites on places", async () => {
    render(<PlacesSection />);
    expect(screen.getAllByRole("article")).toHaveLength(places.length);
    const unliked = screen.getAllByRole("button", { name: "Add to favourites" })[0];
    await userEvent.click(unliked);
    expect(screen.getAllByRole("button", { name: "Remove from favourites" })).toHaveLength(2);
  });

  it("renders the featured itinerary details", () => {
    render(<ItineraryCard />);
    expect(screen.getByText("$1,200")).toBeInTheDocument();
    expect(screen.getByText("7d, 6n")).toBeInTheDocument();
    expect(plannerQuery(screen.getByRole("link", { name: /Build a plan like this/ }))).toContain("Malacca");
  });
});

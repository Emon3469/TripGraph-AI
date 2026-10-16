import type { Metadata, Viewport } from "next";
import { Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";

const jakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  variable: "--font-jakarta",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "TripGraph AI - Plan your itinerary",
    template: "%s | TripGraph AI",
  },
  description:
    "TripGraph AI plans trips with a team of specialist agents for flights, hotels, weather and budgets, with you approving every itinerary.",
  applicationName: "TripGraph AI",
  keywords: ["travel planner", "itinerary", "AI trip planner", "multi-agent"],
};

export const viewport: Viewport = {
  themeColor: "#ff7a3d",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={jakarta.variable}>
      <body className="font-sans">{children}</body>
    </html>
  );
}

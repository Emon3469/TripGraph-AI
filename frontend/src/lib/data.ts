export const traveller = {
  name: "Cecilia Puni",
  firstName: "Cecil",
  role: "Part-time Traveller",
  avatar: "/images/avatars/cecilia.svg",
};

export type Trip = {
  id: string;
  city: string;
  flag: string;
  days: number;
  date: string;
};

export const trips: Trip[] = [
  { id: "kl", city: "Kuala Lumpur", flag: "/images/flags/my.svg", days: 5, date: "24 Dec 2026" },
  { id: "tokyo", city: "Tokyo", flag: "/images/flags/jp.svg", days: 14, date: "1 Jan 2027" },
  { id: "bangkok", city: "Bangkok", flag: "/images/flags/th.svg", days: 8, date: "4 Mar 2027" },
  { id: "hanoi", city: "Hanoi", flag: "/images/flags/vn.svg", days: 8, date: "19 Jul 2027" },
];

export type Story = {
  id: string;
  image: string;
  avatar: string;
  label: string;
  seen: boolean;
  ring: string;
};

export const stories: Story[] = [
  { id: "1", image: "/images/places/cameron-highlands.jpg", avatar: "/images/avatars/aiko.svg", label: "Cameron Highlands", seen: false, ring: "ring-brand-500" },
  { id: "2", image: "/images/places/sapa.jpg", avatar: "/images/avatars/rahim.svg", label: "Sa Pa", seen: false, ring: "ring-rose-400" },
  { id: "3", image: "/images/places/mount-fuji.jpg", avatar: "/images/avatars/edgar.svg", label: "Mount Fuji", seen: false, ring: "ring-violet-500" },
  { id: "4", image: "/images/places/batu-caves.jpg", avatar: "/images/avatars/lina.svg", label: "Batu Caves", seen: false, ring: "ring-brand-500" },
  { id: "5", image: "/images/places/hanoi.jpg", avatar: "/images/avatars/tomas.svg", label: "Hanoi", seen: true, ring: "ring-ink-200" },
  { id: "6", image: "/images/places/malacca.jpg", avatar: "/images/avatars/shelly.svg", label: "Malacca", seen: true, ring: "ring-ink-200" },
];

export type UpcomingTrip = {
  id: string;
  title: string;
  country: string;
  image: string;
  day: string;
  month: string;
  duration: string;
  budget: number;
  companions: string[];
  highlight: boolean;
  prompt: string;
};

export const upcomingTrips: UpcomingTrip[] = [
  {
    id: "kl-ipoh",
    title: "Kuala Lumpur - Ipoh",
    country: "Malaysia",
    image: "/images/places/ipoh.jpg",
    day: "12",
    month: "Dec",
    duration: "4",
    budget: 1200,
    companions: ["/images/avatars/mortis.svg", "/images/avatars/nita.svg"],
    highlight: true,
    prompt: "Plan a 4 day trip from Kuala Lumpur to Ipoh starting 12 December for 2 people with a $1,200 budget",
  },
  {
    id: "sapa",
    title: "Sapa - Ninh Binh",
    country: "Vietnam",
    image: "/images/places/sapa.jpg",
    day: "24",
    month: "Nov",
    duration: "12",
    budget: 890,
    companions: ["/images/avatars/primo.svg", "/images/avatars/aiko.svg"],
    highlight: false,
    prompt: "Plan a 12 day backpacking trip through Sapa and Ninh Binh in Vietnam starting 24 November with an $890 budget",
  },
];

export type Friend = {
  name: string;
  country: string;
  avatar: string;
  lat: number;
  lng: number;
  showLabel: boolean;
};

export const friends: Friend[] = [
  { name: "Shelly A.", country: "Japan", avatar: "/images/avatars/shelly.svg", lat: 36.2, lng: 138.25, showLabel: true },
  { name: "Edgar P.", country: "Argentina", avatar: "/images/avatars/edgar.svg", lat: -34.6, lng: -63.6, showLabel: true },
  { name: "Tomas R.", country: "Canada", avatar: "/images/avatars/tomas.svg", lat: 56.1, lng: -106.3, showLabel: false },
  { name: "Lina K.", country: "Australia", avatar: "/images/avatars/lina.svg", lat: -25.3, lng: 133.8, showLabel: false },
];

export type Place = {
  id: string;
  title: string;
  description: string;
  image: string;
  rating: number;
  reviews: number;
  guide: { name: string; avatar: string };
  tags: { label: string; tone: string }[];
  liked: boolean;
};

export const places: Place[] = [
  {
    id: "central-market",
    title: "Central Market - Kuala Lumpur",
    description:
      "A vibrant cultural landmark offering local crafts, souvenirs, and Malaysian art under one Art Deco roof.",
    image: "/images/places/central-market.jpg",
    rating: 4.5,
    reviews: 47,
    guide: { name: "Nita", avatar: "/images/avatars/nita.svg" },
    tags: [
      { label: "Shopping", tone: "bg-sky-50 text-sky-600" },
      { label: "Souvenirs", tone: "bg-emerald-50 text-emerald-600" },
      { label: "Culture", tone: "bg-amber-50 text-amber-600" },
    ],
    liked: true,
  },
  {
    id: "merdeka-square",
    title: "Merdeka Square - Kuala Lumpur",
    description:
      "An iconic historic site surrounded by colonial buildings and the famous flagpole where independence was declared.",
    image: "/images/places/merdeka-square.jpg",
    rating: 4.6,
    reviews: 53,
    guide: { name: "El Primo", avatar: "/images/avatars/primo.svg" },
    tags: [
      { label: "History", tone: "bg-violet-50 text-violet-600" },
      { label: "Architecture", tone: "bg-rose-50 text-rose-500" },
      { label: "Photography", tone: "bg-teal-50 text-teal-600" },
    ],
    liked: false,
  },
  {
    id: "batu-caves",
    title: "Batu Caves - Selangor",
    description:
      "Limestone caves and Hindu temples reached by 272 rainbow-coloured steps, just north of the city.",
    image: "/images/places/batu-caves.jpg",
    rating: 4.7,
    reviews: 88,
    guide: { name: "Rahim", avatar: "/images/avatars/rahim.svg" },
    tags: [
      { label: "Nature", tone: "bg-emerald-50 text-emerald-600" },
      { label: "Temple", tone: "bg-amber-50 text-amber-600" },
      { label: "Hiking", tone: "bg-sky-50 text-sky-600" },
    ],
    liked: false,
  },
];

export const featuredItinerary = {
  title: "One Week Itinerary - Malacca Heritage Trail",
  traveller: { name: "Mortis A.", avatar: "/images/avatars/mortis.svg" },
  image: "/images/places/malacca-church.jpg",
  budget: 1200,
  persons: 2,
  duration: "7d, 6n",
  prompt: "Plan a one week heritage trip to Malacca for 2 people with a $1,200 budget",
};

export const suggestions = [
  "Plan a 5-day trip to Kuala Lumpur for 2 under $1,200",
  "What's the weather like in Tokyo this week?",
  "Best areas to stay in Bangkok for food lovers",
  "3 days in Hanoi on a backpacker budget",
];

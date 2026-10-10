import { formatDay, type Lang } from "@/lib/landingCopy";

export function pct(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

const NAIROBI = "Africa/Nairobi";

// Constructed once at module load. These were built per call and reached once
// per leg per slip, so a 90-day desk was making thousands of formatter objects
// on every 20s poll tick.
const CLOCK_FORMAT = new Intl.DateTimeFormat("en-GB", {
  timeZone: NAIROBI,
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

const DAY_FORMAT = new Intl.DateTimeFormat("en-CA", {
  timeZone: NAIROBI,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

export function kickoffLocal(iso: string, lang: Lang = "en"): string {
  const clock = CLOCK_FORMAT.format(new Date(iso));
  return `${formatDay(nairobiDay(iso), lang)}, ${clock}`;
}

export function nairobiDay(iso: string): string {
  return DAY_FORMAT.format(new Date(iso));
}

export function slipDates(kickoffs: string[]): string[] {
  return [...new Set(kickoffs.map(nairobiDay))].sort();
}

export function slipCreatedLocal(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function edgeLabel(edge: number | null): string {
  if (edge === null) return "—";
  const pts = (edge * 100).toFixed(1);
  return edge >= 0 ? `+${pts} pts` : `${pts} pts`;
}

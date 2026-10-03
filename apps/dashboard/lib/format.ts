import { formatDay, type Lang } from "@/lib/landingCopy";

export function pct(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

const NAIROBI = "Africa/Nairobi";

export function kickoffLocal(iso: string, lang: Lang = "en"): string {
  const clock = new Intl.DateTimeFormat("en-GB", {
    timeZone: NAIROBI,
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(new Date(iso));
  return `${formatDay(nairobiDay(iso), lang)}, ${clock}`;
}

export function nairobiDay(iso: string): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Africa/Nairobi",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(iso));
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

export function pct(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function kickoffLocal(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
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

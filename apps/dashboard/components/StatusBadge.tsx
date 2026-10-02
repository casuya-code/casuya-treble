import { ReactNode } from "react";

export type StatusKind = "DAY" | "NIGHT" | "PENDING" | "LIVE" | "WON" | "LOST" | "PLACED" | "ALL";

const labels: Record<StatusKind, string> = {
  ALL: "All",
  DAY: "Day",
  NIGHT: "Night",
  PENDING: "Pending",
  LIVE: "Live",
  WON: "Won",
  LOST: "Lost",
  PLACED: "Placed",
};

function Icon({ kind }: { kind: StatusKind }) {
  const common = { width: 14, height: 14, "aria-hidden": true as const };

  switch (kind) {
    case "DAY":
      return (
        <svg {...common} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
        </svg>
      );
    case "NIGHT":
      return (
        <svg {...common} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M21 14.5A8.5 8.5 0 1 1 9.5 3 7 7 0 0 0 21 14.5z" />
        </svg>
      );
    case "PENDING":
      return (
        <svg {...common} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="9" />
          <path d="M12 7v5l3 2" />
        </svg>
      );
    case "LIVE":
      return (
        <svg {...common} viewBox="0 0 24 24" fill="currentColor">
          <circle cx="12" cy="12" r="4" />
        </svg>
      );
    case "WON":
      return (
        <svg {...common} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <path d="M5 12l5 5L20 7" />
        </svg>
      );
    case "LOST":
      return (
        <svg {...common} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <path d="M6 6l12 12M18 6 6 18" />
        </svg>
      );
    case "PLACED":
      return (
        <svg {...common} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M9 11l3 3L22 4" />
          <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
        </svg>
      );
    case "ALL":
    default:
      return (
        <svg {...common} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M4 6h16M4 12h16M4 18h10" />
        </svg>
      );
  }
}

type BadgeProps = {
  kind: StatusKind;
  label?: string;
  className?: string;
};

export function StatusBadge({ kind, label, className = "" }: BadgeProps) {
  const text = label ?? labels[kind];
  return (
    <span className={`badge badge-icon ${kind} ${className}`.trim()}>
      <Icon kind={kind} />
      <span>{text}</span>
    </span>
  );
}

type FilterChipProps = {
  kind: StatusKind;
  active: boolean;
  onClick: () => void;
  children?: ReactNode;
};

export function FilterChip({ kind, active, onClick, children }: FilterChipProps) {
  return (
    <button type="button" className={`chip chip-icon ${kind} ${active ? "active" : ""}`} onClick={onClick}>
      <Icon kind={kind} />
      <span>{children ?? labels[kind]}</span>
    </button>
  );
}

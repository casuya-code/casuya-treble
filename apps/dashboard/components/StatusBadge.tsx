"use client";

import { ReactNode } from "react";
import { useLandingLang } from "@/components/LandingLang";

export type StatusKind =
  | "DAY"
  | "NIGHT"
  | "T00_06"
  | "T06_12"
  | "T12_18"
  | "T18_24"
  | "ALL_DAY"
  | "PENDING"
  | "LIVE"
  | "WON"
  | "LOST"
  | "PLACED"
  | "ALL";

function Glyph({ children }: { children: ReactNode }) {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      {children}
    </svg>
  );
}

function Icon({ kind }: { kind: StatusKind }) {
  switch (kind) {
    case "DAY":
    case "ALL_DAY":
      return (
        <Glyph>
          <circle cx="12" cy="12" r="4" />
          <path d="M12 3v1.5M12 19.5V21M4.9 4.9l1.1 1.1M18 18l1.1 1.1M3 12h1.5M19.5 12H21M4.9 19.1l1.1-1.1M18 6l1.1-1.1" />
        </Glyph>
      );
    case "NIGHT":
      return (
        <Glyph>
          <path d="M20 14.5A8.5 8.5 0 0 1 9.5 4 7 7 0 1 0 20 14.5z" />
        </Glyph>
      );
    case "T00_06":
    case "T06_12":
    case "T12_18":
    case "T18_24":
    case "PENDING":
      return (
        <Glyph>
          <circle cx="12" cy="12" r="8" />
          <path d="M12 8v4.5l2.5 1.5" />
        </Glyph>
      );
    case "LIVE":
      return (
        <Glyph>
          <circle cx="12" cy="12" r="8" />
          <circle cx="12" cy="12" r="3" fill="currentColor" stroke="none" />
        </Glyph>
      );
    case "WON":
      return (
        <Glyph>
          <circle cx="12" cy="12" r="8" />
          <path d="M8.2 12.2l2.4 2.4 5.2-5.4" />
        </Glyph>
      );
    case "LOST":
      return (
        <Glyph>
          <circle cx="12" cy="12" r="8" />
          <path d="M9 9l6 6M15 9l-6 6" />
        </Glyph>
      );
    case "PLACED":
      return (
        <Glyph>
          <path d="M8 4.5h8a1 1 0 0 1 1 1V20l-5-2.4L7 20V5.5a1 1 0 0 1 1-1z" />
          <path d="M9.5 11.2l1.8 1.8 3.4-3.6" />
        </Glyph>
      );
    case "ALL":
    default:
      return (
        <Glyph>
          <path d="M5 7h14M5 12h14M5 17h9" />
        </Glyph>
      );
  }
}

export function DateBadge({ label }: { label: string }) {
  return (
    <span className="badge badge-icon date-badge">
      <Glyph>
        <rect x="4" y="5" width="16" height="15" rx="2" />
        <path d="M4 10h16M8 3.5V7M16 3.5V7" />
      </Glyph>
      <span>{label}</span>
    </span>
  );
}

type BadgeProps = {
  kind: StatusKind;
  label?: string;
  className?: string;
};

export function StatusBadge({ kind, label, className = "" }: BadgeProps) {
  const { t } = useLandingLang();
  const labels: Record<StatusKind, string> = {
    ALL: t.all,
    DAY: t.day,
    NIGHT: t.night,
    T00_06: t.t0006,
    T06_12: t.t0612,
    T12_18: t.t1218,
    T18_24: t.t1824,
    ALL_DAY: t.allDay,
    PENDING: t.pending,
    LIVE: t.live,
    WON: t.won,
    LOST: t.lost,
    PLACED: t.placed,
  };
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
  const { t } = useLandingLang();
  const labels: Record<StatusKind, string> = {
    ALL: t.all,
    DAY: t.day,
    NIGHT: t.night,
    T00_06: t.t0006,
    T06_12: t.t0612,
    T12_18: t.t1218,
    T18_24: t.t1824,
    ALL_DAY: t.allDay,
    PENDING: t.pending,
    LIVE: t.live,
    WON: t.won,
    LOST: t.lost,
    PLACED: t.placed,
  };
  return (
    <button type="button" className={`chip chip-icon ${kind} ${active ? "active" : ""}`} onClick={onClick}>
      <Icon kind={kind} />
      <span>{children ?? labels[kind]}</span>
    </button>
  );
}

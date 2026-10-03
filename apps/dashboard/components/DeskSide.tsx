"use client";

import Link from "next/link";
import { ReactNode } from "react";
import { LangSwitch, useLandingLang } from "@/components/LandingLang";
import { StatusKind } from "@/components/StatusBadge";
import { formatDay, Lang } from "@/lib/landingCopy";

type Filter = StatusKind;

const FILTERS: Filter[] = ["ALL", "PENDING", "WON", "LOST", "PLACED"];

type Counts = {
  total: number;
  pending: number;
  won: number;
  lost: number;
  placed: number;
};

type Props = {
  email: string | null;
  apiOk: boolean | null;
  isAdmin: boolean;
  loading: boolean;
  lang: Lang;
  stats: Counts;
  filter: Filter;
  dateFilter: string | null;
  matchDates: string[];
  showAlternatives: boolean;
  showTools: boolean;
  onFilter: (filter: Filter) => void;
  onDate: (day: string | null) => void;
  onGenerate: () => void;
  onToggleAlternatives: () => void;
  onRefresh: () => void;
  onToggleTools: () => void;
  onLogout: () => void;
  tools?: ReactNode;
};

export function DeskSide({
  email,
  apiOk,
  isAdmin,
  loading,
  lang,
  stats,
  filter,
  dateFilter,
  matchDates,
  showAlternatives,
  showTools,
  onFilter,
  onDate,
  onGenerate,
  onToggleAlternatives,
  onRefresh,
  onToggleTools,
  onLogout,
  tools,
}: Props) {
  const { t } = useLandingLang();
  const labels: Record<Filter, string> = {
    ALL: t.all,
    PENDING: t.pending,
    WON: t.won,
    LOST: t.lost,
    PLACED: t.placed,
    DAY: t.day,
    NIGHT: t.night,
    T00_06: t.t0006,
    T06_12: t.t0612,
    T12_18: t.t1218,
    T18_24: t.t1824,
    ALL_DAY: t.allDay,
    LIVE: t.live,
  };
  const counts: Record<Filter, number> = {
    ALL: stats.total,
    PENDING: stats.pending,
    WON: stats.won,
    LOST: stats.lost,
    PLACED: stats.placed,
    DAY: 0,
    NIGHT: 0,
    T00_06: 0,
    T06_12: 0,
    T12_18: 0,
    T18_24: 0,
    ALL_DAY: 0,
    LIVE: 0,
  };

  return (
    <aside className="desk-side" aria-label={t.menu}>
      <Link href="/" className="brand">
        <span className="brand-mark">C</span>
        <span className="brand-text">
          Casuya <strong className="brand-long">Treble</strong>
        </span>
      </Link>

      <LangSwitch />

      <div className="desk-account">
        {email ? <span className="user-email">{email}</span> : null}
        <div className="desk-account-row">
          <button type="button" className="desk-text" onClick={onLogout}>
            {t.logOut}
          </button>
          <span className={`status-chip ${apiOk === true ? "ok" : apiOk === false ? "bad" : ""}`}>
            {apiOk === true ? t.connected : apiOk === false ? t.offline : "…"}
          </span>
        </div>
      </div>

      <button type="button" className="btn primary desk-generate" disabled={loading} onClick={onGenerate}>
        {showAlternatives ? t.generateTop : t.generateBest}
      </button>

      <nav className="desk-nav" aria-label={t.trebleActions}>
        {FILTERS.map((item) => (
          <button
            key={item}
            type="button"
            className={filter === item ? "active" : ""}
            aria-current={filter === item ? "true" : undefined}
            onClick={() => onFilter(item)}
          >
            <span>{labels[item]}</span>
            <b>{counts[item]}</b>
          </button>
        ))}
      </nav>

      {matchDates.length > 0 ? (
        <nav className="desk-nav" aria-label={t.matchDate}>
          <p className="desk-label">{t.matchDate}</p>
          <button type="button" className={dateFilter === null ? "active" : ""} onClick={() => onDate(null)}>
            <span>{t.allDates}</span>
          </button>
          {matchDates.map((day) => (
            <button key={day} type="button" className={dateFilter === day ? "active" : ""} onClick={() => onDate(day)}>
              <span>{formatDay(day, lang)}</span>
            </button>
          ))}
        </nav>
      ) : null}

      <div className="desk-quiet">
        <button type="button" className="desk-text" disabled={loading} onClick={onToggleAlternatives}>
          {showAlternatives ? t.oneOnly : t.includeAlt}
        </button>
        <button type="button" className="desk-text" disabled={loading} onClick={onRefresh}>
          {t.refresh}
        </button>
        {isAdmin ? (
          <Link href="/admin" className="desk-text">
            {t.admin}
          </Link>
        ) : null}
        {isAdmin ? (
          <button type="button" className="desk-text" disabled={loading} onClick={onToggleTools}>
            {showTools ? t.hide : t.more}
          </button>
        ) : null}
      </div>

      {isAdmin && showTools ? tools : null}
    </aside>
  );
}

"use client";

import Link from "next/link";
import { ReactNode } from "react";
import { LangSwitch, useLandingLang } from "@/components/LandingLang";
import { StatusKind } from "@/components/StatusBadge";
import { formatDay, Lang } from "@/lib/landingCopy";

type Filter = StatusKind;

/** Waiting, then placed, then the result. All is the full list. */
const FILTERS: Filter[] = ["PENDING", "PLACED", "WON", "LOST", "ALL"];

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
  cornerMarket: boolean;
  showTools: boolean;
  onFilter: (filter: Filter) => void;
  onDate: (day: string | null) => void;
  onGenerate: () => void;
  onAlternatives: (value: boolean) => void;
  onCornerMarket: (value: boolean) => void;
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
  cornerMarket,
  showTools,
  onFilter,
  onDate,
  onGenerate,
  onAlternatives,
  onCornerMarket,
  onRefresh,
  onToggleTools,
  onLogout,
  tools,
}: Props) {
  const { t } = useLandingLang();
  const labels: Partial<Record<Filter, string>> = {
    ALL: t.all,
    PENDING: t.pending,
    WON: t.won,
    LOST: t.lost,
    PLACED: t.placed,
  };
  const counts: Partial<Record<Filter, number>> = {
    ALL: stats.total,
    PENDING: stats.pending,
    WON: stats.won,
    LOST: stats.lost,
    PLACED: stats.placed,
  };

  return (
    <aside className="desk-side" aria-label={t.menu}>
      <Link href="/" className="brand">
        <span className="brand-mark">C</span>
        <span className="brand-text">
          Casuya <strong className="brand-long">Treble</strong>
        </span>
      </Link>

      <section className="desk-module" aria-labelledby="desk-step-make">
        <p className="desk-label" id="desk-step-make">
          {t.stepMake}
        </p>
        <div className="desk-choice" role="group" aria-label={t.stepMake}>
          <button type="button" className={cornerMarket ? "" : "active"} onClick={() => onCornerMarket(false)}>
            {t.choiceGoals}
          </button>
          <button type="button" className={cornerMarket ? "active" : ""} onClick={() => onCornerMarket(true)}>
            {t.choiceCorners}
          </button>
        </div>
        <div className="desk-choice" role="group" aria-label={t.stepMake}>
          <button type="button" className={showAlternatives ? "" : "active"} onClick={() => onAlternatives(false)}>
            {t.choiceOne}
          </button>
          <button type="button" className={showAlternatives ? "active" : ""} onClick={() => onAlternatives(true)}>
            {t.choiceThree}
          </button>
        </div>
        <button type="button" className="btn primary desk-generate" disabled={loading} onClick={onGenerate}>
          {showAlternatives ? t.generateTop : t.generateBest}
        </button>
      </section>

      <section className="desk-module" aria-labelledby="desk-step-slips">
        <p className="desk-label" id="desk-step-slips">
          {t.stepSlips}
        </p>
        <nav className="desk-nav">
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
        <button type="button" className="desk-text" disabled={loading} onClick={onRefresh}>
          {t.refresh}
        </button>
      </section>

      <section className="desk-module desk-account" aria-labelledby="desk-step-account">
        <p className="desk-label" id="desk-step-account">
          {t.stepAccount}
        </p>
        <LangSwitch />
        {email ? <span className="user-email">{email}</span> : null}
        <div className="desk-account-row">
          <span className={`status-chip ${apiOk === true ? "ok" : apiOk === false ? "bad" : ""}`}>
            {apiOk === true ? t.connected : apiOk === false ? t.offline : "…"}
          </span>
          <button type="button" className="desk-text" onClick={onLogout}>
            {t.logOut}
          </button>
        </div>
      </section>

      {isAdmin ? (
        <div className="desk-quiet">
          <Link href="/admin" className="desk-text">
            {t.admin}
          </Link>
          <button type="button" className="desk-text" disabled={loading} onClick={onToggleTools}>
            {showTools ? t.hide : t.more}
          </button>
          {showTools ? tools : null}
        </div>
      ) : null}
    </aside>
  );
}

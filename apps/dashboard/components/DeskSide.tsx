"use client";

import Link from "next/link";
import { ReactNode } from "react";
import { LangSwitch, useLandingLang } from "@/components/LandingLang";
import { StatusKind } from "@/components/StatusBadge";
import { fill, formatDay, Lang } from "@/lib/landingCopy";

type Filter = StatusKind;
type Market = "goals" | "corners";

/** Waiting, then placed, then the result. All is the full list. */
const FILTERS: Filter[] = ["PENDING", "PLACED", "WON", "LOST", "ALL"];

type Counts = {
  total: number;
  pending: number;
  won: number;
  lost: number;
  placed: number;
};

/** One settled corner line: settled/won counts plus the model's average claim. */
export type CornerStat = {
  line: number;
  settled: number;
  won: number;
  avgP: number;
  avgOdds: number;
};

type Props = {
  isAdmin: boolean;
  loading: boolean;
  lang: Lang;
  stats: Counts;
  filter: Filter;
  dateFilter: string | null;
  matchDates: string[];
  showAlternatives: boolean;
  wantGoals: boolean;
  wantCorners: boolean;
  showTools: boolean;
  /** True while the sidebar is asking before it deletes pending slips. */
  confirmReplace: boolean;
  /** Pending, unplaced slips this run would delete. */
  deletablePending: number;
  /** Settled corner legs by line for the calibration table. */
  cornerStats: CornerStat[];
  onFilter: (filter: Filter) => void;
  onDate: (day: string | null) => void;
  onGenerate: () => void;
  onCancelGenerate: () => void;
  onAlternatives: (value: boolean) => void;
  onToggleMarket: (market: Market) => void;
  onRefresh: () => void;
  onToggleTools: () => void;
  onLogout: () => void;
  tools?: ReactNode;
};

export function DeskSide({
  isAdmin,
  loading,
  lang,
  stats,
  filter,
  dateFilter,
  matchDates,
  showAlternatives,
  wantGoals,
  wantCorners,
  showTools,
  confirmReplace,
  deletablePending,
  cornerStats,
  onFilter,
  onDate,
  onGenerate,
  onCancelGenerate,
  onAlternatives,
  onToggleMarket,
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
        <div className="desk-choice" role="group" aria-label={t.markets}>
          <button
            type="button"
            className={wantGoals ? "active" : ""}
            aria-pressed={wantGoals}
            disabled={wantGoals && !wantCorners}
            onClick={() => onToggleMarket("goals")}
          >
            {t.choiceGoals}
          </button>
          <button
            type="button"
            className={wantCorners ? "active" : ""}
            aria-pressed={wantCorners}
            disabled={wantCorners && !wantGoals}
            onClick={() => onToggleMarket("corners")}
          >
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
        {confirmReplace && deletablePending > 0 ? (
          <div className="desk-confirm" role="alertdialog" aria-label={t.replacePendingTitle}>
            <p className="desk-confirm-title">{t.replacePendingTitle}</p>
            <p className="desk-confirm-body">{fill(t.replacePendingBody, { n: deletablePending })}</p>
            <div className="desk-confirm-actions">
              <button type="button" className="btn primary" disabled={loading} onClick={onGenerate}>
                {t.replacePendingConfirm}
              </button>
              <button type="button" className="desk-text" disabled={loading} onClick={onCancelGenerate}>
                {t.replacePendingCancel}
              </button>
            </div>
          </div>
        ) : (
          <button type="button" className="btn primary desk-generate" disabled={loading} onClick={onGenerate}>
            {showAlternatives ? t.generateTop : t.generateBest}
          </button>
        )}
        <p className="desk-range">{t.oddsRangeNote}</p>
      </section>

      <div className="desk-scroll">
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
            <p className="desk-label desk-label-in">{t.matchDate}</p>
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
        {cornerStats.length > 0 ? (
          <div className="desk-cal" aria-labelledby="desk-cal-label">
            <p className="desk-label" id="desk-cal-label">
              {t.cornerCalibration}
            </p>
            <table className="desk-cal-table">
              <thead>
                <tr>
                  <th scope="col">{t.cornerCalLine}</th>
                  <th scope="col">{t.cornerCalWon}</th>
                  <th scope="col">{t.cornerCalSettled}</th>
                  <th scope="col">{t.cornerCalHit}</th>
                  <th scope="col">{t.cornerCalModel}</th>
                  <th scope="col">{t.cornerCalOdds}</th>
                </tr>
              </thead>
              <tbody>
                {cornerStats.map((row) => {
                  const hit = row.settled ? (row.won / row.settled) * 100 : null;
                  const badCalibration = hit != null && row.avgP > 0 && hit < row.avgP * 100 - 15;
                  return (
                    <tr key={row.line} className={badCalibration ? "off" : undefined}>
                      <td>O{row.line}+</td>
                      <td>{row.won}</td>
                      <td>{row.settled}</td>
                      <td>{hit == null ? "—" : `${Math.round(hit)}%`}</td>
                      <td>{row.avgP > 0 ? `${Math.round(row.avgP * 100)}%` : "—"}</td>
                      <td>{row.avgOdds > 0 ? row.avgOdds.toFixed(2) : "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p className="desk-cal-note">{t.cornerCalNote}</p>
          </div>
        ) : null}
        <button type="button" className="desk-text" disabled={loading} onClick={onRefresh}>
          {t.refresh}
        </button>
        <div className="desk-quiet">
          <Link href="/hoops" className="desk-text">
            {t.hoops}
          </Link>
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
      </div>

      <section className="desk-module desk-account" aria-labelledby="desk-step-account">
        <p className="desk-label" id="desk-step-account">
          {t.stepAccount}
        </p>
        <LangSwitch />
        <button type="button" className="desk-text" onClick={onLogout}>
          {t.logOut}
        </button>
      </section>
    </aside>
  );
}

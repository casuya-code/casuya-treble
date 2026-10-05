"use client";

import { useState } from "react";
import { DateBadge, StatusBadge, StatusKind } from "@/components/StatusBadge";
import { useLandingLang } from "@/components/LandingLang";
import { Slip, SlipLeg } from "@/lib/api";
import { edgeLabel, kickoffLocal, pct, slipCreatedLocal, slipDates } from "@/lib/format";
import { formatDay } from "@/lib/landingCopy";

function cornerLine(market: string): number | null {
  const match = market.match(/(\d+(?:\.\d+)?)/);
  return match ? Number(match[1]) : null;
}

function legKind(leg: SlipLeg): StatusKind {
  if (leg.market.toLowerCase().includes("corner")) {
    const line = cornerLine(leg.market);
    if (leg.fh_corners == null || line == null) return "PENDING";
    if (leg.fh_corners > line) return "WON";
    if (leg.fh_half_complete || leg.match_finished) return "LOST";
    return "PENDING";
  }
  if (leg.home_goals == null || leg.away_goals == null) return "PENDING";
  if (leg.home_goals + leg.away_goals >= 2) return "WON";
  if (leg.match_finished) return "LOST";
  return "PENDING";
}

function legScore(leg: SlipLeg): string {
  if (leg.market.toLowerCase().includes("corner")) {
    return leg.fh_corners == null ? "—" : String(leg.fh_corners);
  }
  if (leg.home_goals != null && leg.away_goals != null) return `${leg.home_goals}–${leg.away_goals}`;
  return "—";
}

function trebleKind(slip: Slip): StatusKind {
  const kinds = slip.legs.map(legKind);
  if (kinds.some((kind) => kind === "LOST")) return "LOST";
  if (kinds.length > 0 && kinds.every((kind) => kind === "WON")) return "WON";
  if (slip.status === "LIVE") return "LIVE";
  return slip.status;
}

type Props = {
  slip: Slip;
  featured?: boolean;
  copied: boolean;
  loading: boolean;
  onCopy: () => void;
  onTogglePlaced: () => void;
};

export function SlipCard({ slip, featured, copied, loading, onCopy, onTogglePlaced }: Props) {
  const { lang, t } = useLandingLang();
  const [copiedName, setCopiedName] = useState<string | null>(null);

  async function copyMatchName(fixtureId: string, name: string) {
    try {
      await navigator.clipboard.writeText(name);
      setCopiedName(fixtureId);
      window.setTimeout(() => setCopiedName((current) => (current === fixtureId ? null : current)), 3500);
    } catch {
      setCopiedName(`fail:${fixtureId}`);
      window.setTimeout(() => setCopiedName((current) => (current === `fail:${fixtureId}` ? null : current)), 3500);
    }
  }
  const modelPct = slip.model_probability * 100;
  const impliedPct = slip.implied_probability * 100;
  const matchDates = slipDates(slip.legs.map((leg) => leg.kickoff_at));
  const dateLabel = (matchDates.length > 0 ? matchDates : slipDates([slip.timestamp]))
    .map((day) => formatDay(day, lang))
    .join(" · ");

  return (
    <article
      className={`slip-card frame ${featured ? "featured" : ""} ${slip.placed_on_betpawa ? "placed" : ""}`}
      aria-label={`Treble ${slip.closing_odds.toFixed(2)} odds`}
    >
      {slip.forced ? (
        <span className="ribbon forced">{t.forced}</span>
      ) : featured ? (
        <span className="ribbon">{t.bestPick}</span>
      ) : null}

      <header className="slip-head">
        <div>
          <p className="slip-odds">{slip.closing_odds.toFixed(2)}</p>
          <p className="slip-odds-label">
            {t.combinedLabel} · {pct(slip.model_probability)} {t.modelWord}
          </p>
          <p className="slip-created">{t.generated} {slipCreatedLocal(slip.timestamp)}</p>
          {slip.forced ? <p className="forced-note">{t.forcedNote}</p> : null}
        </div>
        <div className="badges">
          <StatusBadge kind={trebleKind(slip)} className="result-badge" />
          {slip.forced ? <span className="badge forced">{t.forced}</span> : null}
          <DateBadge label={dateLabel} />
          {slip.placed_on_betpawa ? <StatusBadge kind="PLACED" className="placed-badge" /> : null}
        </div>
      </header>

      <div className="prob-bar-wrap" title="Green bar = model; gold tick = book implied">
        <div className="prob-bar">
          <div className="prob-model" style={{ width: `${Math.min(modelPct, 100)}%` }} />
          <div className="prob-implied" style={{ left: `${Math.min(impliedPct, 100)}%` }} />
        </div>
        <p className="prob-meta">
          Book {pct(slip.implied_probability)} · Edge {edgeLabel(slip.edge)}
        </p>
      </div>

      <ul className="leg-list">
        {slip.legs.map((leg, index) => (
          <li key={leg.fixture_id} className="leg-row">
            <span className="leg-num">{index + 1}</span>
            <div className="leg-main">
              <strong>
                {leg.home_team} v {leg.away_team}
              </strong>
              <span className="leg-sub">
                {leg.is_demo ? (
                  <span className="leg-demo-tag">{t.practiceTag}</span>
                ) : null}
                {kickoffLocal(leg.kickoff_at, lang)} · {leg.market} @ {leg.leg_odds.toFixed(2)}
                {leg.league && !leg.is_demo ? ` · ${leg.league}` : null}
              </span>
              <button
                type="button"
                className="btn ghost leg-copy"
                onClick={() => void copyMatchName(leg.fixture_id, `${leg.home_team} v ${leg.away_team}`)}
              >
                {copiedName === `fail:${leg.fixture_id}`
                  ? t.copyFailed
                  : copiedName === leg.fixture_id
                    ? t.copiedName
                    : t.copyName}
              </button>
            </div>
            <div className="leg-side">
              <span className="score-box" aria-label={t.score}>
                {legScore(leg)}
              </span>
              <StatusBadge kind={legKind(leg)} className="result-badge" />
            </div>
          </li>
        ))}
      </ul>

      <div className="slip-actions">
        <pre className="copy-preview">{slip.betpawa_copy_text}</pre>
        <p className="copy-help">{t.copyHelp}</p>
        <button type="button" className="btn primary" onClick={onCopy}>
          {copied ? t.copied : t.copySlip}
        </button>
        <p className={`place-state ${slip.placed_on_betpawa ? "is-placed" : ""}`}>
          {slip.placed_on_betpawa ? t.placedStatus : t.openStatus}
        </p>
        <button type="button" className="btn ghost" disabled={loading} onClick={onTogglePlaced}>
          {slip.placed_on_betpawa ? t.undoPlaced : t.markPlaced}
        </button>
      </div>
    </article>
  );
}

"use client";

import { StatusBadge } from "@/components/StatusBadge";
import { Slip } from "@/lib/api";
import { edgeLabel, kickoffLocal, pct, slipCreatedLocal } from "@/lib/format";

type Props = {
  slip: Slip;
  featured?: boolean;
  copied: boolean;
  loading: boolean;
  onCopy: () => void;
  onTogglePlaced: () => void;
};

export function SlipCard({ slip, featured, copied, loading, onCopy, onTogglePlaced }: Props) {
  const modelPct = slip.model_probability * 100;
  const impliedPct = slip.implied_probability * 100;

  return (
    <article
      className={`slip-card frame ${featured ? "featured" : ""} ${slip.placed_on_betpawa ? "placed" : ""}`}
      aria-label={`Treble ${slip.closing_odds.toFixed(2)} odds`}
    >
      {featured ? <span className="ribbon">Best pick</span> : null}

      <header className="slip-head">
        <div>
          <p className="slip-odds">{slip.closing_odds.toFixed(2)}</p>
          <p className="slip-odds-label">
            Combined · {pct(slip.model_probability)} model
          </p>
          <p className="slip-created">Generated {slipCreatedLocal(slip.timestamp)}</p>
        </div>
        <div className="badges">
          <StatusBadge kind={slip.time_category} />
          <StatusBadge kind={slip.status} />
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
                  <span className="leg-demo-tag">Practice — not a real match</span>
                ) : null}
                {kickoffLocal(leg.kickoff_at)} · Over 1.5 @ {leg.leg_odds.toFixed(2)}
                {leg.league && !leg.is_demo ? ` · ${leg.league}` : null}
              </span>
            </div>
          </li>
        ))}
      </ul>

      <div className="slip-actions">
        <button type="button" className="btn primary" onClick={onCopy}>
          {copied ? "Copied" : "Copy for BetPawa"}
        </button>
        <button type="button" className="btn ghost" disabled={loading} onClick={onTogglePlaced}>
          {slip.placed_on_betpawa ? "Not placed" : "Mark placed"}
        </button>
      </div>
    </article>
  );
}

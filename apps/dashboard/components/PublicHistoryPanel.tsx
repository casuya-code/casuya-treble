"use client";

import { useEffect, useState } from "react";
import { api, PublicHistory } from "@/lib/api";

function dayLabel(iso: string): string {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function profitLabel(value: number): string {
  const text = Math.abs(value).toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (value > 0) return `+${text}`;
  if (value < 0) return `−${text}`;
  return "0";
}

function resultWord(result: string): string {
  if (result === "won") return "Won";
  if (result === "lost") return "Lost";
  return "Waiting";
}

export function PublicHistoryPanel() {
  const [history, setHistory] = useState<PublicHistory | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      if (document.visibilityState === "hidden") return;
      try {
        const rows = await api.publicHistory();
        if (!cancelled) {
          setHistory(rows);
          setError(null);
        }
      } catch {
        if (!cancelled) setError("Results are unavailable right now.");
      }
    }

    void load();
    const timer = window.setInterval(() => void load(), 20000);
    document.addEventListener("visibilitychange", load);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", load);
    };
  }, []);

  return (
    <section className="index-history" aria-label="Placed results">
      <h2 className="index-section-title">Placed results</h2>
      <p className="index-history-note index-history-lead">
        Open to everyone. Stake is 2,000 on each match and 2,000 on each treble. The same three matches
        appear once, even when more than one account placed them. The page refreshes on its own. A leg is won
        once two goals are in. It is lost only when the match finishes with fewer than two. Waiting matches stay
        out of the profit. A treble is lost as soon as one leg loses.
      </p>
      {error ? <p className="banner error">{error}</p> : null}
      {!history && !error ? <p className="index-history-note">Loading results…</p> : null}
      {history && history.trebles_placed === 0 ? (
        <p className="index-history-empty">No placed trebles yet. Mark a slip as placed and the result shows here.</p>
      ) : null}
      {history && history.trebles_placed > 0 ? (
        <>
          <div className="index-history-totals">
            <div>
              <strong>{history.matches_won}</strong>
              <span>Matches won</span>
            </div>
            <div>
              <strong>{history.matches_lost}</strong>
              <span>Matches lost</span>
            </div>
            <div>
              <strong>{history.trebles_placed}</strong>
              <span>Trebles placed</span>
            </div>
            <div>
              <strong className={history.single_profit < 0 ? "down" : "up"}>{profitLabel(history.single_profit)}</strong>
              <span>Single profit</span>
            </div>
            <div>
              <strong className={history.treble_profit < 0 ? "down" : "up"}>{profitLabel(history.treble_profit)}</strong>
              <span>Treble profit</span>
            </div>
          </div>
          <ul className="index-history-days">
            {history.days.map((day) => (
              <li key={day.date}>
                <strong>{dayLabel(day.date)}</strong>
                <span>
                  Matches won {day.matches_won} · lost {day.matches_lost}
                </span>
                <span>Single profit {profitLabel(day.single_profit)}</span>
                <span>
                  Trebles placed {day.trebles_placed} · won {day.trebles_won} · lost {day.trebles_lost}
                  {day.trebles_pending ? ` · waiting ${day.trebles_pending}` : ""}
                </span>
                <span>Treble profit {profitLabel(day.treble_profit)}</span>
              </li>
            ))}
          </ul>
          <ul className="index-history-slips">
            {history.slips.map((slip) => (
              <li key={slip.slip_id}>
                <div className="index-history-slip-head">
                  <strong>{dayLabel(slip.date)}</strong>
                  <span className={`index-history-result ${slip.result}`}>{resultWord(slip.result)}</span>
                  <span>{slip.combined_odds.toFixed(2)}</span>
                </div>
                <ul>
                  {slip.legs.map((leg) => (
                    <li key={`${slip.slip_id}-${leg.home_team}-${leg.away_team}`}>
                      <span>
                        {leg.home_team} v {leg.away_team}
                        {leg.practice ? " · Practice" : ""}
                      </span>
                      <span>
                        {leg.home_goals != null && leg.away_goals != null
                          ? `${leg.home_goals}–${leg.away_goals}`
                          : "—"}{" "}
                        · {leg.odds.toFixed(2)} · {resultWord(leg.result)}
                      </span>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </section>
  );
}

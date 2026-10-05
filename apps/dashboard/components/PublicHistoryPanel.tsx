"use client";

import { useEffect, useState } from "react";
import { useLandingLang } from "@/components/LandingLang";
import { api, HistoryLeg, HistorySlip, PublicHistory } from "@/lib/api";
import { formatDay, formatMoney, formatStake } from "@/lib/landingCopy";

function scoreText(leg: HistoryLeg): string {
  if ((leg.market || "").toLowerCase().includes("corner")) {
    return leg.fh_corners == null ? "—" : String(leg.fh_corners);
  }
  if (leg.home_goals == null || leg.away_goals == null) return "—";
  return `${leg.home_goals}–${leg.away_goals}`;
}

function uniqueLegs(slips: HistorySlip[]): HistoryLeg[] {
  const seen = new Set<string>();
  const legs: HistoryLeg[] = [];
  for (const slip of slips) {
    for (const leg of slip.legs) {
      const key = `${leg.home_team}|${leg.away_team}`;
      if (seen.has(key)) continue;
      seen.add(key);
      legs.push(leg);
    }
  }
  return legs;
}

function sharesALostLeg(slips: HistorySlip[]): boolean {
  const counts = new Map<string, number>();
  for (const slip of slips) {
    for (const leg of slip.legs) {
      if (leg.result !== "lost") continue;
      const key = `${leg.home_team}|${leg.away_team}`;
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
  }
  return [...counts.values()].some((count) => count > 1);
}

function MatchRow({ leg }: { leg: HistoryLeg }) {
  const { t } = useLandingLang();
  const word = leg.result === "won" ? t.Won : leg.result === "lost" ? t.Lost : t.Pending;
  const tone = leg.result === "won" ? "pos" : leg.result === "lost" ? "neg" : "";
  const name = `${leg.home_team} v ${leg.away_team}${leg.practice ? ` · ${t.practice}` : ""}`;

  return (
    <div className="row">
      <span className="m">{name}</span>
      <span className="o">{leg.odds.toFixed(2)}</span>
      <span className="sc">{scoreText(leg)}</span>
      <span className={`chip ${tone}`}>{word}</span>
    </div>
  );
}

export function PublicHistoryPanel() {
  const { lang, t } = useLandingLang();
  const [history, setHistory] = useState<PublicHistory | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      if (document.visibilityState === "hidden") return;
      try {
        const rows = await api.publicHistory();
        if (!cancelled) {
          setHistory(rows);
          setError(null);
          setUpdatedAt(new Date());
        }
      } catch {
        if (!cancelled) setError("unavailable");
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

  const dates = history?.days.map((day) => formatDay(day.date, lang)).join(", ") ?? "";
  const stakeLine = history
    ? `${t.stake.replaceAll("{s}", formatStake(history.stake))}${dates ? ` ${t.resultsFor.replace("{date}", dates)}` : ""}`
    : "";
  const updated = updatedAt
    ? updatedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : "";
  const wonTone =
    history && history.trebles_placed > 0 && history.trebles_won === history.trebles_placed
      ? "pos"
      : history && history.treble_profit < 0
        ? "neg"
        : "";

  return (
    <section className="landing-wrap" id="results" aria-label={t.resT}>
      <h2>{t.resT}</h2>
      <p className="lead" style={{ marginTop: 4 }}>
        {t.resP}
      </p>
      {history ? <p className="small" style={{ marginTop: 10 }}>{stakeLine}</p> : null}
      {error ? <p className="note">{t.error}</p> : null}
      {!history && !error ? <p className="small" style={{ marginTop: 12 }}>{t.loading}</p> : null}
      {history && history.trebles_placed === 0 ? <p className="note">{t.empty}</p> : null}
      {history && history.trebles_placed > 0 ? (
        <>
          <div className="group">{t.g1}</div>
          <div className="tiles">
            <div className="tile">
              <span>{t.matchesWon}</span>
              <b className={history.matches_won > 0 ? "pos" : undefined}>{history.matches_won}</b>
            </div>
            <div className="tile">
              <span>{t.matchesLost}</span>
              <b className={history.matches_lost > 0 ? "neg" : undefined}>{history.matches_lost}</b>
            </div>
            <div className="tile sub">
              <span>{t.single}</span>
              <b className={history.single_profit > 0 ? "pos" : history.single_profit < 0 ? "neg" : undefined}>
                TZS {formatMoney(history.single_profit)}
              </b>
            </div>
          </div>
          {history.matches_pending > 0 ? (
            <p className="small">
              {t.waitingMatches}: {history.matches_pending}
            </p>
          ) : null}
          <div className="single">
            <div className="rows">
              {uniqueLegs(history.slips).map((leg) => (
                <MatchRow key={`${leg.home_team}-${leg.away_team}`} leg={leg} />
              ))}
            </div>
          </div>

          <div className="group">{t.g2}</div>
          <div className="tiles">
            <div className="tile">
              <span>{t.treblesPlaced}</span>
              <b>{history.trebles_placed}</b>
            </div>
            <div className="tile">
              <span>{t.tw}</span>
              <b className={wonTone || undefined}>
                {history.trebles_won} / {history.trebles_placed}
              </b>
            </div>
            <div className="tile sub">
              <span>{t.treble}</span>
              <b className={history.treble_profit > 0 ? "pos" : history.treble_profit < 0 ? "neg" : undefined}>
                TZS {formatMoney(history.treble_profit)}
              </b>
            </div>
          </div>
          <p className="note">{sharesALostLeg(history.slips) ? t.share : t.once}</p>
          <div>
            {history.slips.map((slip) => {
              const word = slip.result === "won" ? t.Won : slip.result === "lost" ? t.Lost : t.Pending;
              const badge = slip.result === "won" ? "won" : slip.result === "lost" ? "lost" : "wait";
              return (
                <details className="tr" key={slip.slip_id}>
                  <summary>
                    <span className="sum-left">
                      <span className={`badge ${badge}`}>{word}</span>
                      {slip.forced ? <span className="badge forced">{t.forced}</span> : null}
                      <span className="sum-odds">{slip.combined_odds.toFixed(2)}</span>
                      <span className="sum-odds">
                        {slip.date
                          .split("|")
                          .map((day) => formatDay(day, lang))
                          .join(" · ")}
                      </span>
                    </span>
                    <span className="chev" aria-hidden="true">
                      ▾
                    </span>
                  </summary>
                  <div className="rows">
                    {slip.legs.map((leg) => (
                      <MatchRow key={`${slip.slip_id}-${leg.home_team}-${leg.away_team}`} leg={leg} />
                    ))}
                  </div>
                </details>
              );
            })}
          </div>
          <p className="note">{t.warn}</p>
          <p className="small">
            {t.auto} {updated ? `${t.lu} ${updated}` : ""}
          </p>
        </>
      ) : null}
    </section>
  );
}

"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { AuthGuard } from "@/components/AuthGuard";
import { useLandingLang } from "@/components/LandingLang";
import { api, AuthUser, BbAudit, BbBacktest, BbGates, BbGame, BbHealth, BbShadow, BbShadowRule, BbSlate } from "@/lib/api";
import { fill, formatDay, Lang } from "@/lib/landingCopy";

const GATE_ICONS: Record<string, string> = {
  g1_home_over_rate_68: "🏠",
  g2_away_over_rate_68: "🛫",
  g3_away_last10_over_rate_65: "⏱",
  g4_h2h_pace_101_5: "🏃",
  g5_lineup_confirmed: "👥",
  g6_no_back_to_back: "💤",
  g7_not_tanking_or_dead_rubber: "🛡",
  g8_model_edge_6_5: "⚖️",
  g9_line_movement_under_1_5: "↔️",
  g10_model_confident_over: "🎯",
};

const AND_RULE: Record<Lang, string> = {
  en: "AND · 10 gates",
  sw: "AND · milango 10",
};

const GATE_SHORT: Record<Lang, Record<string, { name: string; thr: string }>> = {
  en: {
    g1_home_over_rate_68: { name: "Home rate", thr: "≥68% over" },
    g2_away_over_rate_68: { name: "Away rate", thr: "≥68% over" },
    g3_away_last10_over_rate_65: { name: "Away last-10", thr: "≥65% over" },
    g4_h2h_pace_101_5: { name: "H2H pace", thr: "≥101.5 poss" },
    g5_lineup_confirmed: { name: "Lineup", thr: "clear" },
    g6_no_back_to_back: { name: "Back-to-back", thr: "none" },
    g7_not_tanking_or_dead_rubber: { name: "Tanking", thr: "none" },
    g8_model_edge_6_5: { name: "Model edge", thr: "≥6.5%" },
    g9_line_movement_under_1_5: { name: "Line moves", thr: "<1.5 pts" },
    g10_model_confident_over: { name: "Confident over", thr: "≥60%" },
  },
  sw: {
    g1_home_over_rate_68: { name: "Kiwango nyumbani", thr: "≥68% over" },
    g2_away_over_rate_68: { name: "Kiwango ugenini", thr: "≥68% over" },
    g3_away_last10_over_rate_65: { name: "Ugenini mwisho-10", thr: "≥65% over" },
    g4_h2h_pace_101_5: { name: "Kasi H2H", thr: "≥101.5 pos" },
    g5_lineup_confirmed: { name: "Mpangilio", thr: "wazi" },
    g6_no_back_to_back: { name: "B2B", thr: "hakuna" },
    g7_not_tanking_or_dead_rubber: { name: "Tanking", thr: "hakuna" },
    g8_model_edge_6_5: { name: "Faida ya modeli", thr: "≥6.5%" },
    g9_line_movement_under_1_5: { name: "Mwendo wa bei", thr: "<1.5 pts" },
    g10_model_confident_over: { name: "Uhakika over", thr: "≥60%" },
  },
};

function shiftDay(day: string, delta: number): string {
  const [y, m, d] = day.split("-").map(Number);
  const base = Date.UTC(y, (m || 1) - 1, d || 1);
  const next = new Date(base + delta * 86400000);
  return next.toISOString().slice(0, 10);
}

function todayNairobi(): string {
  const now = new Date();
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Africa/Nairobi",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(now);
  return parts; // en-CA renders YYYY-MM-DD
}

function nairobiTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-GB", {
    timeZone: "Africa/Nairobi",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function pct(value: number | null | undefined, digits = 1): string {
  if (value == null) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

function num1(value: number | null | undefined): string {
  if (value == null) return "—";
  return value.toFixed(1);
}

function signed(value: number | null | undefined, digits = 1): string {
  if (value == null) return "—";
  const text = value.toFixed(digits);
  return value > 0 ? `+${text}` : text;
}

function HoopsBody() {
  const { t, lang } = useLandingLang();
  const [date, setDate] = useState<string>(() => todayNairobi());
  const [health, setHealth] = useState<BbHealth | null>(null);
  const [gates, setGates] = useState<BbGates | null>(null);
  const [slate, setSlate] = useState<BbSlate | null>(null);
  const [audit, setAudit] = useState<BbAudit | null>(null);
  const [me, setMe] = useState<AuthUser | null>(null);
  const [shadow, setShadow] = useState<BbShadow | null>(null);
  const [history, setHistory] = useState<BbShadowRule[] | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loadId = useRef(0);

  const load = useCallback(async (day: string) => {
    const myId = ++loadId.current;
    setLoading(true);
    setError(null);
    try {
      const [h, g, s, a, user] = await Promise.all([
        api.bbHealth(),
        api.bbGates(),
        api.bbGames(day),
        api.bbAudit(30),
        api.me(),
      ]);
      if (myId !== loadId.current) return;
      setHealth(h);
      setGates(g);
      setSlate(s);
      setAudit(a);
      setMe(user);
      if (user.is_admin) {
        const shadowResult = await api.bbShadow();
        if (myId !== loadId.current) return;
        setShadow(shadowResult);
      } else {
        setShadow(null);
      }
    } catch (err) {
      if (myId === loadId.current) {
        setError(err instanceof Error ? err.message : t.requestFailed);
      }
    } finally {
      if (myId === loadId.current) setLoading(false);
    }
  }, [t.requestFailed]);

  useEffect(() => {
    void load(date);
  }, [date, load]);

  const toggleHistory = useCallback(async () => {
    if (history) {
      setHistory(null);
      return;
    }
    setHistoryLoading(true);
    try {
      const backtest: BbBacktest = await api.bbBacktest();
      setHistory(backtest.candidate_rules.filter((r) => r.n > 0));
    } catch (err) {
      setError(err instanceof Error ? err.message : t.requestFailed);
    } finally {
      setHistoryLoading(false);
    }
  }, [history, t.requestFailed]);

  const gameCards: BbGame[] = slate?.games ?? [];
  const failedCount = gameCards.filter((g) => g.gate_run && !g.gate_run.passed).length;
  const gateShorts = GATE_SHORT[lang];
  const activeRules = shadow?.rules.filter((r) => r.n > 0) ?? [];

  const ruleRow = (rule: BbShadowRule, prefix: string, showClv: boolean) => (
    <div key={`${prefix}-${rule.key}`} className="hoops-shadow-rule" role="listitem">
      <span className="hoops-shadow-name">{rule.label}</span>
      <span className="hoops-shadow-stats">
        <span>
          <b>{rule.hit_rate != null ? pct(rule.hit_rate, 1) : "—"}</b> {t.hitRateWord}
        </span>
        <span>
          <b>{rule.roi != null ? `${signed(rule.roi * 100)}%` : "—"}</b> {t.roiWord}
        </span>
        <span>
          <b>{showClv && rule.avg_clv != null ? signed(rule.avg_clv) : "—"}</b> {t.clvAvgWord}
        </span>
        <span className="hoops-shadow-n">
          {rule.won}–{rule.lost} · n={rule.n}
        </span>
      </span>
    </div>
  );

  return (
    <div className="hoops-wrap">
      <header className="hoops-head">
        <div>
          <Link href="/desk" className="hoops-back">
            ← {t.hoopsBack}
          </Link>
          <h1 className="hoops-title">{t.hoopsTitle}</h1>
          <p className="hoops-sub">{t.hoopsSub}</p>
        </div>
        <button type="button" className="btn primary" disabled={loading} onClick={() => void load(date)}>
          {t.refreshTips}
        </button>
      </header>

      <section className="hoops-status" aria-label={t.lastScan}>
        <span className={`chip ${health?.enabled ? "ok" : ""}`}>
          {health?.enabled ? t.connected : t.offline}
        </span>
        <span className="chip">
          {t.lastScan}: {health?.last_scan_at ? nairobiTime(health.last_scan_at) : t.scanNever}
        </span>
        <span className="chip">
          {t.slateWord}: {slate?.count ?? health?.games_today ?? 0}
        </span>
        <span className="chip">
          {t.tipsWord}: {health?.pending_tips ?? 0} {t.pending.toLowerCase()}
        </span>
        <span className="chip">{fill(t.lockedWord, { n: health?.lock_minutes ?? 75 })}</span>
      </section>

      <nav className="hoops-daynav" aria-label={t.matchDate}>
        <button type="button" onClick={() => setDate((d) => shiftDay(d, -1))} aria-label={t.prevDay}>
          ◀
        </button>
        <div className="hoops-day">{formatDay(date, lang)}</div>
        <button type="button" onClick={() => setDate((d) => shiftDay(d, 1))} aria-label={t.nextDay}>
          ▶
        </button>
        <button type="button" className="hoops-today" onClick={() => setDate(todayNairobi())}>
          {t.todayBtn}
        </button>
      </nav>

      {error ? (
        <p className="hoops-error" role="alert">
          {t.loadHoops}: {error}
        </p>
      ) : null}

      <section className="hoops-audit" aria-label={t.auditTitle}>
        <p className="hoops-label">{t.auditTitle}</p>
        <div className="hoops-audit-row">
          <div>
            <b>{audit ? pct(audit.hit_rate) : "—"}</b>
            <span>{t.hitRateWord}</span>
          </div>
          <div>
            <b>{audit?.won ?? 0}</b>
            <span>{t.won}</span>
          </div>
          <div>
            <b>{audit?.lost ?? 0}</b>
            <span>{t.lost}</span>
          </div>
          <div>
            <b>{audit?.push ?? 0}</b>
            <span>{t.pushWord}</span>
          </div>
          <div>
            <b>{audit?.tips ?? 0}</b>
            <span>{t.tipsWord}</span>
          </div>
        </div>
        <p className="hoops-audit-note">{t.auditNote}</p>
        <p className="hoops-clv">
          <span>
            <b>{audit ? signed(audit.clv.avg_points) : "—"}</b> {t.clvAvgWord}
          </span>
          <span>
            <b>{audit && audit.clv.beat_close_pct != null ? pct(audit.clv.beat_close_pct, 0) : "—"}</b>{" "}
            {t.beatCloseWord}
          </span>
          <span className="hoops-clv-n">
            {t.clvWord} n={audit?.clv.n ?? 0}
          </span>
        </p>
      </section>

      {me?.is_admin ? (
        <section className="hoops-shadow" aria-label={t.shadowTitle}>
          <p className="hoops-label">{t.shadowTitle}</p>
          {activeRules.length > 0 ? (
            <div className="hoops-shadow-list" role="list">
              {activeRules.map((rule) => ruleRow(rule, "live", true))}
            </div>
          ) : (
            <p className="hoops-hint">{t.shadowEmpty}</p>
          )}
          <div className="hoops-shadow-actions">
            <button
              type="button"
              className="hoops-shadow-btn"
              disabled={historyLoading}
              onClick={() => void toggleHistory()}
            >
              {history ? t.hideHistory : t.showHistory}
            </button>
          </div>
          {history ? (
            <>
              <div className="hoops-shadow-list" role="list">
                {history.map((rule) => ruleRow(rule, "hist", false))}
              </div>
              <p className="hoops-audit-note">{t.historyNote}</p>
            </>
          ) : null}
          <p className="hoops-audit-note">{t.shadowNote}</p>
        </section>
      ) : null}

      <section className="hoops-slate" aria-label={t.slateWord}>
        <p className="hoops-label">
          {t.slateWord} — {formatDay(date, lang)}{" "}
          {failedCount > 0 ? <span className="hoops-rejected-tag">· {failedCount}× {t.rejectedWord.toLowerCase()}</span> : null}
        </p>

        {loading && !slate ? <p className="hoops-empty">{t.loading}</p> : null}

        {!loading && gameCards.length === 0 ? (
          <div className="hoops-empty">
            <p>{fill(t.noGames, { date: formatDay(date, lang) })}</p>
            <p className="hoops-hint">{t.noGamesHint}</p>
          </div>
        ) : null}

        {gameCards.map((game) => {
          const checks = game.gate_run?.checks ?? null;
          const failedGates = gates?.gates.filter((g) => checks && checks[g.gate] && !checks[g.gate].passed) ?? [];
          return (
            <article key={game.id} className={`hoops-game ${game.tip ? "tipped" : ""}`}>
              <div className="hoops-game-top">
                <span className="hoops-time">{nairobiTime(game.tipoff_at)}</span>
                <span className="hoops-teams">
                  {game.away_team} @ {game.home_team}
                </span>
                {game.status === "post" || game.status === "live" || game.status === "in" ? (
                  <span className="hoops-score">
                    {game.away_score ?? "–"} : {game.home_score ?? "–"}
                    {game.status === "live" || game.status === "in" ? (
                      <span className="hoops-live">{t.live}</span>
                    ) : game.result ? (
                      <span className={`hoops-result ${game.result}`}>
                        {game.result === "over"
                          ? `${t.overWord} ✓`
                          : game.result === "under"
                            ? `${t.underWord} ✗`
                            : t.pushWord}
                      </span>
                    ) : null}
                  </span>
                ) : null}
                {game.tip ? (
                  <span className={`hoops-tip ${game.tip.status.toLowerCase()}`}>
                    {game.tip.status === "AUTOMATED_REJECTED"
                      ? t.rejectedWord
                      : game.tip.status === "PUSH"
                        ? t.pushWord
                        : game.tip.status === "PENDING"
                          ? `${game.tip.pick} ${num1(game.tip.line)} · ${t.pending}`
                          : game.tip.status === "WON"
                            ? t.won
                            : t.lost}
                  </span>
                ) : null}
              </div>

              <div className="hoops-metrics">
                <div>
                  <span>{t.marketWord}</span>
                  <b>{game.tip ? num1(game.tip.line) : num1(game.market_total)}</b>
                </div>
                <div>
                  <span>{t.modelTotalWord}</span>
                  <b>{num1(game.model?.total)}</b>
                </div>
                <div>
                  <span>{t.pOverWord}</span>
                  <b>{pct(game.model?.p_over)}</b>
                </div>
                <div>
                  <span>{t.edgeWord}</span>
                  <b>{game.model?.edge != null ? pct(game.model.edge) : "—"}</b>
                </div>
              </div>

              {checks && gates ? (
                <div className="hoops-gates" role="list">
                  {gates.gates.map((gateInfo, index) => {
                    const check = checks[gateInfo.gate];
                    if (!check) return null;
                    return (
                      <span
                        key={gateInfo.gate}
                        role="listitem"
                        className={`gate-chip ${check.passed ? "pass" : "fail"}`}
                        title={`${gateInfo.label} — ${check.reason}`}
                      >
                        <b>{index + 1}</b>
                        {check.passed ? "✓" : "✗"}
                      </span>
                    );
                  })}
                  <span className={`gate-verdict ${game.gate_run?.passed ? "pass" : "fail"}`}>
                    {game.gate_run?.passed
                      ? fill(t.gateCount, { n: game.gate_run.passed_count })
                      : `${game.gate_run?.passed_count ?? 0}/10 — ${t.rejectedWord}`}
                  </span>
                </div>
              ) : (
                <p className="hoops-hint">
                  {t.noRunYet}
                  {game.status === "scheduled" ? ` — ${t.autoOnGameDay}` : ""}
                </p>
              )}

              {failedGates.length > 0 ? (
                <ul className="hoops-reasons">
                  {failedGates.map((g) => (
                    <li key={g.gate}>
                      <b>{g.label}</b>: {checks?.[g.gate]?.reason}
                    </li>
                  ))}
                </ul>
              ) : null}

              {game.tip?.notes ? <p className="hoops-note">{game.tip.notes}</p> : null}
            </article>
          );
        })}
      </section>

      <section className="hoops-rules" aria-label={t.gatesTitle}>
        <div className="hoops-rules-head">
          <p className="hoops-label">{t.gatesTitle}</p>
          <span className="hoops-and-badge">{AND_RULE[lang]}</span>
        </div>
        <div className="hoops-tiles" role="list">
          {(gates?.gates ?? []).map((g) => {
            const short = gateShorts[g.gate];
            return (
              <div
                key={g.gate}
                role="listitem"
                className="hoops-tile"
                title={`${short?.name ?? g.label} — ${short?.thr ?? g.threshold}`}
              >
                <span className="hoops-tile-ico">{GATE_ICONS[g.gate] ?? "•"}</span>
                <span className="hoops-tile-name">{short?.name ?? g.label}</span>
                <span className="hoops-tile-thr">{short?.thr ?? g.threshold}</span>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}

export default function HoopsPage() {
  return (
    <AuthGuard>
      <HoopsBody />
    </AuthGuard>
  );
}

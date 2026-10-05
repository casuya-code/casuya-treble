"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AuthGuard } from "@/components/AuthGuard";
import { DeskSide } from "@/components/DeskSide";
import { MenuButton, useLandingLang } from "@/components/LandingLang";
import { StatusKind } from "@/components/StatusBadge";
import { SlipCard } from "@/components/SlipCard";
import Link from "next/link";
import { api, GenerateResult, Slip, WeatherNote } from "@/lib/api";
import { clearToken, markSignedOut } from "@/lib/auth";
import { fill, formatDay } from "@/lib/landingCopy";
import { nairobiDay, slipDates } from "@/lib/format";
import { useRouter } from "next/navigation";

type Filter = StatusKind;

/** One BetPawa pull per browser session. The Import button still refreshes on demand. */
let betpawaAutoImport: ReturnType<typeof api.importBetPawa> | null = null;

function importBetPawaOnce() {
  if (!betpawaAutoImport) {
    betpawaAutoImport = api.importBetPawa().catch((error) => {
      betpawaAutoImport = null;
      throw error;
    });
  }
  return betpawaAutoImport;
}

function weatherDetail(
  notes: WeatherNote[] | undefined,
  t: { weatherRain: string; weatherSnow: string; weatherWind: string },
): string {
  if (!notes?.length) return "";
  const label: Record<string, string> = { rain: t.weatherRain, snow: t.weatherSnow, wind: t.weatherWind };
  const shown = notes.slice(0, 4).map((note) => `${note.match}: ${label[note.reason] ?? note.reason}`);
  return ` ${shown.join(". ")}.`;
}

function trebleGapMessage(
  result: GenerateResult,
  t: {
    noTrebleNone: string;
    noTrebleStarted: string;
    noTreblePrice: string;
    noTrebleFew: string;
    noTrebleSpread: string;
    noTrebleOdds: string;
    noTrebleFloor: string;
    noTrebleCorners: string;
    noTrebleWeather: string;
    noTrebleAdmin: string;
    weatherRain: string;
    weatherSnow: string;
    weatherWind: string;
  },
  isAdmin: boolean,
): string {
  const counts = {
    stored: result.stored,
    upcoming: result.upcoming,
    priced: result.priced,
    same: result.same_day,
    n: result.weather?.length ?? 0,
  };
  const text =
    result.reason === "none_loaded"
      ? t.noTrebleNone
      : result.reason === "all_started"
        ? fill(t.noTrebleStarted, counts)
        : result.reason === "no_price"
          ? fill(t.noTreblePrice, counts)
          : result.reason === "too_few"
            ? fill(t.noTrebleFew, counts)
            : result.reason === "spread_days"
              ? fill(t.noTrebleSpread, counts)
            : result.reason === "below_floor"
              ? t.noTrebleFloor
              : result.reason === "no_corner"
                ? t.noTrebleCorners
              : result.reason === "weather"
                ? fill(t.noTrebleWeather, counts)
                : fill(t.noTrebleOdds, counts);
  const detail = weatherDetail(result.weather, t);
  if (isAdmin && (result.reason === "none_loaded" || result.reason === "all_started")) {
    return `${text} ${t.noTrebleAdmin}${detail}`;
  }
  return `${text}${detail}`;
}

function DeskPage() {
  const router = useRouter();
  const { lang, t } = useLandingLang();
  const [slips, setSlips] = useState<Slip[]>([]);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [loading, setLoading] = useState(false);
  const [apiOk, setApiOk] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("ALL");
  const [dateFilter, setDateFilter] = useState<string | null>(null);
  const [showAlternatives, setShowAlternatives] = useState(false);
  const [cornerMarket, setCornerMarket] = useState(false);
  const [oddsApiReady, setOddsApiReady] = useState(false);
  const [betpawaReady, setBetpawaReady] = useState(true);
  const [showTools, setShowTools] = useState(false);
  const [sideOpen, setSideOpen] = useState(false);
  const [retentionDays, setRetentionDays] = useState(90);

  const refresh = useCallback(async () => {
    let healthOk = false;
    try {
      const health = await api.health();
      healthOk = health.status === "ok" || health.status === "degraded";
      setApiOk(healthOk);
    } catch {
      setApiOk(false);
      setError(t.serverOffline);
      return false;
    }

    let admin = false;
    try {
      const me = await api.me();
      admin = Boolean(me.is_admin);
      setUserEmail(me.email);
      setIsAdmin(admin);
    } catch (e) {
      if (e instanceof Error && e.message === "Session expired") return false;
      setError(e instanceof Error ? e.message : t.loadAccount);
      return false;
    }

    try {
      const provider = await api.oddsProviderStatus();
      setOddsApiReady(provider.configured);
    } catch {
      setOddsApiReady(false);
    }

    try {
      const bp = await api.betpawaStatus();
      setBetpawaReady(bp.configured);
    } catch {
      setBetpawaReady(false);
    }

    try {
      const retention = await api.retentionDays();
      setRetentionDays(retention.retention_days);
      setSlips(await api.listSlips({ days: retention.retention_days }));
      setError(null);
      return { admin };
    } catch (e) {
      setError(e instanceof Error ? e.message : t.loadSlips);
      return false;
    }
  }, [t.loadAccount, t.loadSlips, t.serverOffline]);

  useEffect(() => {
    let cancelled = false;
    let admin = false;
    void (async () => {
      setLoading(true);
      try {
        const session = await refresh();
        if (cancelled || !session) return;
        admin = session.admin;
        const imported = await importBetPawaOnce();
        if (cancelled) return;
        const cleared =
          imported.practice_removed > 0 ? ` ${fill(t.practiceRemoved, { n: imported.practice_removed })}` : "";
        const historyCount = (imported.history_imported ?? 0) + (imported.history_updated ?? 0);
        const history = historyCount > 0 ? ` ${fill(t.historyAdded, { n: historyCount })}` : "";
        const again = session.admin ? ` ${t.importAgain}` : "";
        setInfo(`${fill(t.betpawaUpdated, { n: imported.events_fetched })}${cleared}${history}${again}`);
        const retention = await api.retentionDays();
        if (cancelled) return;
        setSlips(await api.listSlips({ days: retention.retention_days }));
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : admin ? t.refreshFailed : t.refreshFailedOpen);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refresh, t]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.visibilityState === "hidden") return;
      api
        .listSlips({ days: retentionDays })
        .then(setSlips)
        .catch(() => undefined);
    }, 20000);
    return () => window.clearInterval(timer);
  }, [retentionDays]);

  useEffect(() => {
    if (!info) return;
    const timer = setTimeout(() => setInfo(null), 4000);
    return () => clearTimeout(timer);
  }, [info]);

  const filtered = useMemo(() => {
    const byStatus = (() => {
      if (filter === "ALL") return slips;
      if (filter === "PLACED") return slips.filter((s) => s.placed_on_betpawa);
      if (filter === "PENDING" || filter === "WON" || filter === "LOST" || filter === "LIVE") {
        return slips.filter((s) => s.status === filter);
      }
      return slips;
    })();
    if (!dateFilter) return byStatus;
    return byStatus.filter((slip) => {
      const days = slipDates(slip.legs.map((leg) => leg.kickoff_at));
      return days.length === 1 && days[0] === dateFilter;
    });
  }, [slips, filter, dateFilter]);

  const matchDates = useMemo(() => {
    const days = new Set<string>();
    for (const slip of slips) {
      const slipDays = slipDates(slip.legs.map((leg) => leg.kickoff_at));
      if (slipDays.length === 1) days.add(slipDays[0]);
    }
    return [...days].sort();
  }, [slips]);

  useEffect(() => {
    if (dateFilter && !matchDates.includes(dateFilter)) setDateFilter(null);
  }, [dateFilter, matchDates]);

  const dayGroups = useMemo(() => {
    const groups = new Map<string, Slip[]>();
    for (const slip of filtered) {
      const days = slipDates(slip.legs.map((leg) => leg.kickoff_at));
      const key = days.join("|") || nairobiDay(slip.timestamp);
      const rows = groups.get(key) ?? [];
      rows.push(slip);
      groups.set(key, rows);
    }
    return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [filtered]);

  const topSlipId =
    filter === "ALL" || filter === "PENDING" ? filtered.find((s) => s.status === "PENDING")?.slip_id : undefined;

  const stats = useMemo(() => {
    const pending = slips.filter((s) => s.status === "PENDING").length;
    const placed = slips.filter((s) => s.placed_on_betpawa).length;
    const won = slips.filter((s) => s.status === "WON").length;
    const lost = slips.filter((s) => s.status === "LOST").length;
    return { pending, placed, won, lost, total: slips.length };
  }, [slips]);

  async function runAction(action: () => Promise<void>) {
    setLoading(true);
    setError(null);
    try {
      await action();
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : t.somethingWrong);
    } finally {
      setLoading(false);
    }
  }

  async function copySlip(slip: Slip) {
    try {
      await navigator.clipboard.writeText(slip.betpawa_copy_text);
      setCopiedId(slip.slip_id);
      setTimeout(() => setCopiedId(null), 3500);
    } catch {
      setError(t.copyFailed);
    }
  }

  function logout() {
    clearToken();
    markSignedOut();
    router.replace("/");
  }

  function closePhoneSide() {
    if (window.matchMedia("(max-width: 800px)").matches) setSideOpen(false);
  }

  function generate() {
    closePhoneSide();
    void runAction(async () => {
      const created = await api.generateSlips({
        maxSlips: showAlternatives ? 3 : 1,
        replacePending: true,
        market: cornerMarket ? "corners" : "goals",
      });
      if (created.slips.length === 0) {
        throw new Error(trebleGapMessage(created, t, isAdmin));
      }
      const held = weatherDetail(created.weather, t);
      if (created.slips.some((slip) => slip.forced)) {
        const odds = created.slips.map((slip) => slip.closing_odds.toFixed(2)).join(", ");
        setInfo(`${fill(t.forcedReady, { odds })}${held}`);
      } else {
        const ready = showAlternatives ? fill(t.topReady, { n: created.slips.length }) : t.bestReady;
        setInfo(`${ready}${held}`);
      }
    });
  }

  return (
    <>
      {loading ? <div className="loading-bar" aria-hidden /> : null}
      <div className={`desk-app ${sideOpen ? "side-open" : ""}`}>
        {sideOpen ? <button type="button" className="menu-backdrop" aria-label={t.menu} onClick={() => setSideOpen(false)} /> : null}
        <DeskSide
          email={userEmail}
          apiOk={apiOk}
          isAdmin={isAdmin}
          loading={loading}
          lang={lang}
          stats={stats}
          filter={filter}
          dateFilter={dateFilter}
          matchDates={matchDates}
          showAlternatives={showAlternatives}
          cornerMarket={cornerMarket}
          showTools={showTools}
          onFilter={(next) => {
            setFilter(next);
            closePhoneSide();
          }}
          onDate={(day) => {
            setDateFilter(day);
            closePhoneSide();
          }}
          onGenerate={generate}
          onAlternatives={setShowAlternatives}
          onCornerMarket={setCornerMarket}
          onRefresh={() => {
            closePhoneSide();
            void refresh();
          }}
          onToggleTools={() => setShowTools((value) => !value)}
          onLogout={logout}
          tools={
            <div className="tools-row">
              {betpawaReady ? (
                <button
                  type="button"
                  className="btn btn-sm primary"
                  disabled={loading}
                  onClick={() =>
                    runAction(async () => {
                      const r = await api.importBetPawa();
                      const cleared =
                        r.practice_removed > 0 ? ` ${fill(t.practiceRemoved, { n: r.practice_removed })}` : "";
                      setInfo(`${fill(t.importSaved, { n: r.imported + r.updated })}${cleared}`);
                    })
                  }
                >
                  {t.importBetPawa}
                </button>
              ) : null}
              <button
                type="button"
                className="btn btn-sm"
                disabled={loading}
                onClick={() =>
                  runAction(async () => {
                    const rows = await api.seedDemo();
                    setInfo(fill(t.practiceLoaded, { n: rows.length }));
                  })
                }
              >
                {t.practiceData}
              </button>
              {oddsApiReady ? (
                <button
                  type="button"
                  className="btn btn-sm"
                  disabled={loading}
                  onClick={() =>
                    runAction(async () => {
                      const r = await api.importOddsApi();
                      setInfo(fill(t.oddsImported, { n: r.imported + r.updated }));
                    })
                  }
                >
                  {t.importOdds}
                </button>
              ) : null}
              <button
                type="button"
                className="btn btn-sm"
                disabled={loading}
                onClick={() =>
                  runAction(async () => {
                    const r = await api.syncStatus();
                    setInfo(r.slips_updated ? fill(t.slipsUpdated, { n: r.slips_updated }) : t.statusesOk);
                  })
                }
              >
                {t.syncScores}
              </button>
            </div>
          }
        />

        <div className="desk-main">
          <header className="desk-top">
            <Link href="/" className="brand">
              <span className="brand-mark">C</span>
              <span className="brand-text">
                Casuya <strong className="brand-long">Treble</strong>
              </span>
            </Link>
            <MenuButton open={sideOpen} label={t.menu} onToggle={() => setSideOpen((value) => !value)} />
          </header>

          {error ? (
            <p className="banner error" role="alert">
              {error}
            </p>
          ) : null}
          {info ? <p className="banner info">{info}</p> : null}

        <section id="slips" className="slip-grid" aria-label={`Slip history, last ${retentionDays} days`}>
          {filtered.length === 0 ? (
            <div className="empty card">
              <p className="empty-title">
                {dateFilter && filter === "ALL"
                  ? fill(t.noTrebleOnDate, { date: formatDay(dateFilter, lang) })
                  : t.noTrebles}
              </p>
              {dateFilter && filter === "ALL" ? null : (
                <p className="empty-steps">
                  {t.noTreblesBody}
                  {isAdmin ? ` ${t.noTreblesAdmin}` : null}
                </p>
              )}
            </div>
          ) : (
            dayGroups.map(([dayKey, rows]) => (
              <div key={dayKey} className="slip-day">
                <h3 className="slip-day-head">{dayKey.split("|").map((day) => formatDay(day, lang)).join(" · ")}</h3>
                {rows.map((slip) => (
                  <SlipCard
                    key={slip.slip_id}
                    slip={slip}
                    featured={slip.slip_id === topSlipId && slip.status === "PENDING"}
                    copied={copiedId === slip.slip_id}
                    loading={loading}
                    onCopy={() => copySlip(slip)}
                    onTogglePlaced={() =>
                      runAction(async () => {
                        await api.markPlaced(slip.slip_id, !slip.placed_on_betpawa);
                      })
                    }
                  />
                ))}
              </div>
            ))
          )}
        </section>
        </div>
      </div>
    </>
  );
}

export default function DeskRoute() {
  return (
    <AuthGuard>
      <DeskPage />
    </AuthGuard>
  );
}

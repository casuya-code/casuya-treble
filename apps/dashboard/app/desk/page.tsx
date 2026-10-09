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

import { fill, formatDay, formatMonth, WEEKDAYS } from "@/lib/landingCopy";

import { nairobiDay, slipDates } from "@/lib/format";

import { useRouter } from "next/navigation";



type Filter = StatusKind;

type Market = "goals" | "corners";



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

    noTrebleNoModel: string;

    noTrebleModeled: string;

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

    modeled: result.modeled ?? 0,

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

              : result.reason === "no_model"

                ? fill(t.noTrebleNoModel, counts)

              : result.reason === "no_corner"

                ? t.noTrebleCorners

              : result.reason === "weather"

                ? fill(t.noTrebleWeather, counts)

                : fill(t.noTrebleOdds, counts);

  const detail = weatherDetail(result.weather, t);

  // Say how much of the board the model could actually rate, so an empty day
  // never looks like the odds range alone was to blame.
  const coverage =
    result.reason !== "no_model" &&
    result.modeled != null &&
    result.modeled < result.upcoming
      ? ` ${fill(t.noTrebleModeled, counts)}`
      : "";

  if (isAdmin && (result.reason === "none_loaded" || result.reason === "all_started")) {

    return `${text} ${t.noTrebleAdmin}${detail}`;

  }

  return `${text}${coverage}${detail}`;

}



/** Format a Date as a "YYYY-MM-DD" UTC day string. */
function isoDay(date: Date): string {
  return date.toISOString().slice(0, 10);
}

/** Add whole days to a "YYYY-MM-DD" string (UTC calendar math, no timezone drift). */
function shiftDays(day: string, delta: number): string {
  const [year, m, d] = day.split("-").map(Number);
  return isoDay(new Date(Date.UTC(year, m - 1, d + delta)));
}

/** Monday of the week containing the given day. */
function mondayOf(day: string): string {
  const [year, m, d] = day.split("-").map(Number);
  const date = new Date(Date.UTC(year, m - 1, d));
  date.setUTCDate(date.getUTCDate() - ((date.getUTCDay() + 6) % 7));
  return isoDay(date);
}

/** Move a "YYYY-MM-DD" focus day by whole months, clamping to the target month's length. */
function shiftFocusMonths(day: string, delta: number): string {
  const [year, m, d] = day.split("-").map(Number);
  const target = new Date(Date.UTC(year, m - 1 + delta, 1));
  const daysInTarget = new Date(Date.UTC(target.getUTCFullYear(), target.getUTCMonth() + 1, 0)).getUTCDate();
  target.setUTCDate(Math.min(d, daysInTarget));
  return isoDay(target);
}

function DeskPage() {

  const router = useRouter();

  const { lang, t } = useLandingLang();

  const [slips, setSlips] = useState<Slip[]>([]);

  const [isAdmin, setIsAdmin] = useState(false);

  const [loading, setLoading] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const [info, setInfo] = useState<string | null>(null);

  const [copiedId, setCopiedId] = useState<string | null>(null);

  const [filter, setFilter] = useState<Filter>("ALL");

  const [dateFilter, setDateFilter] = useState<string | null>(null);

  /** null = today (default); a "YYYY-MM-DD" focus day once the user steps around. */
  const [focusDate, setFocusDate] = useState<string | null>(null);

  const [showAlternatives, setShowAlternatives] = useState(false);

  const [markets, setMarkets] = useState<Market[]>(["goals", "corners"]);

  const [oddsApiReady, setOddsApiReady] = useState(false);

  const [betpawaReady, setBetpawaReady] = useState(true);

  const [showTools, setShowTools] = useState(false);

  const [sideOpen, setSideOpen] = useState(false);

  const [retentionDays, setRetentionDays] = useState(90);



  const refresh = useCallback(async () => {

    try {

      await api.health();

    } catch {

      setError(t.serverOffline);

      return false;

    }



    let admin = false;

    try {

      const me = await api.me();

      admin = Boolean(me.is_admin);

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

        .then((next) => {

          setSlips(next);

          setError(null);

        })

        .catch(() => undefined);

    }, 20000);

    return () => window.clearInterval(timer);

  }, [retentionDays]);



  useEffect(() => {

    if (!info) return;

    const timer = setTimeout(() => setInfo(null), 4000);

    return () => clearTimeout(timer);

  }, [info]);



  const todayStr = nairobiDay(new Date().toISOString());
  const todayMonth = todayStr.slice(0, 7);

  const byStatus = useMemo(() => {

    if (filter === "ALL") return slips;

    if (filter === "PLACED") return slips.filter((s) => s.placed_on_betpawa);

    if (filter === "PENDING" || filter === "WON" || filter === "LOST" || filter === "LIVE") {

      return slips.filter((s) => s.status === filter);

    }

    return slips;

  }, [slips, filter]);

  /** Months the Previous/Next control can reach: every month that still holds slips, plus the current month. */
  const monthBounds = useMemo(() => {

    let min = todayMonth;

    let max = todayMonth;

    for (const slip of byStatus) {

      const days = slipDates(slip.legs.map((leg) => leg.kickoff_at));

      const monthDays = days.length > 0 ? days : [nairobiDay(slip.timestamp)];

      for (const day of monthDays) {

        const month = day.slice(0, 7);

        if (month < min) min = month;

        if (month > max) max = month;

      }

    }

    return { min, max };

  }, [byStatus, todayMonth]);

  /** The focus day drives everything below: the week strip, the month grid,
      and the month/year steps. Defaults to today. */
  const focusDay = useMemo(() => focusDate ?? todayStr, [focusDate, todayStr]);
  const viewMonth = useMemo(() => focusDay.slice(0, 7), [focusDay]);
  const weekStart = useMemo(() => mondayOf(focusDay), [focusDay]);
  const weekDays = useMemo(() => Array.from({ length: 7 }, (_, i) => shiftDays(weekStart, i)), [weekStart]);

  /** A picked date applies while it sits in the viewed month — even a day with
      no slips, so the calendar can answer "trebles created or not". */
  const activeDate = dateFilter && dateFilter.startsWith(viewMonth) ? dateFilter : null;

  /** Single-day slips by day, across months — circles both the grid and the week strip. */
  const slipDayCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const slip of slips) {
      const slipDays = slipDates(slip.legs.map((leg) => leg.kickoff_at));
      if (slipDays.length !== 1) continue;
      const day = slipDays[0];
      counts.set(day, (counts.get(day) ?? 0) + 1);
    }
    return counts;
  }, [slips]);

  /** Sidebar date list: the viewed month's slip days, plus the picked day so an empty pick stays visible. */
  const matchDates = useMemo(() => {
    const days = new Set<string>();
    for (const day of slipDayCounts.keys()) {
      if (day.startsWith(viewMonth)) days.add(day);
    }
    if (activeDate) days.add(activeDate);
    return [...days].sort();
  }, [slipDayCounts, viewMonth, activeDate]);

  /** Every arrow steps the focus and disables once the target month would fall
      outside the range that still holds slips (or the current month). */
  const prevWeekStart = shiftDays(weekStart, -7);
  const nextWeekStart = shiftDays(weekStart, 7);
  const weekPrevDisabled = shiftDays(prevWeekStart, 6).slice(0, 7) < monthBounds.min;
  const weekNextDisabled = nextWeekStart.slice(0, 7) > monthBounds.max;
  const monthPrevDisabled = shiftFocusMonths(focusDay, -1).slice(0, 7) < monthBounds.min;
  const monthNextDisabled = shiftFocusMonths(focusDay, 1).slice(0, 7) > monthBounds.max;
  const yearPrevDisabled = shiftFocusMonths(focusDay, -12).slice(0, 7) < monthBounds.min;
  const yearNextDisabled = shiftFocusMonths(focusDay, 12).slice(0, 7) > monthBounds.max;

  /** Clicking a day (strip or grid) focuses it and toggles the date filter. */
  const pickDay = (day: string) => {
    setFocusDate(day);
    setDateFilter(dateFilter === day ? null : day);
  };

  const filtered = useMemo(() => {

    if (!activeDate) return byStatus;

    return byStatus.filter((slip) => {

      const days = slipDates(slip.legs.map((leg) => leg.kickoff_at));

      return days.length === 1 && days[0] === activeDate;

    });

  }, [byStatus, activeDate]);

  /** Newest slip in view — pinned above the date groups so the last slip is always first. */
  const pinned = useMemo(
    () => [...filtered].sort((a, b) => b.timestamp.localeCompare(a.timestamp))[0] ?? null,
    [filtered],
  );

  /** The pin stays month-independent; the date groups below show the viewed month only. */
  const monthRows = useMemo(() => {

    return filtered.filter((slip) => {

      const days = slipDates(slip.legs.map((leg) => leg.kickoff_at));

      if (days.length === 0) return nairobiDay(slip.timestamp).startsWith(viewMonth);

      return days.some((day) => day.startsWith(viewMonth));

    });

  }, [filtered, viewMonth]);






  const dayGroups = useMemo(() => {

    const groups = new Map<string, Slip[]>();

    for (const slip of monthRows) {

      if (slip.slip_id === pinned?.slip_id) continue;

      const days = slipDates(slip.legs.map((leg) => leg.kickoff_at));

      const key = days.join("|") || nairobiDay(slip.timestamp);

      const rows = groups.get(key) ?? [];

      rows.push(slip);

      groups.set(key, rows);

    }

    return [...groups.entries()].sort(([a], [b]) => b.localeCompare(a));

  }, [monthRows, pinned]);

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

      setTimeout(() => setCopiedId((current) => (current === slip.slip_id ? null : current)), 3500);

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

        market: markets,

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

          isAdmin={isAdmin}

          loading={loading}

          lang={lang}

          stats={stats}

          filter={filter}

          dateFilter={activeDate}

          matchDates={matchDates}

          showAlternatives={showAlternatives}

          wantGoals={markets.includes("goals")}

          wantCorners={markets.includes("corners")}

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

          onToggleMarket={(market) =>
            setMarkets((current) => {
              if (current.includes(market)) {
                const next = current.filter((value) => value !== market);
                return next.length > 0 ? next : current;
              }
              return [...current, market];
            })
          }

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

          {slips.length > 0 ? (

            <div className="month-picker">

              <div className="week-nav">

                <button

                  type="button"

                  className="btn btn-sm month-step"

                  aria-label={t.prevWeek}

                  disabled={weekPrevDisabled}

                  onClick={() => setFocusDate(shiftDays(focusDay, -7))}

                >

                  ‹

                </button>

                <div

                  className="week-strip"

                  role="group"

                  aria-label={`${formatDay(weekStart, lang)} – ${formatDay(shiftDays(weekStart, 6), lang)}`}

                >

                  {weekDays.map((day, i) => {

                    const slipsOnDay = slipDayCounts.get(day) ?? 0;

                    const selected = day === activeDate;

                    const classes = [

                      "wk-day",

                      slipsOnDay > 0 ? "has-slip" : "",

                      day === todayStr ? "is-today" : "",

                      selected ? "is-selected" : "",

                    ].filter(Boolean).join(" ");

                    const label = formatDay(day, lang);

                    return (

                      <button

                        key={day}

                        type="button"

                        className={classes}

                        aria-pressed={selected}

                        aria-label={slipsOnDay > 1 ? `${label} · ${fill(t.slipCount, { n: slipsOnDay })}` : label}

                        onClick={() => pickDay(day)}

                      >

                        <span className="wk-wd">{WEEKDAYS[lang][i]}</span>

                        <span className="wk-num">{Number(day.slice(8))}</span>

                      </button>

                    );

                  })}

                </div>

                <button

                  type="button"

                  className="btn btn-sm month-step"

                  aria-label={t.nextWeek}

                  disabled={weekNextDisabled}

                  onClick={() => setFocusDate(shiftDays(focusDay, 7))}

                >

                  ›

                </button>

              </div>

              <div className="month-nav">

                <button

                  type="button"

                  className="btn btn-sm month-step year-step"

                  aria-label={t.prevYear}

                  disabled={yearPrevDisabled}

                  onClick={() => setFocusDate(shiftFocusMonths(focusDay, -12))}

                >

                  ‹‹

                </button>

                <div className="month-nav-mid">

                  <button

                    type="button"

                    className="btn btn-sm month-step"

                    aria-label={t.prevMonth}

                    disabled={monthPrevDisabled}

                    onClick={() => setFocusDate(shiftFocusMonths(focusDay, -1))}

                  >

                    ‹

                  </button>

                  <span className="month-label">{formatMonth(viewMonth, lang)}</span>

                  <button

                    type="button"

                    className="btn btn-sm month-step"

                    aria-label={t.nextMonth}

                    disabled={monthNextDisabled}

                    onClick={() => setFocusDate(shiftFocusMonths(focusDay, 1))}

                  >

                    ›

                  </button>

                </div>

                <button

                  type="button"

                  className="btn btn-sm month-step year-step"

                  aria-label={t.nextYear}

                  disabled={yearNextDisabled}

                  onClick={() => setFocusDate(shiftFocusMonths(focusDay, 12))}

                >

                  ››

                </button>

              </div>

            </div>

          ) : null}

          {filtered.length === 0 ? (

            <div className="empty card">

              <p className="empty-title">

                {activeDate && filter === "ALL"

                  ? fill(t.noTrebleOnDate, { date: formatDay(activeDate, lang) })

                  : t.noTrebles}

              </p>

              {activeDate && filter === "ALL" ? null : (

                <p className="empty-steps">

                  {t.noTreblesBody}

                  {isAdmin ? ` ${t.noTreblesAdmin}` : null}

                </p>

              )}

            </div>

          ) : (

            <>

              {pinned ? (

                <div className="slip-day">

                  <h3 className="slip-day-head">{t.lastSlip}</h3>

                  <SlipCard

                    slip={pinned}

                    featured={pinned.slip_id === topSlipId && pinned.status === "PENDING"}

                    showGuide={pinned.slip_id === topSlipId && pinned.status === "PENDING"}

                    copied={copiedId === pinned.slip_id}

                    loading={loading}

                    onCopy={() => copySlip(pinned)}

                    onTogglePlaced={() =>

                      runAction(async () => {

                        await api.markPlaced(pinned.slip_id, !pinned.placed_on_betpawa);

                      })

                    }

                  />

                </div>

              ) : null}

              {monthRows.length === 0 ? (

                <div className="empty card">

                  <p className="empty-title">{fill(t.noTrebleMonth, { month: formatMonth(viewMonth, lang) })}</p>

                  <p className="empty-steps">

                    {viewMonth > monthBounds.min

                      ? t.noTrebleMonthPrev

                      : viewMonth < monthBounds.max

                        ? t.noTrebleMonthNext

                        : ""}

                  </p>

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

                        showGuide={slip.slip_id === topSlipId && slip.status === "PENDING"}

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

            </>

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


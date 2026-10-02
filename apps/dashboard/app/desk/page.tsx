"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AuthGuard } from "@/components/AuthGuard";
import { FilterChip, StatusBadge, StatusKind } from "@/components/StatusBadge";
import { SiteHeader } from "@/components/SiteHeader";
import { SlipCard } from "@/components/SlipCard";
import { api, Slip } from "@/lib/api";
import { clearToken, markSignedOut } from "@/lib/auth";
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

function DeskPage() {
  const router = useRouter();
  const [slips, setSlips] = useState<Slip[]>([]);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [loading, setLoading] = useState(false);
  const [apiOk, setApiOk] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("ALL");
  const [showAlternatives, setShowAlternatives] = useState(false);
  const [oddsApiReady, setOddsApiReady] = useState(false);
  const [betpawaReady, setBetpawaReady] = useState(true);
  const [showTools, setShowTools] = useState(false);
  const [retentionDays, setRetentionDays] = useState(90);

  const refresh = useCallback(async () => {
    let healthOk = false;
    try {
      const health = await api.health();
      healthOk = health.status === "ok" || health.status === "degraded";
      setApiOk(healthOk);
    } catch {
      setApiOk(false);
      setError("Server offline. Run: .\\scripts\\dev-api.ps1 -Restart");
      return false;
    }

    try {
      const me = await api.me();
      setUserEmail(me.email);
      setIsAdmin(Boolean(me.is_admin));
    } catch (e) {
      if (e instanceof Error && e.message === "Session expired") return false;
      setError(e instanceof Error ? e.message : "Could not load account");
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
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load slips");
      return false;
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setLoading(true);
      try {
        const ready = await refresh();
        if (cancelled || !ready) return;
        const imported = await importBetPawaOnce();
        if (cancelled) return;
        const cleared =
          imported.practice_removed > 0 ? ` Removed ${imported.practice_removed} old practice matches.` : "";
        setInfo(
          `BetPawa updated: ${imported.events_fetched} matches.${cleared} Import BetPawa is still there if you want to refresh again.`
        );
        const retention = await api.retentionDays();
        if (cancelled) return;
        setSlips(await api.listSlips({ days: retention.retention_days }));
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Could not refresh BetPawa. Use More → Import BetPawa.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refresh]);

  useEffect(() => {
    if (!info) return;
    const t = setTimeout(() => setInfo(null), 4000);
    return () => clearTimeout(t);
  }, [info]);

  const filtered = useMemo(() => {
    if (filter === "ALL") return slips;
    if (filter === "PLACED") return slips.filter((s) => s.placed_on_betpawa);
    if (filter === "DAY" || filter === "NIGHT") return slips.filter((s) => s.time_category === filter);
    if (filter === "PENDING" || filter === "WON" || filter === "LOST" || filter === "LIVE") {
      return slips.filter((s) => s.status === filter);
    }
    return slips;
  }, [slips, filter]);

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
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  async function copySlip(slip: Slip) {
    try {
      await navigator.clipboard.writeText(slip.betpawa_copy_text);
      setCopiedId(slip.slip_id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      setError("Copy failed — select text manually or use HTTPS.");
    }
  }

  function logout() {
    clearToken();
    markSignedOut();
    router.replace("/");
  }

  return (
    <>
      {loading ? <div className="loading-bar" aria-hidden /> : null}
      <SiteHeader apiOk={apiOk} email={userEmail} isAdmin={isAdmin} onLogout={logout} />

      <div className="app-shell">
        <section className="page-intro page-intro-stats-only" aria-label="Slip summary">
          <div className="stat-frame frame">
            <div className="stat-pill">
              <StatusBadge kind="PENDING" label={`${stats.pending}`} />
              <span>Pending</span>
            </div>
            <div className="stat-pill">
              <StatusBadge kind="WON" label={`${stats.won}`} />
              <span>Won</span>
            </div>
            <div className="stat-pill">
              <StatusBadge kind="LOST" label={`${stats.lost}`} />
              <span>Lost</span>
            </div>
          </div>
        </section>

        {error ? (
          <p className="banner error" role="alert">
            {error}
          </p>
        ) : null}
        {info ? <p className="banner info">{info}</p> : null}

        <section className="control-panel frame">
          <h2 className="frame-title">Treble actions</h2>
          <div className="toolbar toolbar-main">
            <button
              type="button"
              className="btn primary btn-lg"
              disabled={loading}
              onClick={() =>
                runAction(async () => {
                  const created = await api.generateSlips({
                    maxSlips: showAlternatives ? 3 : 1,
                    replacePending: true,
                  });
                  if (created.length === 0) {
                    throw new Error(
                      betpawaReady || oddsApiReady
                        ? "No treble found. More → Import BetPawa for today's matches, or Practice data to test."
                        : "No treble found. More → Import BetPawa, or use Practice data to test."
                    );
                  }
                  setInfo(showAlternatives ? `${created.length} trebles ready` : "Best treble ready");
                })
              }
            >
              Generate {showAlternatives ? "top 3" : "best treble"}
            </button>

            <div className="filters filters-history">
              {(["ALL", "PENDING", "WON", "LOST", "PLACED", "DAY", "NIGHT"] as Filter[]).map((f) => (
                <FilterChip key={f} kind={f} active={filter === f} onClick={() => setFilter(f)} />
              ))}
            </div>
          </div>

          <div className="toolbar toolbar-secondary">
            <button type="button" className="chip" disabled={loading} onClick={() => setShowAlternatives((v) => !v)}>
              {showAlternatives ? "One treble only" : "Include alternatives"}
            </button>
            <button type="button" className="chip" disabled={loading} onClick={() => refresh()}>
              Refresh
            </button>
            {isAdmin ? (
              <button type="button" className="chip" disabled={loading} onClick={() => setShowTools((v) => !v)}>
                {showTools ? "Hide" : "More"}
              </button>
            ) : null}
          </div>

          {isAdmin && showTools ? (
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
                        r.practice_removed > 0
                          ? ` Removed ${r.practice_removed} old practice matches.`
                          : "";
                      setInfo(
                        `BetPawa: ${r.events_fetched} matches (${r.imported + r.updated} saved).${cleared} Generate a new treble, then check odds on betpawa.co.ke.`
                      );
                    })
                  }
                >
                  Import BetPawa
                </button>
              ) : null}
              <button
                type="button"
                className="btn btn-sm"
                disabled={loading}
                onClick={() =>
                  runAction(async () => {
                    const rows = await api.seedDemo();
                    setInfo(`${rows.length} practice fixtures loaded`);
                  })
                }
              >
                Practice data
              </button>
              {oddsApiReady ? (
                <button
                  type="button"
                  className="btn btn-sm"
                  disabled={loading}
                  onClick={() =>
                    runAction(async () => {
                      const r = await api.importOddsApi();
                      setInfo(`Imported ${r.imported + r.updated} fixtures`);
                    })
                  }
                >
                  Import odds
                </button>
              ) : null}
              <button
                type="button"
                className="btn btn-sm"
                disabled={loading}
                onClick={() =>
                  runAction(async () => {
                    const r = await api.syncStatus();
                    setInfo(r.slips_updated ? `Updated ${r.slips_updated} slip(s)` : "Statuses up to date");
                  })
                }
              >
                Sync scores
              </button>
            </div>
          ) : null}
        </section>

        <section id="slips" className="slip-grid" aria-label={`Slip history, last ${retentionDays} days`}>
          {filtered.length === 0 ? (
            <div className="empty card">
              <p className="empty-title">No trebles yet</p>
              <p className="empty-steps">
                Matches load from BetPawa when you open this page. Tap <strong>Generate best treble</strong>.
                {isAdmin ? (
                  <>
                    {" "}
                    Use <strong>More → Import BetPawa</strong> or the Admin page when you want a fresh list.
                  </>
                ) : null}
              </p>
            </div>
          ) : (
            filtered.map((slip) => (
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
            ))
          )}
        </section>
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

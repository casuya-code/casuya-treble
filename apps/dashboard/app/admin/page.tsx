"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthGuard } from "@/components/AuthGuard";
import { SiteHeader } from "@/components/SiteHeader";
import { useLandingLang } from "@/components/LandingLang";
import { api, AdminOverview, AdminUser } from "@/lib/api";
import { clearToken, markSignedOut } from "@/lib/auth";
import { fill } from "@/lib/landingCopy";
import { slipCreatedLocal } from "@/lib/format";

function AdminPage() {
  const router = useRouter();
  const { t } = useLandingLang();
  const [email, setEmail] = useState<string | null>(null);
  const [allowed, setAllowed] = useState<boolean | null>(null);
  const [apiOk, setApiOk] = useState<boolean | null>(null);
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [oddsReady, setOddsReady] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [section, setSection] = useState<"users" | "overview" | "tools">("users");

  const load = useCallback(async () => {
    try {
      const health = await api.health();
      setApiOk(health.status === "ok" || health.status === "degraded");
    } catch {
      setApiOk(false);
      setError(t.serverOffline);
      return;
    }

    try {
      const me = await api.me();
      setEmail(me.email);
      if (!me.is_admin) {
        setAllowed(false);
        return;
      }
      setAllowed(true);
      const [summary, rows, odds] = await Promise.all([
        api.adminOverview(),
        api.adminUsers(),
        api.oddsProviderStatus().catch(() => null),
      ]);
      setOverview(summary);
      setUsers(rows);
      setOddsReady(Boolean(odds?.configured));
      setError(null);
    } catch (e) {
      if (e instanceof Error && e.message === "Session expired") return;
      setError(e instanceof Error ? e.message : t.couldNotLoadAdmin);
    }
  }, [t.couldNotLoadAdmin, t.serverOffline]);

  useEffect(() => {
    void load();
  }, [load]);

  async function run(action: () => Promise<void>) {
    setLoading(true);
    setError(null);
    try {
      await action();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t.somethingWrong);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      {loading ? <div className="loading-bar" aria-hidden /> : null}
      <SiteHeader
        apiOk={apiOk}
        email={email}
        isAdmin={allowed === true}
        wide
        adminPage
        onLogout={() => {
          clearToken();
          markSignedOut();
          router.replace("/");
        }}
        sections={
          allowed
            ? [
                { id: "users", label: users.length ? `${t.users} (${users.length})` : t.users, active: section === "users", onSelect: () => setSection("users") },
                { id: "overview", label: t.overview, active: section === "overview", onSelect: () => setSection("overview") },
                { id: "tools", label: t.tools, active: section === "tools", onSelect: () => setSection("tools") },
                { id: "desk", label: t.trebleLink, href: "/desk" },
              ]
            : undefined
        }
      />
      <div className="admin-layout">
        <aside className="admin-sidebar" aria-label={t.admin}>
          <p className="admin-side-label">{t.admin}</p>
          <nav className="admin-nav">
            <button type="button" className={section === "users" ? "active" : ""} onClick={() => setSection("users")}>
              {t.users}
              {users.length ? ` (${users.length})` : ""}
            </button>
            <button
              type="button"
              className={section === "overview" ? "active" : ""}
              onClick={() => setSection("overview")}
            >
              {t.overview}
            </button>
            <button type="button" className={section === "tools" ? "active" : ""} onClick={() => setSection("tools")}>
              {t.tools}
            </button>
            <Link href="/desk">{t.trebleLink}</Link>
          </nav>
        </aside>
        <div className="admin-main">
          {error ? (
            <p className="banner error" role="alert">
              {error}
            </p>
          ) : null}
          {info ? <p className="banner info">{info}</p> : null}

          {allowed === false ? (
            <section>
              <h2>{t.adminOnly}</h2>
              <p>{fill(t.adminDenied, { email: email ?? "" })}</p>
            </section>
          ) : null}

          {allowed && section === "users" ? (
            <section id="accounts">
              <h2>{t.users}</h2>
              <p className="admin-lead">{fill(t.accountsLead, { n: users.length })}</p>
              <ul className="admin-users">
                {users.map((user) => (
                  <li key={user.id} className="admin-user">
                    <div className="admin-user-meta">
                      <strong>{user.email}</strong>
                      <span className="leg-sub">
                        {user.is_admin ? t.admin : t.userRole} · {user.is_active ? t.active : t.disabled}
                      </span>
                      <span className="leg-sub">
                        {fill(t.slipCount, { n: user.slip_count })} · {t.joined} {slipCreatedLocal(user.created_at)}
                      </span>
                    </div>
                    {user.email === email ? (
                      <span className="leg-sub">{t.thisAccount}</span>
                    ) : (
                      <button
                        type="button"
                        className="btn btn-sm"
                        disabled={loading}
                        onClick={() =>
                          run(async () => {
                            await api.setUserActive(user.id, !user.is_active);
                            setInfo(user.is_active ? fill(t.disabledUser, { email: user.email }) : fill(t.enabledUser, { email: user.email }));
                          })
                        }
                      >
                        {user.is_active ? t.disable : t.enable}
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {allowed && overview && section === "overview" ? (
            <section>
              <h2>{t.overview}</h2>
              <p className="admin-lead">{t.overviewLead}</p>
              <div className="stat-frame frame">
                <div className="stat-pill">
                  <strong>{overview.users}</strong>
                  <span>{t.users}</span>
                </div>
                <div className="stat-pill">
                  <strong>{overview.active_users}</strong>
                  <span>{t.active}</span>
                </div>
                <div className="stat-pill">
                  <strong>{overview.fixtures}</strong>
                  <span>{t.matches}</span>
                </div>
                <div className="stat-pill">
                  <strong>{overview.slips}</strong>
                  <span>{t.slipsWord}</span>
                </div>
              </div>
            </section>
          ) : null}

          {allowed && section === "tools" ? (
            <section>
              <h2>{t.tools}</h2>
              <p className="admin-lead">{t.toolsLead}</p>
              <div className="tools-row">
                <button
                  type="button"
                  className="btn btn-sm primary"
                  disabled={loading}
                  onClick={() =>
                    run(async () => {
                      const r = await api.importBetPawa();
                      setInfo(fill(t.importSaved, { n: r.imported + r.updated }));
                    })
                  }
                >
                  {t.importBetPawa}
                </button>
                <button
                  type="button"
                  className="btn btn-sm"
                  disabled={loading}
                  onClick={() =>
                    run(async () => {
                      const rows = await api.seedDemo();
                      setInfo(fill(t.practiceLoaded, { n: rows.length }));
                    })
                  }
                >
                  {t.practiceData}
                </button>
                {oddsReady ? (
                  <button
                    type="button"
                    className="btn btn-sm"
                    disabled={loading}
                    onClick={() =>
                      run(async () => {
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
                    run(async () => {
                      const r = await api.syncStatus();
                      setInfo(r.slips_updated ? fill(t.slipsUpdated, { n: r.slips_updated }) : t.statusesOk);
                    })
                  }
                >
                  {t.syncScores}
                </button>
              </div>
            </section>
          ) : null}
        </div>
      </div>
    </>
  );
}

export default function AdminRoute() {
  return (
    <AuthGuard>
      <AdminPage />
    </AuthGuard>
  );
}

"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthGuard } from "@/components/AuthGuard";
import { SiteHeader } from "@/components/SiteHeader";
import { api, AdminOverview, AdminUser } from "@/lib/api";
import { clearToken, markSignedOut } from "@/lib/auth";
import { slipCreatedLocal } from "@/lib/format";

function AdminPage() {
  const router = useRouter();
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
      setError("Server offline. Run: .\\scripts\\dev-api.ps1 -Restart");
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
      setError(e instanceof Error ? e.message : "Could not load admin");
    }
  }, []);

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
      setError(e instanceof Error ? e.message : "Something went wrong");
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
      />
      <div className="admin-layout">
        <aside className="admin-sidebar" aria-label="Admin">
          <p className="admin-side-label">Admin</p>
          <nav className="admin-nav">
            <button type="button" className={section === "users" ? "active" : ""} onClick={() => setSection("users")}>
              Users{users.length ? ` (${users.length})` : ""}
            </button>
            <button
              type="button"
              className={section === "overview" ? "active" : ""}
              onClick={() => setSection("overview")}
            >
              Overview
            </button>
            <button type="button" className={section === "tools" ? "active" : ""} onClick={() => setSection("tools")}>
              Tools
            </button>
            <Link href="/desk">Treble</Link>
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
              <h2>Admin only</h2>
              <p>
                Signed in as <strong>{email}</strong>. This login cannot list accounts. Sign in as{" "}
                <strong>admin@casuyawin.com</strong>.
              </p>
            </section>
          ) : null}

          {allowed && section === "users" ? (
            <section id="accounts">
              <h2>Users</h2>
              <p className="admin-lead">
                {users.length} accounts. Disable a user to stop them signing in.
              </p>
              <ul className="admin-users">
                {users.map((user) => (
                  <li key={user.id} className="admin-user">
                    <div className="admin-user-meta">
                      <strong>{user.email}</strong>
                      <span className="leg-sub">
                        {user.is_admin ? "Admin" : "User"} · {user.is_active ? "Active" : "Disabled"}
                      </span>
                      <span className="leg-sub">
                        {user.slip_count} slips · joined {slipCreatedLocal(user.created_at)}
                      </span>
                    </div>
                    {user.email === email ? (
                      <span className="leg-sub">This account</span>
                    ) : (
                      <button
                        type="button"
                        className="btn btn-sm"
                        disabled={loading}
                        onClick={() =>
                          run(async () => {
                            await api.setUserActive(user.id, !user.is_active);
                            setInfo(user.is_active ? `Disabled ${user.email}` : `Enabled ${user.email}`);
                          })
                        }
                      >
                        {user.is_active ? "Disable" : "Enable"}
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {allowed && overview && section === "overview" ? (
            <section>
              <h2>Overview</h2>
              <p className="admin-lead">Counts for the whole desk.</p>
              <div className="stat-frame frame">
                <div className="stat-pill">
                  <strong>{overview.users}</strong>
                  <span>Users</span>
                </div>
                <div className="stat-pill">
                  <strong>{overview.active_users}</strong>
                  <span>Active</span>
                </div>
                <div className="stat-pill">
                  <strong>{overview.fixtures}</strong>
                  <span>Matches</span>
                </div>
                <div className="stat-pill">
                  <strong>{overview.slips}</strong>
                  <span>Slips</span>
                </div>
              </div>
            </section>
          ) : null}

          {allowed && section === "tools" ? (
            <section>
              <h2>Tools</h2>
              <p className="admin-lead">Import matches, load practice data, and sync scores.</p>
              <div className="tools-row">
                <button
                  type="button"
                  className="btn btn-sm primary"
                  disabled={loading}
                  onClick={() =>
                    run(async () => {
                      const r = await api.importBetPawa();
                      setInfo(`BetPawa: ${r.events_fetched} matches saved.`);
                    })
                  }
                >
                  Import BetPawa
                </button>
                <button
                  type="button"
                  className="btn btn-sm"
                  disabled={loading}
                  onClick={() =>
                    run(async () => {
                      const rows = await api.seedDemo();
                      setInfo(`${rows.length} practice fixtures loaded`);
                    })
                  }
                >
                  Practice data
                </button>
                {oddsReady ? (
                  <button
                    type="button"
                    className="btn btn-sm"
                    disabled={loading}
                    onClick={() =>
                      run(async () => {
                        const r = await api.importOddsApi();
                        setInfo(`Imported ${r.imported + r.updated} odds fixtures`);
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
                    run(async () => {
                      const r = await api.syncStatus();
                      setInfo(r.slips_updated ? `Updated ${r.slips_updated} slip(s)` : "Statuses up to date");
                    })
                  }
                >
                  Sync scores
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

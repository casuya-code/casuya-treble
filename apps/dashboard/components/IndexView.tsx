"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PublicHistoryPanel } from "@/components/PublicHistoryPanel";
import { LangSwitch, MenuButton, useLandingLang } from "@/components/LandingLang";
import { api, VisitTotals } from "@/lib/api";
import { isLoggedIn, takeSignedOutNotice } from "@/lib/auth";

const EXAMPLE = [
  { odds: 1.45 },
  { odds: 1.52 },
  { odds: 1.4 },
];

function ExampleSlip() {
  const { t } = useLandingLang();
  const legs = EXAMPLE.map((leg, index) => ({
    name: `${t.leg} ${index + 1}`,
    odds: leg.odds,
  }));
  const total = legs.reduce((product, leg) => product * leg.odds, 1);

  return (
    <div className="slip" id="hero-slip">
      <span className="slip-tag">{t.ex}</span>
      {legs.map((leg) => (
        <div className="leg" key={leg.name}>
          <div>
            <b>{leg.name}</b>
            <small>{t.o15}</small>
          </div>
          <span className="odd">{leg.odds.toFixed(2)}</span>
        </div>
      ))}
      <div className="tear" />
      <p className="calc">{legs.map((leg) => leg.odds.toFixed(2)).join(" × ")}</p>
      <div className="total">{total.toFixed(2)}</div>
      <div className="small">{t.combined}</div>
      <p className="small" style={{ marginTop: 14 }}>
        {t.exn}
      </p>
    </div>
  );
}

function visitorId(): string {
  const key = "ct-visitor";
  const saved = localStorage.getItem(key);
  if (saved) return saved;
  const created = crypto.randomUUID();
  localStorage.setItem(key, created);
  return created;
}

function VisitLine() {
  const { t } = useLandingLang();
  const [counts, setCounts] = useState<VisitTotals | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .recordVisit(visitorId())
      .then((totals) => {
        if (!cancelled) setCounts(totals);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  const show = (value: number | undefined) => (value == null ? "–" : String(value));

  return (
    <p className="visit-line">
      {`${t.visitToday}=${show(counts?.today)} | ${t.visitYesterday}=${show(counts?.yesterday)} | ${t.visitWeek}=${show(counts?.week)} | ${t.visitYear}=${show(counts?.year)}`}
    </p>
  );
}

function LandingPage() {
  const { t } = useLandingLang();
  const [loggedIn, setLoggedIn] = useState(false);
  const [signedOut, setSignedOut] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    setLoggedIn(isLoggedIn());
    setSignedOut(takeSignedOutNotice());
  }, []);

  const primary = loggedIn
    ? { href: "/desk", label: t.open }
    : signedOut
      ? { href: "/login", label: t.open }
      : { href: "/register", label: t.open };

  const quiet = loggedIn ? null : signedOut ? { href: "/register", label: t.create } : { href: "/login", label: t.signIn };

  return (
    <div className="landing">
      <header className="landing-wrap landing-top">
        <Link href="/" className="landing-brand">
          Casuya <span className="pos">Treble</span>
        </Link>
        <MenuButton open={menuOpen} label={t.menu} onToggle={() => setMenuOpen((value) => !value)} />
        <div className={`header-panel ${menuOpen ? "open" : ""}`}>
          <LangSwitch />
          <Link className="ct-btn" href={primary.href} onClick={() => setMenuOpen(false)}>
            {primary.label}
          </Link>
          {quiet ? (
            <Link className="landing-quiet" href={quiet.href} onClick={() => setMenuOpen(false)}>
              {quiet.label}
            </Link>
          ) : null}
        </div>
      </header>

      <main>
        <section className="landing-wrap landing-hero">
          <div>
            <h1>{t.h1}</h1>
            <p className="lead">{t.lead}</p>
            {signedOut ? <p className="note landing-note">{t.signedOut}</p> : null}
            <Link className="ct-btn" href={primary.href}>
              {primary.label}
            </Link>
            {quiet ? (
              <div>
                <Link className="landing-quiet" href={quiet.href}>
                  {quiet.label}
                </Link>
              </div>
            ) : null}
          </div>
          <ExampleSlip />
        </section>

        <section className="landing-wrap">
          <h2>{t.howT}</h2>
          <div className="steps">
            <div className="step">
              <span className="n">1</span>
              <h3>{t.s1t}</h3>
              <p>{t.s1p}</p>
            </div>
            <div className="step">
              <span className="n">2</span>
              <h3>{t.s2t}</h3>
              <p>{t.s2p}</p>
            </div>
            <div className="step">
              <span className="n">3</span>
              <h3>{t.s3t}</h3>
              <p>{t.s3p}</p>
            </div>
          </div>
        </section>

        <PublicHistoryPanel />

        <section className="landing-wrap">
          <h2>{t.trustT}</h2>
          <div className="trust">
            <div>
              <b>{t.t1t}</b>
              <span>{t.t1p}</span>
            </div>
            <div>
              <b>{t.t2t}</b>
              <span>{t.t2p}</span>
            </div>
            <div>
              <b>{t.t3t}</b>
              <span>{t.t3p}</span>
            </div>
          </div>
        </section>

        <section className="landing-wrap">
          <div className="cta">
            <h2>{signedOut ? t.ctaSignedOut : t.ctaT}</h2>
            <p>{signedOut ? t.ctaSignedOutP : t.ctaP}</p>
            <Link className="ct-btn" href={primary.href}>
              {primary.label}
            </Link>
          </div>
        </section>
      </main>

      <footer className="landing-footer">
        <div className="landing-wrap">
          <VisitLine />
          <p>
            <strong>{t.f1}</strong> {t.f2}
          </p>
        </div>
      </footer>

      <div className="landing-sticky">
        <Link className="ct-btn" href={primary.href}>
          {primary.label}
        </Link>
      </div>
    </div>
  );
}

export function IndexView() {
  return <LandingPage />;
}

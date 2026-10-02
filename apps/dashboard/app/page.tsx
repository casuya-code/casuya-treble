"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { TrebleSchematic } from "@/components/TrebleSchematic";
import { PublicHistoryPanel } from "@/components/PublicHistoryPanel";
import { isLoggedIn, takeSignedOutNotice } from "@/lib/auth";

const steps = [
  {
    tone: "blue",
    title: "See today’s list",
    body: "Open Casuya Treble and the football matches arrive from BetPawa, with Over 1.5 prices.",
  },
  {
    tone: "green",
    title: "Let the model sort them",
    body: "A Poisson score model keeps three legs only when their prices multiply to 3.00 or more.",
  },
  {
    tone: "amber",
    title: "Place it yourself",
    body: "Copy the slip, check the live price on betpawa.co.ke, then stake it by hand.",
  },
] as const;

function StepIcon({ tone }: { tone: (typeof steps)[number]["tone"] }) {
  if (tone === "blue") {
    return (
      <svg viewBox="0 0 48 48" aria-hidden="true">
        <rect x="8" y="10" width="32" height="28" rx="6" fill="none" stroke="currentColor" strokeWidth="2" />
        <path d="M16 20h16M16 26h16M16 32h10" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
    );
  }
  if (tone === "green") {
    return (
      <svg viewBox="0 0 48 48" aria-hidden="true">
        <path d="M8 36c6-18 10-22 16-22s8 10 16 4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path d="M8 38h32" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true">
      <rect x="14" y="8" width="20" height="26" rx="3" fill="none" stroke="currentColor" strokeWidth="2" />
      <path d="M18 16h12M18 22h12M18 28h8" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <path d="M10 34l6 6 14-14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function IndexPage() {
  const [loggedIn, setLoggedIn] = useState(false);
  const [signedOut, setSignedOut] = useState(false);

  useEffect(() => {
    setLoggedIn(isLoggedIn());
    setSignedOut(takeSignedOutNotice());
  }, []);

  const primary = loggedIn
    ? { href: "/desk", label: "Open trebles" }
    : signedOut
      ? { href: "/login", label: "Sign in" }
      : { href: "/register", label: "Create account" };

  const secondary = loggedIn
    ? null
    : signedOut
      ? { href: "/register", label: "Create account" }
      : { href: "/login", label: "Sign in" };

  return (
    <div className="index-page">
      <header className="index-header">
        <div className="index-header-inner">
          <Link href="/" className="brand">
            <span className="brand-mark">C</span>
            <span className="brand-text">
              Casuya <strong className="brand-long">Treble</strong>
            </span>
          </Link>
          <nav className="index-nav" aria-label="Account">
            {secondary ? (
              <Link href={secondary.href} className="btn btn-sm">
                {secondary.label}
              </Link>
            ) : null}
            <Link href={primary.href} className="btn btn-sm primary">
              {primary.label}
            </Link>
          </nav>
        </div>
      </header>

      {signedOut ? (
        <p className="index-out" role="status">
          Signed out. Your slips stay on the account. Sign in when you want them again.
        </p>
      ) : null}

      <section className="index-hero">
        <div className="index-copy">
          <p className="index-kicker">Over 1.5 football trebles</p>
          <h1>Three legs. One slip. You place it.</h1>
          <p className="index-lead">
            Casuya reads today’s BetPawa football list, scores the matches, and shows a treble only when the
            combined price is at least 3.00.
          </p>
          <div className="index-actions">
            <Link href={primary.href} className="btn primary btn-lg">
              {primary.label}
            </Link>
            {secondary ? (
              <Link href={secondary.href} className="btn btn-lg">
                {secondary.label}
              </Link>
            ) : null}
          </div>
        </div>
        <TrebleSchematic />
      </section>

      <section className="index-steps" aria-label="How a visit works">
        <h2 className="index-section-title">How a visit works</h2>
        <div className="index-step-grid">
          {steps.map((step, index) => (
            <article key={step.title} className={`index-step tone-${step.tone}`}>
              <div className="index-step-icon">
                <StepIcon tone={step.tone} />
              </div>
              <p className="index-step-num">0{index + 1}</p>
              <h3>{step.title}</h3>
              <p>{step.body}</p>
            </article>
          ))}
        </div>
      </section>

      <PublicHistoryPanel />

      <section className="index-rules" aria-label="What you can count on">
        <h2 className="index-section-title">What you can count on</h2>
        <ul>
          <li>
            <strong>90 days</strong>
            <span>Slips stay on your account.</span>
          </li>
          <li>
            <strong>Labeled practice</strong>
            <span>Practice matches leave once real fixtures are loaded.</span>
          </li>
          <li>
            <strong>Live price</strong>
            <span>Check betpawa.co.ke before you stake. Casuya Treble does not send the bet.</span>
          </li>
        </ul>
      </section>

      <section className="index-close">
        <h2>{loggedIn ? "Today’s list is ready." : signedOut ? "Your account is still here." : "Start with today’s list."}</h2>
        <Link href={primary.href} className="btn primary btn-lg">
          {primary.label}
        </Link>
      </section>
    </div>
  );
}

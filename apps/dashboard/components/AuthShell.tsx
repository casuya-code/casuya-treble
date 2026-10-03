"use client";

import Link from "next/link";
import { ReactNode } from "react";
import { LangSwitch, useLandingLang } from "@/components/LandingLang";

type Props = {
  title: string;
  subtitle: string;
  children: ReactNode;
  footer: ReactNode;
};

export function AuthShell({ title, subtitle, children, footer }: Props) {
  const { t } = useLandingLang();
  return (
    <div className="auth-page">
      <div className="auth-card frame">
        <div className="auth-tools">
          <Link href="/" className="brand auth-brand">
            <span className="brand-mark">C</span>
            <span className="brand-text">
              Casuya <strong className="brand-long">Treble</strong>
            </span>
          </Link>
          <LangSwitch />
        </div>
        <h1>{title}</h1>
        <p className="auth-sub">{subtitle}</p>
        {children}
        <div className="auth-footer">{footer}</div>
        <Link href="/" className="btn auth-home">
          {t.home}
        </Link>
      </div>
    </div>
  );
}

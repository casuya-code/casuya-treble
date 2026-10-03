"use client";

import Link from "next/link";
import { useState } from "react";
import { LangSwitch, MenuButton, useLandingLang } from "@/components/LandingLang";

export type HeaderSection = {
  id: string;
  label: string;
  active?: boolean;
  href?: string;
  onSelect?: () => void;
};

type Props = {
  apiOk: boolean | null;
  email?: string | null;
  isAdmin?: boolean;
  wide?: boolean;
  adminPage?: boolean;
  onLogout?: () => void;
  sections?: HeaderSection[];
};

export function SiteHeader({ apiOk, email, isAdmin, wide, adminPage, onLogout, sections }: Props) {
  const { t } = useLandingLang();
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);

  return (
    <header className={`site-header ${wide ? "site-header-wide" : ""} ${adminPage ? "admin-topbar" : ""}`}>
      {open ? <button type="button" className="menu-backdrop" aria-label={t.menu} onClick={close} /> : null}
      <div className="site-header-inner">
        <Link href="/" className="brand" onClick={close}>
          <span className="brand-mark">C</span>
          <span className="brand-text">
            Casuya <strong className="brand-long">Treble</strong>
          </span>
        </Link>
        <MenuButton open={open} label={t.menu} onToggle={() => setOpen((value) => !value)} />
        <div className={`header-panel ${open ? "open" : ""}`} id="app-menu">
          {sections && sections.length > 0 ? (
            <nav className="menu-sections" aria-label={t.admin}>
              {sections.map((item) =>
                item.href ? (
                  <Link key={item.id} href={item.href} className={item.active ? "active" : ""} onClick={close}>
                    {item.label}
                  </Link>
                ) : (
                  <button
                    key={item.id}
                    type="button"
                    className={item.active ? "active" : ""}
                    aria-current={item.active ? "page" : undefined}
                    onClick={() => {
                      item.onSelect?.();
                      close();
                    }}
                  >
                    {item.label}
                  </button>
                ),
              )}
            </nav>
          ) : null}
          <LangSwitch />
          {isAdmin && !adminPage ? (
            <Link href="/admin" className="chip admin-link" onClick={close}>
              {t.admin}
            </Link>
          ) : null}
          {email ? <span className="user-email">{email}</span> : null}
          {onLogout ? (
            <button type="button" className="btn btn-sm chip" onClick={onLogout}>
              {t.logOut}
            </button>
          ) : null}
          <span className={`status-chip ${apiOk === true ? "ok" : apiOk === false ? "bad" : ""}`}>
            {apiOk === true ? t.connected : apiOk === false ? t.offline : "…"}
          </span>
        </div>
      </div>
    </header>
  );
}

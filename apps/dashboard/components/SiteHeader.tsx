"use client";

import Link from "next/link";

type Props = {
  apiOk: boolean | null;
  email?: string | null;
  isAdmin?: boolean;
  wide?: boolean;
  adminPage?: boolean;
  onLogout?: () => void;
};

export function SiteHeader({ apiOk, email, isAdmin, wide, adminPage, onLogout }: Props) {
  return (
    <header className={`site-header ${wide ? "site-header-wide" : ""} ${adminPage ? "admin-topbar" : ""}`}>
      <div className="site-header-inner">
        <Link href="/" className="brand">
          <span className="brand-mark">C</span>
          <span className="brand-text">
            Casuya <strong className="brand-long">Treble</strong>
          </span>
        </Link>
        <div className="header-right">
          {isAdmin && !adminPage ? (
            <Link href="/admin" className="chip admin-link">
              Admin
            </Link>
          ) : null}
          {email ? <span className="user-email">{email}</span> : null}
          {onLogout ? (
            <button type="button" className="btn btn-sm chip" onClick={onLogout}>
              Log out
            </button>
          ) : null}
          <span className={`status-chip ${apiOk === true ? "ok" : apiOk === false ? "bad" : ""}`}>
            {apiOk === true ? "Connected" : apiOk === false ? "Offline" : "…"}
          </span>
        </div>
      </div>
    </header>
  );
}

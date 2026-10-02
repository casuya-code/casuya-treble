import Link from "next/link";
import { ReactNode } from "react";

type Props = {
  title: string;
  subtitle: string;
  children: ReactNode;
  footer: ReactNode;
};

export function AuthShell({ title, subtitle, children, footer }: Props) {
  return (
    <div className="auth-page">
      <div className="auth-card frame">
        <Link href="/" className="brand auth-brand">
          <span className="brand-mark">C</span>
          <span className="brand-text">
            Casuya <strong className="brand-long">Treble</strong>
          </span>
        </Link>
        <h1>{title}</h1>
        <p className="auth-sub">{subtitle}</p>
        {children}
        <div className="auth-footer">{footer}</div>
      </div>
    </div>
  );
}

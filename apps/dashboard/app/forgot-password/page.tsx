"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { AuthShell } from "@/components/AuthShell";
import { useLandingLang } from "@/components/LandingLang";
import { api } from "@/lib/api";

export default function ForgotPasswordPage() {
  const { t } = useLandingLang();
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [resetLink, setResetLink] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setMessage(null);
    setResetLink(null);
    try {
      const res = await api.forgotPassword(email);
      setMessage(res.message);
      if (res.reset_link) setResetLink(res.reset_link);
    } catch (err) {
      setError(err instanceof Error ? err.message : t.requestFailed);
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      title={t.forgotTitle}
      subtitle={t.forgotSub}
      footer={
        <>
          <Link href="/login">{t.backLogin}</Link>
        </>
      }
    >
      <form className="auth-form" onSubmit={onSubmit}>
        {error ? <p className="banner error">{error}</p> : null}
        {message ? <p className="banner info">{message}</p> : null}
        {resetLink ? (
          <p className="reset-link-box">
            {t.resetDev}:{" "}
            <a href={resetLink}>{resetLink}</a>
          </p>
        ) : null}
        <label>
          {t.email}
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <button type="submit" className="btn primary btn-block" disabled={loading}>
          {loading ? t.sending : t.sendReset}
        </button>
      </form>
    </AuthShell>
  );
}

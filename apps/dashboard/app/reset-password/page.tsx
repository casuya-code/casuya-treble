"use client";

import Link from "next/link";
import { FormEvent, Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AuthShell } from "@/components/AuthShell";
import { useLandingLang } from "@/components/LandingLang";
import { api } from "@/lib/api";

function ResetForm() {
  const router = useRouter();
  const { t } = useLandingLang();
  const params = useSearchParams();
  const tokenFromUrl = params.get("token") ?? "";

  const [token, setToken] = useState(tokenFromUrl);
  // URL changed (e.g. a new reset link) — adjust during render, not in an effect.
  const [seenToken, setSeenToken] = useState(tokenFromUrl);
  if (tokenFromUrl !== seenToken) {
    setSeenToken(tokenFromUrl);
    if (tokenFromUrl) setToken(tokenFromUrl);
  }
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const redirectTimer = useRef<number | null>(null);

  useEffect(
    () => () => {
      if (redirectTimer.current !== null) window.clearTimeout(redirectTimer.current);
    },
    [],
  );

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      setError(t.passwordsMismatch);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await api.resetPassword(token, password);
      setMessage(res.message);
      redirectTimer.current = window.setTimeout(() => router.replace("/login"), 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : t.resetFailed);
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      title={t.resetTitle}
      subtitle={t.resetSub}
      footer={
        <>
          <Link href="/login">{t.logIn}</Link>
        </>
      }
    >
      <form className="auth-form" onSubmit={onSubmit}>
        {error ? <p className="banner error">{error}</p> : null}
        {message ? <p className="banner info">{message}</p> : null}
        <label>
          {t.resetToken}
          <input type="text" required value={token} onChange={(e) => setToken(e.target.value)} />
        </label>
        <label>
          {t.newPassword}
          <input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        <label>
          {t.confirmPassword}
          <input
            type="password"
            required
            minLength={8}
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
          />
        </label>
        <button type="submit" className="btn primary btn-block" disabled={loading}>
          {loading ? t.saving : t.savePassword}
        </button>
      </form>
    </AuthShell>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div className="auth-page">Loading…</div>}>
      <ResetForm />
    </Suspense>
  );
}

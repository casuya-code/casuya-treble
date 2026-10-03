"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthShell } from "@/components/AuthShell";
import { useLandingLang } from "@/components/LandingLang";
import { api } from "@/lib/api";
import { setToken } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const { t } = useLandingLang();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await api.login(email, password);
      setToken(res.access_token);
      router.replace("/desk");
    } catch (err) {
      setError(err instanceof Error ? err.message : t.loginFailed);
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      title={t.loginTitle}
      subtitle={t.loginSub}
      footer={
        <>
          <Link href="/register">{t.create}</Link>
          <span> · </span>
          <Link href="/forgot-password">{t.forgot}</Link>
        </>
      }
    >
      <form className="auth-form" onSubmit={onSubmit}>
        {error ? <p className="banner error">{error}</p> : null}
        <label>
          {t.email}
          <input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          {t.password}
          <input
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        <button type="submit" className="btn primary btn-block" disabled={loading}>
          {loading ? t.signingIn : t.logIn}
        </button>
      </form>
    </AuthShell>
  );
}

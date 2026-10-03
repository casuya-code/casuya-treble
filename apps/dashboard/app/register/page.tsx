"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthShell } from "@/components/AuthShell";
import { useLandingLang } from "@/components/LandingLang";
import { api } from "@/lib/api";
import { setToken } from "@/lib/auth";

export default function RegisterPage() {
  const router = useRouter();
  const { t } = useLandingLang();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      setError(t.passwordsMismatch);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await api.register(email, password);
      setToken(res.access_token);
      router.replace("/desk");
    } catch (err) {
      setError(err instanceof Error ? err.message : t.registerFailed);
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      title={t.createTitle}
      subtitle={t.createSub}
      footer={
        <>
          {t.alreadyHave} <Link href="/login">{t.logIn}</Link>
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
          {t.passwordHint}
          <input
            type="password"
            required
            minLength={8}
            autoComplete="new-password"
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
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
          />
        </label>
        <button type="submit" className="btn primary btn-block" disabled={loading}>
          {loading ? t.creating : t.create}
        </button>
      </form>
    </AuthShell>
  );
}

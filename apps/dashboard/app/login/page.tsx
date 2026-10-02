"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthShell } from "@/components/AuthShell";
import { api } from "@/lib/api";
import { setToken } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
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
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      title="Log in"
      subtitle="Access your trebles and BetPawa tracking."
      footer={
        <>
          <Link href="/register">Create account</Link>
          <span> · </span>
          <Link href="/forgot-password">Forgot password?</Link>
        </>
      }
    >
      <form className="auth-form" onSubmit={onSubmit}>
        {error ? <p className="banner error">{error}</p> : null}
        <label>
          Email
          <input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          Password
          <input
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        <button type="submit" className="btn primary btn-block" disabled={loading}>
          {loading ? "Signing in…" : "Log in"}
        </button>
      </form>
    </AuthShell>
  );
}

"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const response = await fetch(API + "/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email, password }),
      });
      if (!response.ok) throw new Error((await response.json()).detail ?? "Login failed");
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return <main className="auth-shell"><form className="auth-card" onSubmit={submit}>
    <p className="eyebrow">NEXUS-Ω</p><h1>Welcome back</h1><p className="muted">Sign in to your workspace.</p>
    <label>Email<input type="email" value={email} onChange={e => setEmail(e.target.value)} required /></label>
    <label>Password<input type="password" value={password} onChange={e => setPassword(e.target.value)} required /></label>
    {error && <p className="error">{error}</p>}
    <button disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
    <a href="/register">Create an account</a>
  </form></main>;
}

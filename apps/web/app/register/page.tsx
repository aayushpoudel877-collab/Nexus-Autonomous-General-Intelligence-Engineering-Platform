"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export default function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({ full_name: "", email: "", password: "", organization_name: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError("");
    try {
      const response = await fetch(API + "/auth/register", {
        method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include",
        body: JSON.stringify(form),
      });
      if (!response.ok) throw new Error((await response.json()).detail ?? "Registration failed");
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally { setBusy(false); }
  }

  const update = (key: keyof typeof form, value: string) => setForm({ ...form, [key]: value });
  return <main className="auth-shell"><form className="auth-card" onSubmit={submit}>
    <p className="eyebrow">NEXUS-Ω</p><h1>Create workspace</h1><p className="muted">Start your AI engineering and learning workspace.</p>
    <label>Full name<input value={form.full_name} onChange={e => update("full_name", e.target.value)} required /></label>
    <label>Email<input type="email" value={form.email} onChange={e => update("email", e.target.value)} required /></label>
    <label>Organization<input value={form.organization_name} onChange={e => update("organization_name", e.target.value)} required /></label>
    <label>Password<input type="password" minLength={12} value={form.password} onChange={e => update("password", e.target.value)} required /></label>
    {error && <p className="error">{error}</p>}<button disabled={busy}>{busy ? "Creating…" : "Create account"}</button>
    <a href="/login">Already have an account?</a>
  </form></main>;
}

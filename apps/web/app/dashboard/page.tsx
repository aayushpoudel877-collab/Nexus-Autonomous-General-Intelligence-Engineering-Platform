"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

type Me = { user: { full_name: string; email: string }; organization_id: string; role: string };

export default function DashboardPage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  useEffect(() => {
    fetch(API + "/auth/me", { credentials: "include" })
      .then(async response => {
        if (!response.ok) throw new Error("unauthorized");
        return response.json();
      })
      .then(setMe).catch(() => router.replace("/login"));
  }, [router]);

  async function logout() {
    await fetch(API + "/auth/logout", { method: "POST", credentials: "include" });
    router.replace("/login");
  }

  if (!me) return <main className="shell"><p className="muted">Loading workspace…</p></main>;
  return <main className="shell"><div className="dashboard-top"><div><p className="eyebrow">NEXUS-Ω CONTROL PLANE</p><h1>Good to see you, {me.user.full_name}.</h1><p className="lead">{me.user.email} · {me.role}</p></div><button className="secondary" onClick={logout}>Sign out</button></div>
    <section className="grid dashboard-grid">
      <article><span className="status-dot" /><h2>Identity</h2><p>Your account and organization membership are active.</p></article>
      <article><span className="status-dot" /><h2>LMS</h2><p>Course, lesson and assessment infrastructure is the next domain layer.</p></article>
      <article><span className="status-dot" /><h2>AI Engineering</h2><p>Projects, experiments and autonomous workflows will connect here.</p></article>
    </section>
  </main>;
}

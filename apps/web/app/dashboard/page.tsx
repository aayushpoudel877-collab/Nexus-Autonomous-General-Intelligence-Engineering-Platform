"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

type Organization = { id: string; name: string; slug: string; role_id: string };
type Me = { user: { full_name: string; email: string }; organization_id: string; role: string };

async function request(path: string, init?: RequestInit) {
  const response = await fetch(API + path, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw Object.assign(new Error(body.detail ?? ("Request failed (" + response.status + ")")), { status: response.status });
  return body;
}

export default function DashboardPage() {
  const router = useRouter();
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState("");
  const [switching, setSwitching] = useState(false);

  useEffect(() => {
    void (async () => {
      try {
        const orgs = await request("/auth/organizations") as Organization[];
        setOrganizations(orgs);
        try {
          setMe(await request("/auth/me") as Me);
        } catch (e) {
          if (e instanceof Error && "status" in e && (e as Error & { status?: number }).status === 409) {
            return;
          }
          throw e;
        }
        if (orgs.length === 0) router.replace("/login");
      } catch {
        router.replace("/login");
      }
    })();
  }, [router]);

  async function switchOrganization(id: string) {
    setSwitching(true); setError("");
    try {
      setMe(await request("/auth/select-organization/" + id, { method: "POST" }) as Me);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not select organization.");
    } finally {
      setSwitching(false);
    }
  }

  async function logout() {
    await fetch(API + "/auth/logout", { method: "POST", credentials: "include" });
    router.replace("/login");
  }

  if (!organizations.length) return <main className="shell"><p className="muted">Loading workspace…</p></main>;
  if (!me) return <main className="shell"><section className="auth-card"><p className="eyebrow">NEXUS-Ω ORGANIZATIONS</p><h1>Select a workspace</h1><p className="muted">This account has access to more than one organization. Choose the workspace for this session.</p><label>Organization<select onChange={e => void switchOrganization(e.target.value)} defaultValue=""><option value="" disabled>Select an organization</option>{organizations.map(org => <option key={org.id} value={org.id}>{org.name}</option>)}</select></label>{error && <p className="error">{error}</p>}</section></main>;

  return <main className="shell">
    <div className="dashboard-top">
      <div><p className="eyebrow">NEXUS-Ω CONTROL PLANE</p><h1>Good to see you, {me.user.full_name}.</h1><p className="lead">{me.user.email} · {me.role} · {organizations.find(org => org.id === me.organization_id)?.name}</p></div>
      <button className="secondary" onClick={logout}>Sign out</button>
    </div>
    {organizations.length > 1 && <section style={{ margin: "18px 0" }}><label>Workspace<select value={me.organization_id} disabled={switching} onChange={e => void switchOrganization(e.target.value)}>{organizations.map(org => <option key={org.id} value={org.id}>{org.name}</option>)}</select></label></section>}
    <section className="grid dashboard-grid">
      <article><span className="status-dot" /><h2>Identity</h2><p>Your account and selected organization are active.</p></article>
      <article><span className="status-dot" /><h2>LMS</h2><p>Course, lesson and assessment infrastructure is available.</p></article>
      <article><span className="status-dot" /><h2>AI Engineering</h2><p>Projects, experiments and autonomous workflows connect here.</p></article>
    </section>
  </main>;
}

"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

type Event = {
  id: string;
  actor_user_id: string | null;
  organization_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  detail: Record<string, unknown>;
  ip_address: string | null;
  user_agent: string | null;
  request_id: string | null;
  created_at: string;
};

async function request(path: string) {
  const response = await fetch(API + path, { credentials: "include" });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail ?? ("Request failed (" + response.status + ")"));
  return body;
}

export default function AuditPage() {
  const [events, setEvents] = useState<Event[]>([]);
  const [action, setAction] = useState("");
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  const [hasMore, setHasMore] = useState(false);

  async function load(nextOffset = 0) {
    setError("");
    try {
      const suffix = action.trim() ? "&action=" + encodeURIComponent(action.trim()) : "";
      const rows = await request("/audit/events?limit=50&offset=" + nextOffset + suffix) as Event[];
      setEvents(rows);
      setOffset(nextOffset);
      setHasMore(rows.length === 50);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load audit events.");
    }
  }

  useEffect(() => { void load(); }, []);

  return <main className="shell">
    <section className="hero">
      <p className="eyebrow">NEXUS-Ω / PHASE 9</p>
      <h1>Audit Stream</h1>
      <p className="lead">Organization-scoped audit events with request correlation. Access is restricted to owner and admin roles by the API.</p>
      <p><a href="/dashboard">Dashboard</a> · <a href="/">Home</a></p>
    </section>

    {error && <p role="alert" style={{ marginTop: 18 }}>{error}</p>}
    <section style={{ marginTop: 24 }}>
      <form onSubmit={(event) => { event.preventDefault(); void load(0); }} style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <label>Action filter<input value={action} maxLength={120} onChange={(event) => setAction(event.target.value)} placeholder="e.g. identity.login" /></label>
        <button type="submit">Filter</button>
      </form>
    </section>

    <section style={{ display: "grid", gap: 12, marginTop: 24 }}>
      {events.map((event) => <article key={event.id}>
        <p className="eyebrow">{event.action} · {event.resource_type}</p>
        <h2>{event.resource_id ?? "Event"}</h2>
        <p>Request: <code>{event.request_id ?? "not recorded"}</code></p>
        <small>{new Date(event.created_at).toLocaleString()} · Actor {event.actor_user_id ?? "system"}{event.ip_address ? " · " + event.ip_address : ""}</small>
        <details style={{ marginTop: 8 }}><summary>Details</summary><pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{JSON.stringify(event.detail, null, 2)}</pre></details>
      </article>)}
      {!events.length && <p>No audit events found.</p>}
    </section>

    <div style={{ display: "flex", gap: 10, marginTop: 18 }}>
      <button disabled={offset === 0} onClick={() => void load(Math.max(0, offset - 50))}>Previous</button>
      <button disabled={!hasMore} onClick={() => void load(offset + 50)}>Next</button>
    </div>
  </main>;
}

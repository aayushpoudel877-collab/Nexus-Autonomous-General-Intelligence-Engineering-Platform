"use client";

import { FormEvent, useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

type Health = {
  documents: Record<string, number>;
  chunks: number;
  new_feedback: number;
  pending_reindex_approvals: number;
  retrieval_mode: string;
  reindex_execution: string;
};
type Document = { id: string; title: string; source_uri: string; status: string; content_chars: number; created_at: string };
type Evidence = { evidence_id: string; document_id: string; chunk_id: string; title: string; source_uri: string; text: string; start_char: number; end_char: number; score: number; character_ngram_score?: number };
type QueryResult = { query: string; retrieval_mode: string; character_ngram_weight?: number; evidence: Evidence[]; note: string };
type Feedback = { id: string; query_sha256: string; evidence_ids: string[]; rating: "helpful" | "unhelpful"; note: string; status: string; created_at: string };
type FeedbackSummary = { total: number; by_rating: { helpful: number; unhelpful: number }; by_status: { new: number; triaged: number; resolved: number; ignored: number }; helpful_rate_percent: number | null; privacy: string };
type FeedbackTrend = { days: number; timezone: "UTC"; total: number; series: { date: string; helpful: number; unhelpful: number; total: number }[]; privacy: string };
type FeedbackPeriod = { start_date: string; end_date_exclusive: string; helpful: number; unhelpful: number; total: number; helpful_rate_percent: number | null };
type FeedbackComparison = { days: number; timezone: "UTC"; current: FeedbackPeriod; previous: FeedbackPeriod; change: { total: { absolute: number; percent: number | null }; helpful: { absolute: number; percent: number | null }; unhelpful: { absolute: number; percent: number | null }; helpful_rate_percentage_points: number | null }; privacy: string };
type FeedbackBacklog = { timezone: "UTC"; total_open: number; new_total: number; triaged_total: number; series: { key: string; label: string; new: number; triaged: number; total: number }[]; privacy: string };
type FeedbackLifecycleTrend = { days: number; timezone: "UTC"; totals: { created: number; triaged: number; resolved: number; ignored: number; total_actions: number }; series: { date: string; created: number; triaged: number; resolved: number; ignored: number; total_actions: number }[]; interpretation: string; privacy: string };
type ReindexRequest = { id: string; document_id: string; reason: string; status: string; requested_by_user_id: string | null; reviewed_by_user_id: string | null; created_at: string };

async function request(path: string, init?: RequestInit) {
  const response = await fetch(API + path, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? {});
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return body;
}

function Metric({ label, value, detail }: { label: string; value: string | number; detail: string }) {
  return <article><p className="eyebrow">{label}</p><h2 style={{ fontSize: "2.2rem", margin: "8px 0" }}>{value}</h2><p className="muted">{detail}</p></article>;
}

export default function RAGOperatorPage() {
  const [health, setHealth] = useState<Health | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [feedback, setFeedback] = useState<Feedback[]>([]);
  const [feedbackSummary, setFeedbackSummary] = useState<FeedbackSummary | null>(null);
  const [feedbackTrend, setFeedbackTrend] = useState<FeedbackTrend | null>(null);
  const [feedbackComparison, setFeedbackComparison] = useState<FeedbackComparison | null>(null);
  const [feedbackBacklog, setFeedbackBacklog] = useState<FeedbackBacklog | null>(null);
  const [feedbackLifecycle, setFeedbackLifecycle] = useState<FeedbackLifecycleTrend | null>(null);
  const [trendDays, setTrendDays] = useState("30");
  const [requests, setRequests] = useState<ReindexRequest[]>([]);
  const [query, setQuery] = useState("");
  const [characterNgramWeight, setCharacterNgramWeight] = useState("0");
  const [queryResult, setQueryResult] = useState<QueryResult | null>(null);
  const [feedbackNote, setFeedbackNote] = useState("");
  const [reindexReasons, setReindexReasons] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    const results = await Promise.allSettled([
      request("/rag/operator/health") as Promise<Health>,
      request("/rag/documents?status=active&limit=100") as Promise<Document[]>,
      request("/rag/operator/feedback?status=new&limit=50") as Promise<Feedback[]>,
      request("/rag/operator/reindex-requests?limit=50") as Promise<ReindexRequest[]>,
      request("/rag/operator/feedback/summary") as Promise<FeedbackSummary>,
      request(`/rag/operator/feedback/trend?days=${trendDays}`) as Promise<FeedbackTrend>,
      request(`/rag/operator/feedback/compare?days=${trendDays}`) as Promise<FeedbackComparison>,
      request("/rag/operator/feedback/backlog") as Promise<FeedbackBacklog>,
      request(`/rag/operator/feedback/lifecycle-trend?days=${trendDays}`) as Promise<FeedbackLifecycleTrend>,
    ]);
    if (results[0].status === "fulfilled") setHealth(results[0].value);
    if (results[1].status === "fulfilled") setDocuments(results[1].value);
    if (results[2].status === "fulfilled") setFeedback(results[2].value);
    if (results[3].status === "fulfilled") setRequests(results[3].value);
    if (results[4].status === "fulfilled") setFeedbackSummary(results[4].value);
    if (results[5].status === "fulfilled") setFeedbackTrend(results[5].value);
    if (results[6].status === "fulfilled") setFeedbackComparison(results[6].value);
    if (results[7].status === "fulfilled") setFeedbackBacklog(results[7].value);
    if (results[8].status === "fulfilled") setFeedbackLifecycle(results[8].value);
    const failures = results.filter((item): item is PromiseRejectedResult => item.status === "rejected");
    if (failures.length === results.length) setError(failures.map(item => item.reason instanceof Error ? item.reason.message : "Could not load operator data.").join(" · "));
    else if (failures.length) setNotice("Some operator sections are unavailable for this role. The API enforces permissions per action.");
    setLoading(false);
  }

  useEffect(() => { void load(); }, [trendDays]);

  async function runQuery(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!query.trim() || busy) return;
    setBusy("query"); setError(""); setNotice(""); setQueryResult(null);
    try {
      setQueryResult(await request("/rag/query", {
        method: "POST",
        body: JSON.stringify({
          query: query.trim(),
          top_k: 8,
          character_ngram_weight: Number(characterNgramWeight),
        }),
      }) as QueryResult);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not run retrieval.");
    } finally {
      setBusy("");
    }
  }

  async function submitFeedback(rating: "helpful" | "unhelpful", evidence?: Evidence) {
    if (!queryResult || busy) return;
    setBusy("feedback"); setError(""); setNotice("");
    try {
      await request("/rag/operator/feedback", {
        method: "POST",
        body: JSON.stringify({
          query: queryResult.query,
          evidence_ids: evidence ? [evidence.evidence_id] : queryResult.evidence.map(item => item.evidence_id),
          rating,
          note: feedbackNote.trim(),
        }),
      });
      setFeedbackNote("");
      setNotice("Feedback recorded. The raw query is not stored in the feedback record.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not record feedback.");
    } finally {
      setBusy("");
    }
  }

  async function updateFeedback(id: string, status: "triaged" | "resolved" | "ignored") {
    setBusy(id); setError(""); setNotice("");
    try {
      await request("/rag/operator/feedback/" + id, { method: "PATCH", body: JSON.stringify({ status }) });
      setNotice("Feedback status updated.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update feedback.");
    } finally {
      setBusy("");
    }
  }

  async function askForReindex(documentId: string) {
    const reason = (reindexReasons[documentId] ?? "").trim();
    if (!reason || busy) return;
    setBusy(documentId); setError(""); setNotice("");
    try {
      await request("/rag/operator/documents/" + documentId + "/reindex", { method: "POST", body: JSON.stringify({ reason }) });
      setReindexReasons(current => ({ ...current, [documentId]: "" }));
      setNotice("Reindex request submitted for approval. This records a request; it does not run an indexing job.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not request reindex.");
    } finally {
      setBusy("");
    }
  }

  async function reviewReindex(id: string, decision: "approved" | "rejected") {
    setBusy(id); setError(""); setNotice("");
    try {
      await request("/rag/operator/reindex-requests/" + id, { method: "PATCH", body: JSON.stringify({ decision }) });
      setNotice("Review decision saved. Reindex execution remains disconnected.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not review request.");
    } finally {
      setBusy("");
    }
  }

  return <main className="shell">
    <section className="hero">
      <p className="eyebrow">NEXUS-Ω / RAG PHASES 36–37</p>
      <h1>RAG Operator Workbench</h1>
      <p className="lead">Inspect corpus health, compare multilingual lexical retrieval, triage feedback and manage reindex approvals within your selected organization.</p>
      <p><a href="/dashboard">Dashboard</a> · <a href="/rag-studio">RAG Studio</a> · <a href="/audit">Audit stream</a> · <a href="/">Home</a> · <button className="secondary" onClick={() => void load()} disabled={loading}>{loading ? "Refreshing…" : "Refresh data"}</button></p>
    </section>

    {error && <p role="alert" className="error" style={{ maxWidth: 1120, margin: "20px auto" }}>{error}</p>}
    {notice && <p role="status" className="muted" style={{ maxWidth: 1120, margin: "20px auto" }}>{notice}</p>}

    <section className="grid" style={{ maxWidth: 1120, margin: "28px auto", gridTemplateColumns: "repeat(auto-fit,minmax(190px,1fr))" }}>
      <Metric label="ACTIVE DOCUMENTS" value={health?.documents.active ?? "—"} detail="Visible to this organization" />
      <Metric label="CHUNKS" value={health?.chunks ?? "—"} detail="Persisted retrieval units" />
      <Metric label="NEW FEEDBACK" value={health?.new_feedback ?? "—"} detail="Waiting for triage" />
      <Metric label="REINDEX APPROVALS" value={health?.pending_reindex_approvals ?? "—"} detail="Pending operator review" />
    </section>

    <section style={{ maxWidth: 1120, margin: "32px auto", display: "grid", gap: 18 }}>
      <article>
        <p className="eyebrow">RETRIEVAL DIAGNOSTICS</p>
        <h2>Run a query and inspect evidence</h2>
        <p className="muted">Results show the current retrieval mode and evidence scores. Query traces are shown in this session and are not persisted as raw query text.</p>
        <form onSubmit={runQuery} style={{ display: "grid", gap: 12 }}>
          <label style={{ display: "grid", gap: 8 }}>Test query
            <textarea value={query} onChange={e => setQuery(e.target.value)} maxLength={2000} rows={3} required placeholder="Ask a question about your indexed documents…" />
          </label>
          <label style={{ display: "grid", gap: 8, maxWidth: 420 }}>Character n-gram assist
            <select value={characterNgramWeight} onChange={e => setCharacterNgramWeight(e.target.value)}>
              <option value="0">Off — standard lexical matching</option>
              <option value="0.25">Low — 25%</option>
              <option value="0.5">Balanced — 50%</option>
              <option value="0.75">High — 75%</option>
              <option value="1">Character n-grams only</option>
            </select>
            <span className="muted">An optional lexical fallback for scripts without reliable whitespace word boundaries. This is not translation or semantic search.</span>
          </label>
          <div><button type="submit" disabled={busy !== "" || !query.trim()}>{busy === "query" ? "Retrieving…" : "Run retrieval"}</button></div>
        </form>
        {queryResult && <div style={{ marginTop: 20 }}>
          <p className="muted">Mode: <strong>{queryResult.retrieval_mode}</strong> · character n-gram weight {((queryResult.character_ngram_weight ?? 0) * 100).toFixed(0)}% · {queryResult.evidence.length} evidence item(s)</p>
          <p>{queryResult.note}</p>
          <div style={{ display: "grid", gap: 12 }}>
            {queryResult.evidence.map(item => <article key={item.evidence_id}>
              <p className="eyebrow">{item.title} · fused score {item.score.toFixed(4)} · n-gram coverage {(item.character_ngram_score ?? 0).toFixed(3)}</p>
              <p style={{ whiteSpace: "pre-wrap" }}>{item.text}</p>
              <small className="muted">Evidence {item.evidence_id} · chars {item.start_char}–{item.end_char}</small>
              {item.source_uri && <p><a href={item.source_uri} target="_blank" rel="noreferrer">Open source</a></p>}
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button className="secondary" disabled={busy !== ""} onClick={() => void submitFeedback("helpful", item)}>Useful evidence</button>
                <button className="secondary" disabled={busy !== ""} onClick={() => void submitFeedback("unhelpful", item)}>Not useful</button>
              </div>
            </article>)}
            {!queryResult.evidence.length && <p>No evidence was retrieved for this query.</p>}
          </div>
          {queryResult.evidence.length > 0 && <form onSubmit={e => { e.preventDefault(); void submitFeedback("unhelpful"); }} style={{ display: "grid", gap: 8, marginTop: 16 }}>
            <label style={{ display: "grid", gap: 8 }}>Optional feedback note
              <textarea value={feedbackNote} onChange={e => setFeedbackNote(e.target.value)} maxLength={1000} rows={2} placeholder="Describe what could be improved (do not include secrets or personal data)." />
            </label>
            <div><button type="submit" className="secondary" disabled={busy !== ""}>Flag this result set</button></div>
          </form>}
        </div>}
      </article>

      <article>
        <p className="eyebrow">FEEDBACK INSIGHTS</p>
        <h2>How is retrieval working for your team?</h2>
        {feedbackSummary ? <>
          <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))", gap: 12 }}>
            <Metric label="TOTAL RESPONSES" value={feedbackSummary.total} detail="All recorded feedback" />
            <Metric label="HELPFUL" value={feedbackSummary.by_rating.helpful} detail="Marked useful by users" />
            <Metric label="NEEDS IMPROVEMENT" value={feedbackSummary.by_rating.unhelpful} detail="Marked not useful" />
            <Metric label="HELPFUL RATE" value={feedbackSummary.helpful_rate_percent === null ? "—" : feedbackSummary.helpful_rate_percent + "%"} detail="Of all submitted ratings" />
          </div>
          <div style={{ display: "flex", gap: 18, flexWrap: "wrap", marginTop: 16 }}>
            <span className="muted">New: <strong>{feedbackSummary.by_status.new}</strong></span>
            <span className="muted">Triaged: <strong>{feedbackSummary.by_status.triaged}</strong></span>
            <span className="muted">Resolved: <strong>{feedbackSummary.by_status.resolved}</strong></span>
            <span className="muted">Ignored: <strong>{feedbackSummary.by_status.ignored}</strong></span>
          </div>
          <p className="muted">{feedbackSummary.privacy}</p>
        </> : <p className="muted">Feedback insight aggregates are unavailable for this role or could not be loaded.</p>}
      </article>

      <article>
        <p className="eyebrow">FEEDBACK ACTIVITY</p>
        <h2>Feedback over time</h2>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", margin: "12px 0 18px" }}>
          <label>Time window
            <select value={trendDays} onChange={event => setTrendDays(event.target.value)} style={{ marginLeft: 8 }}>
              <option value="7">Last 7 days</option>
              <option value="30">Last 30 days</option>
              <option value="90">Last 90 days</option>
            </select>
          </label>
          <span className="muted">{feedbackTrend?.total ?? "—"} responses · UTC</span>
        </div>
        {feedbackComparison ? <section aria-label="Feedback period comparison" style={{ display: "grid", gap: 10, margin: "8px 0 20px" }}>
          <p className="eyebrow">PERIOD-OVER-PERIOD · {feedbackComparison.days} COMPLETE UTC DAYS</p>
          <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit,minmax(155px,1fr))", gap: 12 }}>
            <Metric label="CURRENT PERIOD" value={feedbackComparison.current.total} detail={feedbackComparison.current.start_date + " to " + feedbackComparison.current.end_date_exclusive + " (exclusive)"} />
            <Metric label="PREVIOUS PERIOD" value={feedbackComparison.previous.total} detail={feedbackComparison.previous.start_date + " to " + feedbackComparison.previous.end_date_exclusive + " (exclusive)"} />
            <Metric label="HELPFUL RESPONSES" value={feedbackComparison.current.helpful} detail={(feedbackComparison.change.helpful.absolute > 0 ? "+" : "") + feedbackComparison.change.helpful.absolute + " vs " + feedbackComparison.previous.helpful + " previously"} />
            <Metric label="NEEDS IMPROVEMENT" value={feedbackComparison.current.unhelpful} detail={(feedbackComparison.change.unhelpful.absolute > 0 ? "+" : "") + feedbackComparison.change.unhelpful.absolute + " vs " + feedbackComparison.previous.unhelpful + " previously"} />
            <Metric label="RESPONSE CHANGE" value={(feedbackComparison.change.total.absolute > 0 ? "+" : "") + feedbackComparison.change.total.absolute} detail={feedbackComparison.change.total.percent === null ? "Percentage change unavailable (no prior responses)" : (feedbackComparison.change.total.percent > 0 ? "+" : "") + feedbackComparison.change.total.percent + "% vs previous period"} />
            <Metric label="HELPFUL-RATE CHANGE" value={feedbackComparison.change.helpful_rate_percentage_points === null ? "—" : (feedbackComparison.change.helpful_rate_percentage_points > 0 ? "+" : "") + feedbackComparison.change.helpful_rate_percentage_points + " pp"} detail="Percentage-point difference; user-perceived usefulness only" />
          </div>
          <p className="muted">{feedbackComparison.privacy}</p>
        </section> : <p className="muted">Period comparison is unavailable for this role or could not be loaded.</p>}
        {feedbackTrend ? <>
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 14 }}>
            <span className="muted"><span aria-hidden="true" style={{ display: "inline-block", width: 9, height: 9, borderRadius: 3, background: "#16856b", marginRight: 6 }} />Helpful</span><span className="muted"><span aria-hidden="true" style={{ display: "inline-block", width: 9, height: 9, borderRadius: 3, background: "#d97757", marginRight: 6 }} />Needs improvement</span>
          </div>
          <div style={{ display: "grid", gap: 8 }}>
            {feedbackTrend.series.map(day => {
              const max = Math.max(1, ...feedbackTrend.series.map(item => item.total));
              return <div key={day.date} style={{ display: "grid", gridTemplateColumns: "104px minmax(80px,1fr) 34px", alignItems: "center", gap: 10 }}>
                <small className="muted">{day.date.slice(5)}</small>
                <div role="img" aria-label={day.date + ": " + day.helpful + " helpful, " + day.unhelpful + " needs improvement"} style={{ display: "grid", gap: 3 }}>
                  <div style={{ height: 7, width: Math.max(day.helpful ? 3 : 0, day.helpful / max * 100) + "%", background: "#16856b", borderRadius: 6 }} />
                  <div style={{ height: 7, width: Math.max(day.unhelpful ? 3 : 0, day.unhelpful / max * 100) + "%", background: "#d97757", borderRadius: 6 }} />
                </div>
                <small className="muted" style={{ textAlign: "right" }}>{day.total}</small>
              </div>;
            })}
          </div>
          <p className="muted" style={{ marginTop: 14 }}>{feedbackTrend.privacy}</p>
        </> : <p className="muted">Daily feedback activity is unavailable for this role or could not be loaded.</p>}
      </article>

      <article>
        <p className="eyebrow">FEEDBACK LIFECYCLE</p>
        <h2>Submission, triage and resolution activity</h2>
        {feedbackLifecycle ? <>
          <p className="muted">{feedbackLifecycle.days}-day activity window · UTC · {feedbackLifecycle.totals.total_actions} recorded actions</p>
          <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit,minmax(145px,1fr))", gap: 12, marginBottom: 16 }}>
            <Metric label="SUBMITTED" value={feedbackLifecycle.totals.created} detail="Feedback created" />
            <Metric label="TRIAGED" value={feedbackLifecycle.totals.triaged} detail="Moved into triage" />
            <Metric label="RESOLVED" value={feedbackLifecycle.totals.resolved} detail="Marked resolved" />
            <Metric label="IGNORED" value={feedbackLifecycle.totals.ignored} detail="Marked ignored" />
          </div>
          <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginBottom: 12 }}>
            <span className="muted">Submitted <span aria-hidden="true" style={{ display: "inline-block", width: 9, height: 9, background: "#64748b", borderRadius: 3 }} /></span>
            <span className="muted">Triaged <span aria-hidden="true" style={{ display: "inline-block", width: 9, height: 9, background: "#16856b", borderRadius: 3 }} /></span>
            <span className="muted">Resolved <span aria-hidden="true" style={{ display: "inline-block", width: 9, height: 9, background: "#2563eb", borderRadius: 3 }} /></span>
            <span className="muted">Ignored <span aria-hidden="true" style={{ display: "inline-block", width: 9, height: 9, background: "#d97757", borderRadius: 3 }} /></span>
          </div>
          <div style={{ display: "grid", gap: 7 }}>
            {feedbackLifecycle.series.map(day => {
              const max = Math.max(1, ...feedbackLifecycle.series.map(item => item.total_actions));
              return <div key={day.date} style={{ display: "grid", gridTemplateColumns: "90px minmax(100px,1fr) 32px", alignItems: "center", gap: 10 }}>
                <small className="muted">{day.date.slice(5)}</small>
                <div role="img" aria-label={day.date + ": " + day.created + " submitted, " + day.triaged + " triaged, " + day.resolved + " resolved, " + day.ignored + " ignored"} style={{ display: "grid", gap: 3 }}>
                  {[["created", "#64748b"], ["triaged", "#16856b"], ["resolved", "#2563eb"], ["ignored", "#d97757"]].map(([key, color]) => {
                    const count = day[key as "created" | "triaged" | "resolved" | "ignored"];
                    return <div key={key} style={{ height: 5, width: Math.max(count ? 3 : 0, count / max * 100) + "%", background: color, borderRadius: 5 }} />;
                  })}
                </div>
                <small className="muted" style={{ textAlign: "right" }}>{day.total_actions}</small>
              </div>;
            })}
          </div>
          <p className="muted" style={{ marginTop: 14 }}>{feedbackLifecycle.interpretation} {feedbackLifecycle.privacy}</p>
        </> : <p className="muted">Feedback lifecycle analytics are unavailable for this role or could not be loaded.</p>}
      </article>

      <article>
        <p className="eyebrow">FEEDBACK BACKLOG</p>
        <h2>How long has unresolved feedback been waiting?</h2>
        {feedbackBacklog ? <>
          <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit,minmax(155px,1fr))", gap: 12, marginBottom: 16 }}>
            <Metric label="OPEN FEEDBACK" value={feedbackBacklog.total_open} detail="New and triaged items" />
            <Metric label="NEW" value={feedbackBacklog.new_total} detail="Not yet triaged" />
            <Metric label="TRIAGED" value={feedbackBacklog.triaged_total} detail="Awaiting resolution or dismissal" />
          </div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
              <thead><tr>
                <th scope="col" style={{ padding: 10 }}>Age (UTC)</th>
                <th scope="col" style={{ padding: 10 }}>New</th>
                <th scope="col" style={{ padding: 10 }}>Triaged</th>
                <th scope="col" style={{ padding: 10 }}>Total</th>
              </tr></thead>
              <tbody>{feedbackBacklog.series.map(bucket => <tr key={bucket.key} style={{ borderTop: "1px solid #e4e7ec" }}>
                <th scope="row" style={{ padding: 10 }}>{bucket.label}</th>
                <td style={{ padding: 10 }}>{bucket.new}</td>
                <td style={{ padding: 10 }}>{bucket.triaged}</td>
                <td style={{ padding: 10 }}><strong>{bucket.total}</strong></td>
              </tr>)}</tbody>
            </table>
          </div>
          <p className="muted">{feedbackBacklog.privacy}</p>
        </> : <p className="muted">Feedback backlog aging is unavailable for this role or could not be loaded.</p>}
      </article>

      <article>
        <p className="eyebrow">FEEDBACK TRIAGE</p>
        <h2>New feedback</h2>
        <p className="muted">Feedback contains query digests and evidence IDs rather than the raw query. Access is restricted by API role permissions.</p>
        {feedback.map(item => <div key={item.id} style={{ borderTop: "1px solid #e4e7ec", padding: "14px 0" }}>
          <p><strong>{item.rating === "helpful" ? "Helpful" : "Needs improvement"}</strong> · {new Date(item.created_at).toLocaleString()}</p>
          <p className="muted">Query digest: <code>{item.query_sha256.slice(0, 16)}…</code> · Evidence IDs: {item.evidence_ids.join(", ") || "none"}</p>
          {item.note && <p>{item.note}</p>}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button className="secondary" disabled={busy !== ""} onClick={() => void updateFeedback(item.id, "triaged")}>Mark triaged</button>
            <button className="secondary" disabled={busy !== ""} onClick={() => void updateFeedback(item.id, "resolved")}>Resolve</button>
            <button className="secondary" disabled={busy !== ""} onClick={() => void updateFeedback(item.id, "ignored")}>Ignore</button>
          </div>
        </div>)}
        {!feedback.length && <p className="muted">No new feedback or the triage queue is not available to this role.</p>}
      </article>

      <article>
        <p className="eyebrow">CONTROLLED REINDEXING</p>
        <h2>Request reindex review</h2>
        <p className="muted">Only active documents are listed. Owner/admin authorization is enforced by the API. An approval records a decision only; it does not execute a job.</p>
        {documents.map(doc => <div key={doc.id} style={{ borderTop: "1px solid #e4e7ec", padding: "14px 0", display: "grid", gap: 8 }}>
          <strong>{doc.title}</strong>
          <small className="muted">{doc.content_chars.toLocaleString()} characters · added {new Date(doc.created_at).toLocaleDateString()} · <code>{doc.id}</code></small>
          <label style={{ display: "grid", gap: 8 }}>Reason for reindex
            <input value={reindexReasons[doc.id] ?? ""} onChange={e => setReindexReasons(current => ({ ...current, [doc.id]: e.target.value }))} maxLength={1000} placeholder="Explain what should be refreshed" />
          </label>
          <div><button className="secondary" disabled={busy !== "" || !(reindexReasons[doc.id] ?? "").trim()} onClick={() => void askForReindex(doc.id)}>Submit for approval</button></div>
        </div>)}
        {!documents.length && <p className="muted">No active documents found.</p>}
      </article>

      <article>
        <p className="eyebrow">APPROVAL QUEUE</p>
        <h2>Reindex requests</h2>
        {requests.map(item => <div key={item.id} style={{ borderTop: "1px solid #e4e7ec", padding: "14px 0" }}>
          <p><strong>{item.status.replaceAll("_", " ")}</strong> · {new Date(item.created_at).toLocaleString()}</p>
          <p>{item.reason}</p>
          <small className="muted">Document <code>{item.document_id}</code> · Request <code>{item.id}</code></small>
          {item.status === "pending_approval" && <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
            <button className="secondary" disabled={busy !== ""} onClick={() => void reviewReindex(item.id, "approved")}>Approve request</button>
            <button className="secondary" disabled={busy !== ""} onClick={() => void reviewReindex(item.id, "rejected")}>Reject request</button>
          </div>}
        </div>)}
        {!requests.length && <p className="muted">No reindex requests or the approval queue is not available to this role.</p>}
      </article>

      <article>
        <p className="eyebrow">EVALUATION GOVERNANCE</p>
        <h2>Dataset review status</h2>
        <p className="muted">The CI evaluation gate currently runs deterministic contract fixtures. A human-reviewed dataset approval interface and semantic answer-faithfulness evaluation are not connected yet; do not treat synthetic fixtures as production-quality benchmarks.</p>
        <p><a href="https://github.com/aayushpoudel877-collab/Nexus-Autonomous-General-Intelligence-Engineering-Platform/tree/main/docs/rag">Review RAG evaluation documentation</a></p>
      </article>
    </section>
  </main>;
}

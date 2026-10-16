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
type Evidence = { evidence_id: string; document_id: string; chunk_id: string; title: string; source_uri: string; text: string; start_char: number; end_char: number; score: number };
type QueryResult = { query: string; retrieval_mode: string; evidence: Evidence[]; note: string };
type Feedback = { id: string; query_sha256: string; evidence_ids: string[]; rating: "helpful" | "unhelpful"; note: string; status: string; created_at: string };
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
    ]);
    if (results[0].status === "fulfilled") setHealth(results[0].value);
    if (results[1].status === "fulfilled") setDocuments(results[1].value);
    if (results[2].status === "fulfilled") setFeedback(results[2].value);
    if (results[3].status === "fulfilled") setRequests(results[3].value);
    const failures = results.filter((item): item is PromiseRejectedResult => item.status === "rejected");
    if (failures.length === results.length) setError(failures.map(item => item.reason instanceof Error ? item.reason.message : "Could not load operator data.").join(" · "));
    else if (failures.length) setNotice("Some operator sections are unavailable for this role. The API enforces permissions per action.");
    setLoading(false);
  }

  useEffect(() => { void load(); }, []);

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
      <p className="eyebrow">NEXUS-Ω / RAG PHASE 36</p>
      <h1>RAG Operator Workbench</h1>
      <p className="lead">Inspect corpus health, run retrieval diagnostics, triage feedback and manage reindex approvals within your selected organization.</p>
      <p><a href="/dashboard">Dashboard</a> · <a href="/audit">Audit stream</a> · <a href="/">Home</a> · <button className="secondary" onClick={() => void load()} disabled={loading}>{loading ? "Refreshing…" : "Refresh data"}</button></p>
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
          <p className="muted">Mode: <strong>{queryResult.retrieval_mode}</strong> · {queryResult.evidence.length} evidence item(s)</p>
          <p>{queryResult.note}</p>
          <div style={{ display: "grid", gap: 12 }}>
            {queryResult.evidence.map(item => <article key={item.evidence_id}>
              <p className="eyebrow">{item.title} · score {item.score.toFixed(4)}</p>
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

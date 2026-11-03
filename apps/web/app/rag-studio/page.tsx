"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const MAX_FILE_BYTES = 10 * 1024 * 1024;
const ACCEPTED_FILES = ".txt,.md,.html,.htm,.pdf,.docx";

type Document = {
  id: string;
  title: string;
  source_uri: string;
  content_chars: number;
  status: "active" | "archived" | "deleted";
  metadata: Record<string, unknown>;
  created_at: string;
  content_sha256?: string;
};
type Evidence = {
  evidence_id: string;
  document_id: string;
  chunk_id: string;
  title: string;
  source_uri: string;
  text: string;
  start_char: number;
  end_char: number;
  score: number;
  character_ngram_score?: number;
};
type QueryResult = {
  query: string;
  retrieval_mode: string;
  character_ngram_weight: number;
  evidence: Evidence[];
  note: string;
};
type CreatedResponse = { document: Document; created: boolean };

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!(init?.body instanceof FormData) && init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(API + path, { ...init, headers, credentials: "include" });
  if (response.status === 204) return undefined as T;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof body.detail === "string" ? body.detail : "";
    if (response.status === 401) throw new Error("Your session has expired. Sign in again to continue.");
    if (response.status === 403) throw new Error("Your account can view this workspace, but this action needs an owner, admin, or instructor role.");
    throw new Error(detail || "Request failed (" + response.status + "). Please try again.");
  }
  return body as T;
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1024 / 1024).toFixed(1) + " MB";
}

function shortDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value));
}

function safeHttpUrl(value: string) {
  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.toString() : "";
  } catch {
    return "";
  }
}

export default function RAGStudioPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState<"sources" | "ask">("sources");
  const [sourceMode, setSourceMode] = useState<"file" | "text">("file");
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [sourceUri, setSourceUri] = useState("");
  const [pastedText, setPastedText] = useState("");
  const [question, setQuestion] = useState("");
  const [queryResult, setQueryResult] = useState<QueryResult | null>(null);
  const [ngramWeight, setNgramWeight] = useState("0");
  const [expandedEvidence, setExpandedEvidence] = useState<string[]>([]);
  const [busy, setBusy] = useState<"ingest" | "query" | "feedback" | "delete" | "">("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [selectedDocument, setSelectedDocument] = useState("");

  const loadDocuments = useCallback(async (quiet = false) => {
    if (quiet) setRefreshing(true);
    else setLoading(true);
    try {
      const rows = await apiRequest<Document[]>("/rag/documents?status=active&limit=100");
      setDocuments(rows);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load your knowledge sources.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { void loadDocuments(); }, [loadDocuments]);

  const totalCharacters = useMemo(
    () => documents.reduce((sum, document) => sum + document.content_chars, 0),
    [documents],
  );

  function selectFile(event: ChangeEvent<HTMLInputElement>) {
    const next = event.target.files?.[0] ?? null;
    setError("");
    if (next && next.size > MAX_FILE_BYTES) {
      setFile(null);
      event.target.value = "";
      setError("That file is " + formatBytes(next.size) + ". The upload limit is 10 MB.");
      return;
    }
    setFile(next);
    if (next && !title.trim()) setTitle(next.name.replace(/\.[^.]+$/, ""));
  }

  async function addSource(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setBusy("ingest");
    setError("");
    setNotice("");
    try {
      let result: CreatedResponse;
      if (sourceMode === "file") {
        if (!file) throw new Error("Choose a document first.");
        const form = new FormData();
        form.append("file", file);
        if (title.trim()) form.append("title", title.trim());
        if (sourceUri.trim()) form.append("source_uri", sourceUri.trim());
        result = await apiRequest<CreatedResponse>("/rag/documents/upload", { method: "POST", body: form });
      } else {
        if (!title.trim()) throw new Error("Add a name for this source.");
        if (!pastedText.trim()) throw new Error("Paste some text to add to your knowledge base.");
        result = await apiRequest<CreatedResponse>("/rag/documents", {
          method: "POST",
          body: JSON.stringify({ title: title.trim(), text: pastedText, source_uri: sourceUri.trim() }),
        });
      }
      setNotice(result.created
        ? '"' + result.document.title + '" was added and is ready for retrieval.'
        : 'This content already exists as "' + result.document.title + '". No duplicate was created.');
      setFile(null);
      setTitle("");
      setSourceUri("");
      setPastedText("");
      const input = document.getElementById("rag-file-input") as HTMLInputElement | null;
      if (input) input.value = "";
      await loadDocuments(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add this source.");
    } finally {
      setBusy("");
    }
  }

  async function runSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!question.trim() || busy) return;
    setBusy("query");
    setError("");
    setNotice("");
    setQueryResult(null);
    setExpandedEvidence([]);
    try {
      const result = await apiRequest<QueryResult>("/rag/query", {
        method: "POST",
        body: JSON.stringify({ query: question.trim(), top_k: 8, character_ngram_weight: Number(ngramWeight) }),
      });
      setQueryResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not search your knowledge base.");
    } finally {
      setBusy("");
    }
  }

  async function sendFeedback(rating: "helpful" | "unhelpful", evidence?: Evidence) {
    if (!queryResult || busy) return;
    setBusy("feedback");
    setError("");
    setNotice("");
    try {
      await apiRequest("/rag/operator/feedback", {
        method: "POST",
        body: JSON.stringify({
          query: queryResult.query,
          evidence_ids: evidence ? [evidence.evidence_id] : queryResult.evidence.map(item => item.evidence_id),
          rating,
          note: "",
        }),
      });
      setNotice("Thanks — your feedback was saved. The feedback record stores a query digest, not the raw question.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save feedback.");
    } finally {
      setBusy("");
    }
  }

  async function removeSource(item: Document) {
    if (busy) return;
    if (!window.confirm('Remove "' + item.title + '" from active retrieval?')) return;
    setBusy("delete");
    setError("");
    setNotice("");
    try {
      await apiRequest("/rag/documents/" + item.id, { method: "DELETE" });
      setNotice('"' + item.title + '" was removed from the active knowledge base.');
      await loadDocuments(true);
      if (selectedDocument === item.id) setSelectedDocument("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not remove this source.");
    } finally {
      setBusy("");
    }
  }

  function toggleEvidence(id: string) {
    setExpandedEvidence(current => current.includes(id) ? current.filter(item => item !== id) : [...current, id]);
  }

  return (
    <main className="rag-studio">
      <header className="rag-studio-header">
        <a className="rag-brand" href="/">NEXUS<span>Ω</span></a>
        <nav aria-label="Main navigation"><a href="/dashboard">Dashboard</a><a href="/rag-operator">Operator tools</a><a href="/audit">Audit</a></nav>
      </header>

      <section className="rag-welcome">
        <div>
          <p className="rag-kicker">YOUR KNOWLEDGE WORKSPACE</p>
          <h1>Make your knowledge<br /><span>work for you.</span></h1>
          <p className="rag-intro">Bring your documents together, ask questions in plain language, and see exactly which sources support each result.</p>
          <div className="rag-status"><span className="rag-status-dot" /> Workspace connected <span className="rag-status-separator">·</span> Organization-scoped knowledge</div>
        </div>
        <div className="rag-welcome-art" aria-hidden="true">
          <div className="rag-orbit rag-orbit-one" /><div className="rag-orbit rag-orbit-two" /><div className="rag-orbit-core">N</div>
          <span className="rag-orbit-tag rag-tag-a">Sources</span><span className="rag-orbit-tag rag-tag-b">Answers</span><span className="rag-orbit-tag rag-tag-c">Evidence</span>
        </div>
      </section>

      <section className="rag-how" aria-label="How RAG Studio works">
        <div className="rag-how-step"><span>01</span><div><strong>Add your sources</strong><small>Upload files or paste text</small></div></div><div className="rag-how-line" />
        <div className="rag-how-step"><span>02</span><div><strong>Build your library</strong><small>Content is extracted and split into chunks</small></div></div><div className="rag-how-line" />
        <div className="rag-how-step"><span>03</span><div><strong>Ask with evidence</strong><small>Find relevant passages and inspect sources</small></div></div>
      </section>

      {(error || notice) && <div className={"rag-message " + (error ? "is-error" : "is-success")} role={error ? "alert" : "status"}>{error || notice}</div>}

      <section className="rag-workspace">
        <aside className="rag-sidebar">
          <div className="rag-sidebar-title"><div><p className="rag-kicker">WORKSPACE</p><h2>Knowledge base</h2></div><button className="rag-icon-button" onClick={() => void loadDocuments(true)} disabled={refreshing} aria-label="Refresh sources">{refreshing ? "…" : "↻"}</button></div>
          <div className="rag-stats"><div><strong>{loading ? "—" : documents.length}</strong><span>Active sources</span></div><div><strong>{loading ? "—" : totalCharacters.toLocaleString()}</strong><span>Characters stored</span></div></div>
          <div className="rag-source-list">
            {loading && <p className="rag-empty">Loading your sources…</p>}
            {!loading && documents.map(item => (
              <div className={"rag-source-item " + (selectedDocument === item.id ? "is-selected" : "")} key={item.id}>
                <button className="rag-source-select" onClick={() => setSelectedDocument(current => current === item.id ? "" : item.id)} aria-expanded={selectedDocument === item.id}>
                  <span className="rag-file-icon">▤</span><span className="rag-source-copy"><strong>{item.title}</strong><small>{item.content_chars.toLocaleString()} characters · {shortDate(item.created_at)}</small></span><span className="rag-chevron">{selectedDocument === item.id ? "−" : "+"}</span>
                </button>
                {selectedDocument === item.id && <div className="rag-source-detail"><span className="rag-ready-pill">Ready for retrieval</span><small>Content ID: {item.id.slice(0, 8)}…</small><small>SHA-256: {item.content_sha256?.slice(0, 16) ?? "available in source record"}…</small>{safeHttpUrl(item.source_uri) && <a href={safeHttpUrl(item.source_uri)} target="_blank" rel="noreferrer">Open original source ↗</a>}<button className="rag-remove-link" onClick={() => void removeSource(item)} disabled={busy !== ""}>Remove from active library</button></div>}
              </div>
            ))}
            {!loading && !documents.length && <div className="rag-empty-state"><span>▤</span><strong>Your library is empty</strong><p>Add your first source to make it searchable.</p><button className="rag-text-button" onClick={() => { setActiveTab("sources"); document.getElementById("rag-add-source")?.scrollIntoView({ behavior: "smooth" }); }}>Add a source →</button></div>}
          </div>
          <div className="rag-sidebar-foot"><span className="rag-mini-dot" /> Your sources are isolated to your organization.</div>
        </aside>

        <div className="rag-main-panel">
          <div className="rag-tabs" role="tablist" aria-label="RAG workspace">
            <button role="tab" aria-selected={activeTab === "sources"} className={activeTab === "sources" ? "is-active" : ""} onClick={() => setActiveTab("sources")}>＋ Add knowledge</button>
            <button role="tab" aria-selected={activeTab === "ask"} className={activeTab === "ask" ? "is-active" : ""} onClick={() => setActiveTab("ask")}>⌕ Ask your knowledge</button>
          </div>

          {activeTab === "sources" ? (
            <section className="rag-panel-content" id="rag-add-source">
              <div className="rag-panel-heading"><div><p className="rag-kicker">STEP 01 · ADD KNOWLEDGE</p><h2>Give your AI something to know.</h2><p>Start with a document or paste the text you want to search later.</p></div><span className="rag-heading-icon">＋</span></div>
              <div className="rag-mode-switch" role="group" aria-label="Source type"><button className={sourceMode === "file" ? "is-active" : ""} onClick={() => setSourceMode("file")}><span>⇧</span> Upload a file</button><button className={sourceMode === "text" ? "is-active" : ""} onClick={() => setSourceMode("text")}><span>¶</span> Paste text</button></div>
              <form className="rag-add-form" onSubmit={addSource}>
                {sourceMode === "file" ? (
                  <label className={"rag-dropzone " + (file ? "has-file" : "")} htmlFor="rag-file-input">
                    <input id="rag-file-input" type="file" accept={ACCEPTED_FILES} onChange={selectFile} />
                    <span className="rag-upload-symbol">↑</span><strong>{file ? file.name : "Choose a document to upload"}</strong><span>{file ? formatBytes(file.size) + " · Ready to add" : "Select a file from your device"}</span><small>PDF, DOCX, TXT, Markdown or HTML · Up to 10 MB</small>
                  </label>
                ) : (
                  <label className="rag-field rag-text-field">Document text<textarea value={pastedText} onChange={event => setPastedText(event.target.value)} rows={9} maxLength={2_000_000} placeholder="Paste notes, policies, research, course material, or any text you want to make searchable…" /></label>
                )}
                <div className="rag-form-grid">
                  <label className="rag-field">Source name<input value={title} onChange={event => setTitle(event.target.value)} maxLength={300} placeholder={file?.name ?? "e.g. Product handbook"} /></label>
                  <label className="rag-field">Original link <span className="rag-optional">Optional</span><input type="url" value={sourceUri} onChange={event => setSourceUri(event.target.value)} maxLength={2048} placeholder="https://example.com/document" /></label>
                </div>
                <div className="rag-add-footer"><p>Content is stored in your organization’s knowledge base. Duplicate content is detected automatically.</p><button className="rag-primary-button" type="submit" disabled={busy !== "" || (sourceMode === "file" ? !file : !pastedText.trim())}>{busy === "ingest" ? "Adding source…" : "Add to knowledge base"} <span>→</span></button></div>
              </form>
              <div className="rag-info-note"><span>ⓘ</span><p><strong>What happens next?</strong> NEXUS extracts the readable text, splits it into smaller passages (chunks), and saves it for retrieval. This is a synchronous ingestion step, not a background indexing job.</p></div>
            </section>
          ) : (
            <section className="rag-panel-content rag-ask-panel">
              <div className="rag-panel-heading"><div><p className="rag-kicker">STEP 03 · ASK YOUR KNOWLEDGE</p><h2>What would you like to find?</h2><p>Ask a question. NEXUS will search your active sources and show the passages it matched.</p></div><span className="rag-heading-icon">⌕</span></div>
              <form className="rag-question-form" onSubmit={runSearch}>
                <label className="rag-field">Your question<textarea value={question} onChange={event => setQuestion(event.target.value)} rows={3} maxLength={2000} placeholder="For example: What are the key steps in our onboarding process?" /></label>
                <div className="rag-question-options"><label className="rag-field rag-select-field">Language matching<select value={ngramWeight} onChange={event => setNgramWeight(event.target.value)}><option value="0">Standard word matching</option><option value="0.25">Add light character matching</option><option value="0.5">Balanced character matching</option><option value="0.75">Strong character matching</option><option value="1">Character matching only</option></select></label><button className="rag-primary-button" type="submit" disabled={busy !== "" || !question.trim() || documents.length === 0}>{busy === "query" ? "Searching sources…" : "Search my knowledge"} <span>→</span></button></div>
              </form>
              {documents.length === 0 && <div className="rag-info-note"><span>ⓘ</span><p><strong>Add a source first.</strong> Your knowledge base is empty, so there is nothing to search yet. Use “Add knowledge” to upload a document or paste text.</p></div>}
              {queryResult && (
                <div className="rag-results">
                  <div className="rag-results-heading"><div><p className="rag-kicker">SEARCH RESULTS</p><h3>{queryResult.evidence.length ? queryResult.evidence.length + " relevant passage" + (queryResult.evidence.length === 1 ? "" : "s") + " found" : "No matching passages found"}</h3></div><span className="rag-mode-pill">Lexical retrieval</span></div>
                  <p className="rag-result-explainer">{queryResult.note}</p>
                  {queryResult.evidence.map((item, index) => {
                    const expanded = expandedEvidence.includes(item.evidence_id);
                    return <article className="rag-evidence-card" key={item.evidence_id}>
                      <div className="rag-evidence-top"><span className="rag-evidence-number">0{index + 1}</span><div><strong>{item.title}</strong><small>Characters {item.start_char.toLocaleString()}–{item.end_char.toLocaleString()}</small></div><span className="rag-score">{(item.score * 100).toFixed(0)}<small>match</small></span></div>
                      <p className={expanded ? "rag-evidence-text expanded" : "rag-evidence-text"}>{item.text}</p>
                      <div className="rag-evidence-actions"><button onClick={() => toggleEvidence(item.evidence_id)}>{expanded ? "Show less" : "Read full passage"}</button>{safeHttpUrl(item.source_uri) && <a href={safeHttpUrl(item.source_uri)} target="_blank" rel="noreferrer">Open source ↗</a>}</div>
                      <div className="rag-evidence-feedback"><span>Was this passage useful?</span><button disabled={busy !== ""} onClick={() => void sendFeedback("helpful", item)}>Useful</button><button disabled={busy !== ""} onClick={() => void sendFeedback("unhelpful", item)}>Not useful</button></div>
                    </article>;
                  })}
                  <p className="rag-disclaimer">These are retrieved source passages, not an AI-generated answer. Similarity scores indicate ranking strength, not factual certainty. NEXUS does not currently have a hosted answer-generation provider connected.</p>
                </div>
              )}
            </section>
          )}
        </div>
      </section>

      <footer className="rag-footer"><span>NEXUS Ω · RAG STUDIO</span><span>Evidence first. Clear by design.</span><a href="/rag-operator">Advanced operator controls ↗</a></footer>
    </main>
  );
}

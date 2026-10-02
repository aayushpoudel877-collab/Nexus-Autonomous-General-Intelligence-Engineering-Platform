"use client";

import { FormEvent, useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
type Project = { id: string; name: string };
type Model = { id: string; name: string; version: string; status: string };
type Comparison = {
  id: string; baseline_model_id: string; candidate_model_id: string;
  deltas: Record<string, number>; status: "passed" | "needs_improvement";
  summary: string; created_at: string;
};

async function request(path: string, init?: RequestInit) {
  const response = await fetch(API + path, {
    ...init, credentials: "include",
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? ("Request failed (" + response.status + ")"));
  }
  return response.json();
}

export default function BenchmarksPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [comparisons, setComparisons] = useState<Comparison[]>([]);
  const [projectId, setProjectId] = useState("");
  const [baselineId, setBaselineId] = useState("");
  const [candidateId, setCandidateId] = useState("");
  const [baselineText, setBaselineText] = useState('{"accuracy":0.80,"loss":0.42}');
  const [candidateText, setCandidateText] = useState('{"accuracy":0.86,"loss":0.35}');
  const [criteriaText, setCriteriaText] = useState('{"accuracy":{"direction":"maximize","minimum_improvement":0.02},"loss":{"direction":"minimize","minimum_improvement":0.01}}');
  const [summary, setSummary] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    void request("/workbench/projects").then((rows: Project[]) => {
      setProjects(rows);
      if (rows.length) setProjectId(rows[0].id);
    }).catch((e) => setError(e instanceof Error ? e.message : "Could not load projects."));
  }, []);

  useEffect(() => {
    if (!projectId) { setModels([]); setComparisons([]); return; }
    setBaselineId(""); setCandidateId("");
    void Promise.all([
      request("/ml/projects/" + projectId + "/models"),
      request("/benchmarks/projects/" + projectId + "/comparisons"),
    ]).then(([modelRows, comparisonRows]) => {
      setModels(modelRows as Model[]);
      setComparisons(comparisonRows as Comparison[]);
    }).catch((e) => setError(e instanceof Error ? e.message : "Could not load comparisons."));
  }, [projectId]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!projectId || !baselineId || !candidateId || saving) return;
    setSaving(true); setError("");
    try {
      const row = await request("/benchmarks/projects/" + projectId + "/comparisons", {
        method: "POST",
        body: JSON.stringify({
          baseline_model_id: baselineId, candidate_model_id: candidateId,
          baseline_metrics: JSON.parse(baselineText), candidate_metrics: JSON.parse(candidateText),
          criteria: JSON.parse(criteriaText), summary,
        }),
      }) as Comparison;
      setComparisons((current) => [row, ...current]); setSummary("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not record comparison.");
    } finally { setSaving(false); }
  }

  function modelLabel(id: string) {
    const model = models.find((item) => item.id === id);
    return model ? model.name + " (" + model.version + ")" : id;
  }

  return <main className="shell">
    <section className="hero">
      <p className="eyebrow">NEXUS-Ω / PHASE 8</p>
      <h1>Continuous Improvement Benchmarks</h1>
      <p className="lead">Compare a candidate model with a baseline using explicit directional metric thresholds. Metrics are caller-reported: this records and checks evidence but does not execute models or independently verify the reported results.</p>
      <p><a href="/">Home</a> · <a href="/workbench">AI Workbench</a> · <a href="/ml-lifecycle">ML Lifecycle</a> · <a href="/multimodal">Multimodal Catalog</a></p>
    </section>
    {error && <p role="alert" style={{ marginTop: 18 }}>{error}</p>}
    <section style={{ marginTop: 24 }}>
      <label>Workbench project <select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
        <option value="">Select a project</option>
        {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select></label>
    </section>
    {projectId && <section className="grid" style={{ alignItems: "start", marginTop: 24 }}>
      <article>
        <h2>Record comparison</h2>
        {models.filter((m) => m.status !== "archived").length < 2 && <p>Register at least two non-archived models in ML Lifecycle first.</p>}
        <form onSubmit={submit} style={{ display: "grid", gap: 10 }}>
          <label>Baseline model <select required value={baselineId} onChange={(e) => setBaselineId(e.target.value)}>
            <option value="">Select baseline</option>
            {models.filter((m) => m.status !== "archived").map((m) => <option key={m.id} value={m.id}>{m.name} ({m.version})</option>)}
          </select></label>
          <label>Candidate model <select required value={candidateId} onChange={(e) => setCandidateId(e.target.value)}>
            <option value="">Select candidate</option>
            {models.filter((m) => m.status !== "archived").map((m) => <option key={m.id} value={m.id}>{m.name} ({m.version})</option>)}
          </select></label>
          <label>Baseline metrics (JSON) <textarea required rows={4} value={baselineText} onChange={(e) => setBaselineText(e.target.value)} /></label>
          <label>Candidate metrics (JSON) <textarea required rows={4} value={candidateText} onChange={(e) => setCandidateText(e.target.value)} /></label>
          <label>Criteria (JSON) <textarea required rows={4} value={criteriaText} onChange={(e) => setCriteriaText(e.target.value)} /></label>
          <label>Notes (optional) <textarea rows={3} maxLength={12000} value={summary} onChange={(e) => setSummary(e.target.value)} /></label>
          <button type="submit" disabled={saving || !baselineId || !candidateId || baselineId === candidateId}>{saving ? "Recording…" : "Record comparison"}</button>
        </form>
      </article>
      <article>
        <h2>Comparison history</h2>
        {comparisons.length === 0 ? <p>No comparisons recorded for this project yet.</p> :
          <div style={{ display: "grid", gap: 12 }}>{comparisons.map((c) => <div key={c.id} style={{ border: "1px solid var(--border, #d8dee8)", borderRadius: 12, padding: 14 }}>
            <p className="eyebrow">{c.status.replaceAll("_", " ")}</p>
            <h3>{modelLabel(c.baseline_model_id)} → {modelLabel(c.candidate_model_id)}</h3>
            <p>Metric deltas: <code>{JSON.stringify(c.deltas)}</code></p>
            {c.summary && <p>{c.summary}</p>}
            <small>{new Date(c.created_at).toLocaleString()}</small>
          </div>)}</div>}
      </article>
    </section>}
  </main>;
}

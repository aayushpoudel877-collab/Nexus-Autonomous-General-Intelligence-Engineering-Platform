"use client";

import { FormEvent, useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

type Project = { id: string; name: string };
type Run = {
  id: string; project_id: string; dataset_id: string | null; name: string;
  algorithm: string; status: string; metrics: Record<string, number | string>;
  error_summary: string; started_at: string | null; finished_at: string | null;
};
type Model = {
  id: string; project_id: string; source_training_run_id: string | null;
  source_experiment_id: string | null; name: string; version: string;
  framework: string; artifact_uri: string | null; status: string;
  metrics: Record<string, number | string>; approval_note: string;
};
type Evaluation = {
  id: string; model_id: string; evaluator: string; status: string;
  metrics: Record<string, number | string>; criteria: Record<string, number | string | boolean>;
  summary: string;
};

async function request(path: string, init?: RequestInit) {
  const response = await fetch(`${API}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed (${response.status})`);
  }
  if (response.status === 204) return null;
  return response.json();
}

export default function MLLifecyclePage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [runs, setRuns] = useState<Run[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [selectedModelId, setSelectedModelId] = useState("");
  const [evaluations, setEvaluations] = useState<Evaluation[]>([]);
  const [runName, setRunName] = useState("");
  const [algorithm, setAlgorithm] = useState("baseline");
  const [modelName, setModelName] = useState("");
  const [modelVersion, setModelVersion] = useState("1.0.0");
  const [framework, setFramework] = useState("unknown");
  const [artifactUri, setArtifactUri] = useState("");
  const [approvalNote, setApprovalNote] = useState("");
  const [evaluator, setEvaluator] = useState("held-out validation");
  const [evaluationSummary, setEvaluationSummary] = useState("");
  const [evaluationMetrics, setEvaluationMetrics] = useState('{"accuracy": 0.95}');
  const [evaluationCriteria, setEvaluationCriteria] = useState('{"accuracy": {"min": 0.9}}');
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  async function loadProjects() {
    setLoading(true);
    try {
      const rows = (await request("/workbench/projects")) as Project[];
      setProjects(rows);
      if (!projectId && rows.length) setProjectId(rows[0].id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load projects.");
    } finally {
      setLoading(false);
    }
  }

  async function loadProjectData(id: string) {
    if (!id) { setRuns([]); setModels([]); setEvaluations([]); return; }
    try {
      const [runRows, modelRows] = await Promise.all([
        request(`/ml/projects/${id}/training-runs`) as Promise<Run[]>,
        request(`/ml/projects/${id}/models`) as Promise<Model[]>,
      ]);
      setRuns(runRows);
      setModels(modelRows);
      const chosen = modelRows.find((item) => item.id === selectedModelId) ?? modelRows[0];
      setSelectedModelId(chosen?.id ?? "");
      setEvaluations(chosen ? await request(`/ml/models/${chosen.id}/evaluations`) : []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load ML lifecycle data.");
    }
  }

  useEffect(() => { void loadProjects(); }, []);
  useEffect(() => { void loadProjectData(projectId); }, [projectId]);

  async function createRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!projectId || saving || runName.trim().length < 2) return;
    setSaving(true); setError("");
    try {
      const run = await request(`/ml/projects/${projectId}/training-runs`, {
        method: "POST", body: JSON.stringify({ name: runName.trim(), algorithm }),
      }) as Run;
      setRuns((current) => [run, ...current]);
      setRunName("");
    } catch (e) { setError(e instanceof Error ? e.message : "Could not create run."); }
    finally { setSaving(false); }
  }

  async function updateRun(run: Run, status: string) {
    setError("");
    try {
      const updated = await request(`/ml/training-runs/${run.id}`, {
        method: "PATCH", body: JSON.stringify({ status }),
      }) as Run;
      setRuns((current) => current.map((item) => item.id === updated.id ? updated : item));
    } catch (e) { setError(e instanceof Error ? e.message : "Could not update run."); }
  }

  async function registerModel(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const source = runs.find((run) => run.status === "succeeded");
    if (!source || saving || modelName.trim().length < 2) return;
    setSaving(true); setError("");
    try {
      const model = await request(`/ml/projects/${projectId}/models`, {
        method: "POST",
        body: JSON.stringify({
          name: modelName.trim(), version: modelVersion.trim(), framework: framework.trim() || "unknown",
          artifact_uri: artifactUri.trim() || null, source_training_run_id: source.id,
        }),
      }) as Model;
      setModels((current) => [model, ...current]);
      setSelectedModelId(model.id);
      setEvaluations([]);
      setModelName(""); setArtifactUri("");
    } catch (e) { setError(e instanceof Error ? e.message : "Could not register model."); }
    finally { setSaving(false); }
  }

  async function runAutomatedEvaluation() {
    if (!selectedModelId || saving) return;
    setSaving(true); setError("");
    try {
      const item = await request(`/ml/models/${selectedModelId}/evaluations/run`, {
        method: "POST",
        body: JSON.stringify({
          summary: evaluationSummary.trim(),
          metrics: JSON.parse(evaluationMetrics),
          criteria: JSON.parse(evaluationCriteria),
        }),
      }) as Evaluation;
      setEvaluations((current) => [item, ...current]);
      setEvaluationSummary("");
    } catch (e) { setError(e instanceof Error ? e.message : "Could not run automated evaluation."); }
    finally { setSaving(false); }
  }

  async function createEvaluation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedModelId || saving || evaluator.trim().length < 2) return;
    setSaving(true); setError("");
    try {
      const item = await request(`/ml/models/${selectedModelId}/evaluations`, {
        method: "POST",
        body: JSON.stringify({
          evaluator: evaluator.trim(),
          summary: evaluationSummary.trim(),
          metrics: JSON.parse(evaluationMetrics),
          criteria: JSON.parse(evaluationCriteria),
        }),
      }) as Evaluation;
      setEvaluations((current) => [item, ...current]);
      setEvaluationSummary("");
    } catch (e) { setError(e instanceof Error ? e.message : "Could not create evaluation."); }
    finally { setSaving(false); }
  }

  async function updateEvaluation(item: Evaluation, status: string) {
    setError("");
    try {
      const updated = await request(`/ml/evaluations/${item.id}`, {
        method: "PATCH", body: JSON.stringify({ status }),
      }) as Evaluation;
      setEvaluations((current) => current.map((entry) => entry.id === updated.id ? updated : entry));
    } catch (e) { setError(e instanceof Error ? e.message : "Could not update evaluation."); }
  }

  async function updateModel(model: Model, status: string) {
    setError("");
    try {
      const updated = await request(`/ml/models/${model.id}`, {
        method: "PATCH", body: JSON.stringify({ status, ...(status === "approved" ? { approval_note: approvalNote.trim() } : {}) }),
      }) as Model;
      setModels((current) => current.map((item) => item.id === updated.id ? updated : item));
      if (status === "approved") setApprovalNote("");
    } catch (e) { setError(e instanceof Error ? e.message : "Could not update model."); }
  }

  const selectedModel = models.find((item) => item.id === selectedModelId);

  return (
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">NEXUS-Ω / PHASE 6</p>
        <h1>ML Lifecycle Control</h1>
        <p className="lead">Track run metadata, record evaluations and require a passing evaluation plus a human review note before approving a model. This workspace does not execute training or deploy artifacts.</p>
        <p><a href="/">Home</a> · <a href="/workbench">AI Workbench</a> · <a href="/research">Research Planner</a></p>
      </section>

      {error && <p role="alert" style={{ marginTop: 18 }}>{error}</p>}
      <section style={{ marginTop: 24 }}>
        <label>Workbench project{" "}
          <select value={projectId} onChange={(event) => setProjectId(event.target.value)}>
            <option value="">Select a project</option>
            {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
          </select>
        </label>
        {loading && <p>Loading projects…</p>}
        {!loading && projects.length === 0 && <p>Create a project in the <a href="/workbench">AI Workbench</a> before using ML lifecycle tracking.</p>}
      </section>

      <section className="grid" style={{ alignItems: "start", marginTop: 24 }}>
        <article>
          <h2>Training runs</h2>
          <form onSubmit={createRun} style={{ display: "grid", gap: 10 }}>
            <label>Run name<input required minLength={2} maxLength={180} value={runName} onChange={(event) => setRunName(event.target.value)} /></label>
            <label>Algorithm / recipe<input required maxLength={120} value={algorithm} onChange={(event) => setAlgorithm(event.target.value)} /></label>
            <button disabled={!projectId || saving || runName.trim().length < 2}>{saving ? "Saving…" : "Record training run"}</button>
          </form>
          <div style={{ display: "grid", gap: 12, marginTop: 18 }}>
            {runs.map((run) => <div key={run.id} style={{ border: "1px solid var(--border, #d8dee8)", borderRadius: 12, padding: 14 }}>
              <strong>{run.name}</strong><p>{run.algorithm} · {run.status}</p>
              <small>Run ID: {run.id}</small>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
                {run.status === "queued" && <button onClick={() => void updateRun(run, "running")}>Mark running</button>}
                {run.status === "running" && <><button onClick={() => void updateRun(run, "succeeded")}>Mark succeeded</button><button onClick={() => void updateRun(run, "failed")}>Mark failed</button></>}
                {(run.status === "queued" || run.status === "running") && <button onClick={() => void updateRun(run, "cancelled")}>Cancel</button>}
              </div>
            </div>)}
            {!runs.length && <p>No training runs recorded yet.</p>}
          </div>
        </article>

        <article>
          <h2>Model registry</h2>
          <form onSubmit={registerModel} style={{ display: "grid", gap: 10 }}>
            <label>Model name<input required minLength={2} maxLength={180} value={modelName} onChange={(event) => setModelName(event.target.value)} /></label>
            <label>Version<input required maxLength={80} value={modelVersion} onChange={(event) => setModelVersion(event.target.value)} /></label>
            <label>Framework<input maxLength={80} value={framework} onChange={(event) => setFramework(event.target.value)} /></label>
            <label>Artifact URI (metadata only)<input maxLength={2048} value={artifactUri} onChange={(event) => setArtifactUri(event.target.value)} placeholder="Optional artifact reference" /></label>
            <button disabled={!projectId || saving || !runs.some((run) => run.status === "succeeded") || modelName.trim().length < 2}>Register from successful run</button>
          </form>
          <div style={{ display: "grid", gap: 12, marginTop: 18 }}>
            {models.map((model) => <div key={model.id} style={{ border: "1px solid var(--border, #d8dee8)", borderRadius: 12, padding: 14 }}>
              <button type="button" onClick={() => { setSelectedModelId(model.id); void request(`/ml/models/${model.id}/evaluations`).then(setEvaluations).catch((e) => setError(e instanceof Error ? e.message : "Could not load evaluations.")); }} aria-pressed={selectedModelId === model.id}><strong>{model.name} v{model.version}</strong></button>
              <p>{model.framework} · {model.status}</p>
              {model.status === "candidate" && <button onClick={() => void updateModel(model, "validated")}>Validate model</button>}
              {model.status === "validated" && <div style={{ display: "grid", gap: 8 }}>
                <label>Human approval note<textarea rows={2} value={approvalNote} onChange={(event) => setApprovalNote(event.target.value)} /></label>
                <button disabled={!approvalNote.trim()} onClick={() => void updateModel(model, "approved")}>Approve model</button>
              </div>}
              {(model.status === "candidate" || model.status === "validated" || model.status === "approved") && <button style={{ marginLeft: 8 }} onClick={() => void updateModel(model, "archived")}>Archive</button>}
            </div>)}
            {!models.length && <p>No registered models yet. Complete a run, then register its model metadata.</p>}
          </div>
        </article>
      </section>

      {selectedModel && <section style={{ marginTop: 28 }}>
        <h2>Evaluations for {selectedModel.name} v{selectedModel.version}</h2>
        <form onSubmit={createEvaluation} style={{ display: "grid", gap: 10, maxWidth: 680 }}>
          <label>Evaluator<input required minLength={2} maxLength={120} value={evaluator} onChange={(event) => setEvaluator(event.target.value)} /></label>
          <label>Recorded metrics (JSON)<textarea required rows={2} value={evaluationMetrics} onChange={(event) => setEvaluationMetrics(event.target.value)} /></label>
          <label>Pass criteria (JSON; each metric needs min and/or max)<textarea required rows={2} value={evaluationCriteria} onChange={(event) => setEvaluationCriteria(event.target.value)} /></label>
          <label>Evaluation plan / notes<textarea rows={3} maxLength={12000} value={evaluationSummary} onChange={(event) => setEvaluationSummary(event.target.value)} /></label>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button disabled={saving}>Add evaluation evidence</button>
            <button type="button" disabled={saving} onClick={() => void runAutomatedEvaluation()}>Run deterministic evaluator</button>
          </div>
          <small>The deterministic evaluator validates the submitted metrics against the submitted criteria and writes a terminal pass/fail result; it does not execute the model or independently measure it.</small>
        </form>
        <div style={{ display: "grid", gap: 12, marginTop: 16 }}>
          {evaluations.map((item) => <div key={item.id} style={{ border: "1px solid var(--border, #d8dee8)", borderRadius: 12, padding: 14 }}>
            <strong>{item.evaluator}</strong><p>{item.status}</p><p>{item.summary || "No summary recorded."}</p><small>Metrics: {JSON.stringify(item.metrics)} · Criteria: {JSON.stringify(item.criteria)}</small>
            {item.status === "queued" && <button onClick={() => void updateEvaluation(item, "running")}>Start evaluation</button>}
            {item.status === "running" && <><button onClick={() => void updateEvaluation(item, "passed")}>Mark passed</button><button style={{ marginLeft: 8 }} onClick={() => void updateEvaluation(item, "failed")}>Mark failed</button></>}
          </div>)}
          {!evaluations.length && <p>No evaluation records yet.</p>}
        </div>
      </section>}
    </main>
  );
}

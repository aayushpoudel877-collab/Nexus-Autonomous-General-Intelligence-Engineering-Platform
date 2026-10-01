"use client";

import { FormEvent, useEffect, useState } from "react";
import { useParams } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

type Dataset = {
  id: string;
  name: string;
  description: string;
  row_count: number | null;
  source_uri: string | null;
};
type Experiment = {
  id: string;
  name: string;
  algorithm: string;
  status: string;
  dataset_id: string | null;
  parameters: Record<string, unknown>;
  metrics: Record<string, unknown>;
  notes: string;
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
  return response.json();
}

export default function WorkbenchProjectPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [datasetName, setDatasetName] = useState("");
  const [datasetSource, setDatasetSource] = useState("");
  const [experimentName, setExperimentName] = useState("");
  const [algorithm, setAlgorithm] = useState("baseline");
  const [datasetId, setDatasetId] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [datasetRows, experimentRows] = await Promise.all([
        request(`/workbench/projects/${projectId}/datasets`),
        request(`/workbench/projects/${projectId}/experiments`),
      ]);
      setDatasets(datasetRows);
      setExperiments(experimentRows);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load project workspace.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (projectId) void load();
  }, [projectId]);

  async function createDataset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving || datasetName.trim().length < 2) return;
    setSaving(true);
    setError("");
    try {
      const dataset = await request(`/workbench/projects/${projectId}/datasets`, {
        method: "POST",
        body: JSON.stringify({
          name: datasetName.trim(),
          source_uri: datasetSource.trim() || null,
          description: "",
        }),
      });
      setDatasets((current) => [dataset, ...current]);
      setDatasetName("");
      setDatasetSource("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create dataset.");
    } finally {
      setSaving(false);
    }
  }

  async function createExperiment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving || experimentName.trim().length < 2) return;
    setSaving(true);
    setError("");
    try {
      const experiment = await request(`/workbench/projects/${projectId}/experiments`, {
        method: "POST",
        body: JSON.stringify({
          name: experimentName.trim(),
          algorithm: algorithm.trim() || "baseline",
          dataset_id: datasetId || null,
          parameters: {},
          notes: "",
        }),
      });
      setExperiments((current) => [experiment, ...current]);
      setExperimentName("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create experiment.");
    } finally {
      setSaving(false);
    }
  }

  async function setExperimentStatus(experiment: Experiment, status: string) {
    setError("");
    try {
      const updated = await request(`/workbench/experiments/${experiment.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      setExperiments((current) =>
        current.map((item) => item.id === updated.id ? updated : item)
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update experiment.");
    }
  }

  return (
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">NEXUS-Ω / PROJECT WORKSPACE</p>
        <h1>Datasets & experiments</h1>
        <p className="lead">Keep data references, experiment parameters and recorded metrics organized.</p>
        <p><a href="/workbench">← All projects</a> · <a href="/">Home</a></p>
      </section>

      {error && <p role="alert" style={{ marginTop: 18 }}>{error}</p>}
      {loading ? <p>Loading workspace…</p> : (
        <section className="grid" style={{ alignItems: "start", marginTop: 28 }}>
          <article>
            <h2>Datasets</h2>
            <form onSubmit={createDataset} style={{ display: "grid", gap: 12 }}>
              <label>Dataset name
                <input required minLength={2} maxLength={180} value={datasetName} onChange={(event) => setDatasetName(event.target.value)} />
              </label>
              <label>Source URI (optional)
                <input maxLength={2048} value={datasetSource} onChange={(event) => setDatasetSource(event.target.value)} placeholder="s3://bucket/path or https://…" />
              </label>
              <button type="submit" disabled={saving || datasetName.trim().length < 2}>{saving ? "Saving…" : "Add dataset metadata"}</button>
            </form>
            <div style={{ display: "grid", gap: 12, marginTop: 20 }}>
              {datasets.length === 0 ? <p>No dataset metadata registered yet.</p> : datasets.map((dataset) => (
                <div key={dataset.id} style={{ border: "1px solid var(--border, #d8dee8)", borderRadius: 12, padding: 14 }}>
                  <h3>{dataset.name}</h3>
                  <p>{dataset.row_count == null ? "Row count not recorded" : `${dataset.row_count.toLocaleString()} rows`}</p>
                  {dataset.source_uri && <p><small>{dataset.source_uri}</small></p>}
                </div>
              ))}
            </div>
          </article>

          <article>
            <h2>Experiments</h2>
            <form onSubmit={createExperiment} style={{ display: "grid", gap: 12 }}>
              <label>Experiment name
                <input required minLength={2} maxLength={180} value={experimentName} onChange={(event) => setExperimentName(event.target.value)} placeholder="e.g. Logistic regression baseline" />
              </label>
              <label>Algorithm or approach
                <input maxLength={120} value={algorithm} onChange={(event) => setAlgorithm(event.target.value)} />
              </label>
              <label>Dataset (optional)
                <select value={datasetId} onChange={(event) => setDatasetId(event.target.value)}>
                  <option value="">No dataset selected</option>
                  {datasets.map((dataset) => <option key={dataset.id} value={dataset.id}>{dataset.name}</option>)}
                </select>
              </label>
              <button type="submit" disabled={saving || experimentName.trim().length < 2}>{saving ? "Saving…" : "Plan experiment"}</button>
            </form>
            <div style={{ display: "grid", gap: 12, marginTop: 20 }}>
              {experiments.length === 0 ? <p>No experiments planned yet.</p> : experiments.map((experiment) => (
                <div key={experiment.id} style={{ border: "1px solid var(--border, #d8dee8)", borderRadius: 12, padding: 14 }}>
                  <h3>{experiment.name}</h3>
                  <p>{experiment.algorithm} · <strong>{experiment.status}</strong></p>
                  {Object.keys(experiment.metrics).length > 0 && <pre>{JSON.stringify(experiment.metrics, null, 2)}</pre>}
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                    {experiment.status === "planned" && <button type="button" onClick={() => setExperimentStatus(experiment, "queued")}>Queue</button>}
                    {["planned", "queued"].includes(experiment.status) && <button type="button" onClick={() => setExperimentStatus(experiment, "running")}>Mark running</button>}
                    {experiment.status === "running" && <>
                      <button type="button" onClick={() => setExperimentStatus(experiment, "succeeded")}>Mark succeeded</button>
                      <button type="button" onClick={() => setExperimentStatus(experiment, "failed")}>Mark failed</button>
                    </>}
                  </div>
                </div>
              ))}
            </div>
          </article>
        </section>
      )}
    </main>
  );
}

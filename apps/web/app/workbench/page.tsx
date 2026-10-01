"use client";

import { FormEvent, useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

type Project = {
  id: string;
  name: string;
  description: string;
  task_type: string;
  status: string;
  created_at: string;
};

const taskTypes = [
  ["classification", "Classification"],
  ["regression", "Regression"],
  ["clustering", "Clustering"],
  ["nlp", "Natural language processing"],
  ["computer_vision", "Computer vision"],
  ["forecasting", "Forecasting"],
  ["other", "Other"],
];

export default function WorkbenchPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [taskType, setTaskType] = useState("classification");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

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

  async function loadProjects() {
    setLoading(true);
    setError("");
    try {
      setProjects(await request("/workbench/projects"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load projects.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadProjects();
  }, []);

  async function createProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving || name.trim().length < 2) return;
    setSaving(true);
    setError("");
    try {
      const project = await request("/workbench/projects", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim(),
          task_type: taskType,
        }),
      });
      setProjects((current) => [project, ...current]);
      setName("");
      setDescription("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create project.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">NEXUS-Ω / PHASE 4</p>
        <h1>AI Engineering Workbench</h1>
        <p className="lead">
          Organize research projects, dataset metadata and reproducible model experiments.
        </p>
        <p><a href="/">Home</a> · <a href="/lms">LMS</a> · <a href="/tutor">AI Tutor</a></p>
      </section>

      <section className="grid" style={{ alignItems: "start", marginTop: 28 }}>
        <article>
          <h2>Start a project</h2>
          <form onSubmit={createProject} style={{ display: "grid", gap: 12 }}>
            <label>
              Project name
              <input
                required
                minLength={2}
                maxLength={180}
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="e.g. Nepali text classification"
              />
            </label>
            <label>
              Problem type
              <select value={taskType} onChange={(event) => setTaskType(event.target.value)}>
                {taskTypes.map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </label>
            <label>
              Research objective
              <textarea
                maxLength={12000}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="What are you trying to measure or learn?"
                rows={4}
              />
            </label>
            <button type="submit" disabled={saving || name.trim().length < 2}>
              {saving ? "Creating…" : "Create project"}
            </button>
          </form>
        </article>

        <article>
          <h2>Your projects</h2>
          {error && <p role="alert">{error}</p>}
          {loading ? <p>Loading projects…</p> : projects.length === 0 ? (
            <p>No projects yet. Create one to start tracking datasets and experiments.</p>
          ) : (
            <div style={{ display: "grid", gap: 14 }}>
              {projects.map((project) => (
                <div key={project.id} style={{ border: "1px solid var(--border, #d8dee8)", borderRadius: 12, padding: 16 }}>
                  <p className="eyebrow">{project.task_type.replaceAll("_", " ")}</p>
                  <h3>{project.name}</h3>
                  <p>{project.description || "No objective added yet."}</p>
                  <small>{project.status} · Created {new Date(project.created_at).toLocaleDateString()}</small>
                  <p><a href={`/workbench/projects/${project.id}`}>Open project workspace →</a></p>
                </div>
              ))}
            </div>
          )}
        </article>
      </section>
    </main>
  );
}

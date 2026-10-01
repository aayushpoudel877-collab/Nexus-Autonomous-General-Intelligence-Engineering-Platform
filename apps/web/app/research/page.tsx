"use client";

import { FormEvent, useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

type Task = {
  id: string;
  title: string;
  description: string;
  task_type: string;
  status: string;
  depends_on: string[];
  output_summary: string;
};
type Plan = {
  id: string;
  title: string;
  goal: string;
  status: string;
  workbench_project_id: string | null;
  tasks: Task[];
};

const taskTypes = [
  ["literature_review", "Literature review"],
  ["data_collection", "Data collection"],
  ["data_cleaning", "Data cleaning"],
  ["analysis", "Analysis"],
  ["experiment", "Experiment"],
  ["evaluation", "Evaluation"],
  ["report", "Report"],
  ["other", "Other"],
];

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

export default function ResearchPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [activePlan, setActivePlan] = useState("");
  const [title, setTitle] = useState("");
  const [goal, setGoal] = useState("");
  const [taskTitle, setTaskTitle] = useState("");
  const [taskDescription, setTaskDescription] = useState("");
  const [taskType, setTaskType] = useState("analysis");
  const [dependencies, setDependencies] = useState<string[]>([]);
  const [outputDrafts, setOutputDrafts] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const active = plans.find((plan) => plan.id === activePlan) ?? plans[0];

  async function loadPlans() {
    setLoading(true);
    setError("");
    try {
      const rows = (await request("/research/plans")) as Plan[];
      setPlans(rows);
      if (!activePlan && rows.length) setActivePlan(rows[0].id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load research plans.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadPlans();
  }, []);

  async function createPlan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving || title.trim().length < 3 || goal.trim().length < 10) return;
    setSaving(true);
    setError("");
    try {
      const plan = (await request("/research/plans", {
        method: "POST",
        body: JSON.stringify({ title: title.trim(), goal: goal.trim() }),
      })) as Plan;
      setPlans((current) => [plan, ...current]);
      setActivePlan(plan.id);
      setTitle("");
      setGoal("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create research plan.");
    } finally {
      setSaving(false);
    }
  }

  async function createTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!active || saving || taskTitle.trim().length < 3) return;
    setSaving(true);
    setError("");
    try {
      const task = (await request(`/research/plans/${active.id}/tasks`, {
        method: "POST",
        body: JSON.stringify({
          title: taskTitle.trim(),
          description: taskDescription.trim(),
          task_type: taskType,
          depends_on: dependencies,
        }),
      })) as Task;
      setPlans((current) => current.map((plan) =>
        plan.id === active.id
          ? { ...plan, status: "active", tasks: [...plan.tasks, task] }
          : plan
      ));
      setTaskTitle("");
      setTaskDescription("");
      setDependencies([]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not add research task.");
    } finally {
      setSaving(false);
    }
  }

  async function updateTask(task: Task, status: string) {
    if (!active) return;
    setError("");
    try {
      const updated = (await request(`/research/tasks/${task.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          status,
          output_summary: outputDrafts[task.id] ?? task.output_summary,
        }),
      })) as Task;
      setPlans((current) => current.map((plan) =>
        plan.id === active.id
          ? { ...plan, tasks: plan.tasks.map((item) => item.id === updated.id ? updated : item) }
          : plan
      ));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update task.");
    }
  }

  return (
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">NEXUS-Ω / PHASE 5</p>
        <h1>Autonomous Research Planner</h1>
        <p className="lead">
          Turn a research goal into a dependency-aware task graph. Track readiness and record findings as work progresses.
        </p>
        <p><a href="/">Home</a> · <a href="/workbench">AI Workbench</a> · <a href="/tutor">AI Tutor</a></p>
      </section>

      {error && <p role="alert" style={{ marginTop: 18 }}>{error}</p>}

      <section className="grid" style={{ alignItems: "start", marginTop: 28 }}>
        <article>
          <h2>New research plan</h2>
          <form onSubmit={createPlan} style={{ display: "grid", gap: 12 }}>
            <label>Plan title
              <input required minLength={3} maxLength={200} value={title} onChange={(event) => setTitle(event.target.value)} placeholder="e.g. Evaluate low-resource Nepali NLP" />
            </label>
            <label>Research goal
              <textarea required minLength={10} maxLength={12000} rows={4} value={goal} onChange={(event) => setGoal(event.target.value)} placeholder="State the research question, constraints and desired evidence." />
            </label>
            <button type="submit" disabled={saving || title.trim().length < 3 || goal.trim().length < 10}>
              {saving ? "Saving…" : "Create plan"}
            </button>
          </form>

          <h2 style={{ marginTop: 28 }}>Research plans</h2>
          {loading ? <p>Loading plans…</p> : plans.length === 0 ? <p>No plans yet. Create one to begin breaking down the research goal.</p> : (
            <div style={{ display: "grid", gap: 10 }}>
              {plans.map((plan) => (
                <button key={plan.id} type="button" onClick={() => setActivePlan(plan.id)} aria-pressed={active?.id === plan.id} style={{ textAlign: "left", padding: 14, borderRadius: 12, border: active?.id === plan.id ? "2px solid currentColor" : "1px solid var(--border, #d8dee8)" }}>
                  <strong>{plan.title}</strong>
                  <p>{plan.tasks.length} tasks · {plan.status}</p>
                </button>
              ))}
            </div>
          )}
        </article>

        <article>
          {!active ? <><h2>Task graph</h2><p>Select or create a research plan to manage its tasks.</p></> : <>
            <p className="eyebrow">{active.status.toUpperCase()} · {active.tasks.length} TASKS</p>
            <h2>{active.title}</h2>
            <p>{active.goal}</p>

            <h3>Add a task</h3>
            <form onSubmit={createTask} style={{ display: "grid", gap: 12 }}>
              <label>Task title
                <input required minLength={3} maxLength={200} value={taskTitle} onChange={(event) => setTaskTitle(event.target.value)} placeholder="e.g. Collect benchmark datasets" />
              </label>
              <label>Task type
                <select value={taskType} onChange={(event) => setTaskType(event.target.value)}>
                  {taskTypes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </label>
              <label>Description
                <textarea rows={3} maxLength={12000} value={taskDescription} onChange={(event) => setTaskDescription(event.target.value)} placeholder="Define expected output and completion criteria." />
              </label>
              {active.tasks.length > 0 && <fieldset style={{ border: "1px solid var(--border, #d8dee8)", borderRadius: 10, padding: 12 }}>
                <legend>Depends on (optional)</legend>
                {active.tasks.map((task) => <label key={task.id} style={{ display: "flex", gap: 8, margin: "8px 0" }}>
                  <input type="checkbox" checked={dependencies.includes(task.id)} onChange={(event) => setDependencies((current) => event.target.checked ? [...current, task.id] : current.filter((id) => id !== task.id))} />
                  {task.title} · {task.status}
                </label>)}
              </fieldset>}
              <button type="submit" disabled={saving || taskTitle.trim().length < 3}>{saving ? "Saving…" : "Add task"}</button>
            </form>

            <h3 style={{ marginTop: 28 }}>Task graph</h3>
            {active.tasks.length === 0 ? <p>No tasks yet. Add the first task to start the research workflow.</p> : (
              <div style={{ display: "grid", gap: 12 }}>
                {active.tasks.map((task, index) => {
                  const deps = task.depends_on.map((id) => active.tasks.find((item) => item.id === id)?.title ?? "Unknown task");
                  return <div key={task.id} style={{ border: "1px solid var(--border, #d8dee8)", borderRadius: 12, padding: 14 }}>
                    <p className="eyebrow">STEP {index + 1} · {task.task_type.replaceAll("_", " ")}</p>
                    <h3>{task.title}</h3>
                    <p>{task.description || "No description provided."}</p>
                    <p><strong>Status:</strong> {task.status}</p>
                    {deps.length > 0 && <p><strong>Depends on:</strong> {deps.join(", ")}</p>}
                    <label>Finding / output summary
                      <textarea rows={2} maxLength={12000} value={outputDrafts[task.id] ?? task.output_summary} onChange={(event) => setOutputDrafts((current) => ({ ...current, [task.id]: event.target.value }))} />
                    </label>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 10 }}>
                      {task.status === "planned" && <button type="button" onClick={() => updateTask(task, "ready")}>Mark ready</button>}
                      {task.status === "ready" && <button type="button" onClick={() => updateTask(task, "running")}>Start task</button>}
                      {task.status === "running" && <>
                        <button type="button" onClick={() => updateTask(task, "succeeded")}>Mark succeeded</button>
                        <button type="button" onClick={() => updateTask(task, "failed")}>Mark failed</button>
                      </>}
                      {(task.status === "blocked" || task.status === "failed") && <button type="button" onClick={() => updateTask(task, "ready")}>Retry / unblock</button>}
                      {!["succeeded", "cancelled"].includes(task.status) && <button type="button" onClick={() => updateTask(task, "cancelled")}>Cancel</button>}
                    </div>
                  </div>;
                })}
              </div>
            )}
          </>}
        </article>
      </section>
    </main>
  );
}

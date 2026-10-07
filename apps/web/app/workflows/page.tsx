"use client";

import { useEffect, useMemo, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

type Node = { id: string; node_key: string; title: string; node_type: string; depends_on: string[]; config: Record<string, unknown> };
type Workflow = { id: string; name: string; description: string; version: number; status: string; nodes: Node[] };
type Replay = { event_count: number; replay_checksum: string; projected_status: string | null; projected_nodes: Array<{ node_key: string; status: string }>; drifted: boolean };
type Run = { id: string; status: string; created_at: string; node_runs: Array<{ id: string; node_id: string; status: string; attempt: number; output_json: Record<string, unknown>; error_message: string }>; approvals: Array<{ id: string; node_run_id: string; status: string; prompt: string; decision_note: string }> };

async function request(path: string, init?: RequestInit) {
  const response = await fetch(`${API}${path}`, { ...init, credentials: "include", headers: { "Content-Type": "application/json", ...init?.headers } });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed (${response.status})`);
  }
  return response.json();
}

const sample = JSON.stringify([
  { node_key: "prepare", title: "Prepare", node_type: "checkpoint", depends_on: [], config: {} },
  { node_key: "review", title: "Human review", node_type: "approval", depends_on: ["prepare"], config: { prompt: "Approve the workflow to continue." } },
  { node_key: "complete", title: "Complete", node_type: "checkpoint", depends_on: ["review"], config: {} },
], null, 2);

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [activeWorkflow, setActiveWorkflow] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [nodes, setNodes] = useState(sample);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);\n  const [replays, setReplays] = useState<Record<string, Replay>>({});
  const active = useMemo(() => workflows.find((item) => item.id === activeWorkflow) ?? workflows[0], [workflows, activeWorkflow]);

  async function load() {
    try {
      const rows = (await request("/workflows")) as Workflow[];
      setWorkflows(rows);
      if (!activeWorkflow && rows[0]) setActiveWorkflow(rows[0].id);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not load workflows."); }
  }
  async function loadRuns(workflowId: string) {
    try { setRuns((await request(`/workflows/${workflowId}/runs`)) as Run[]); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not load runs."); }
  }
  useEffect(() => { void load(); }, []);
  useEffect(() => { if (active?.id) void loadRuns(active.id); }, [active?.id]);

  async function createWorkflow() {
    if (busy) return;
    setBusy(true); setError("");
    try {
      const parsed = JSON.parse(nodes);
      const created = (await request("/workflows", { method: "POST", body: JSON.stringify({ name, description, nodes: parsed }) })) as Workflow;
      setWorkflows((current) => [created, ...current]); setActiveWorkflow(created.id); setName(""); setDescription("");
    } catch (e) { setError(e instanceof Error ? e.message : "Workflow definition is invalid."); }
    finally { setBusy(false); }
  }
  async function startRun() {
    if (!active || busy) return;
    setBusy(true); setError("");
    try { await request(`/workflows/${active.id}/runs`, { method: "POST", body: JSON.stringify({ input_json: {} }) }); await loadRuns(active.id); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not start run."); }
    finally { setBusy(false); }
  }
  async function tick(runId: string) {
    if (!active || busy) return;
    setBusy(true); setError("");
    try { await request(`/workflows/${active.id}/runs/${runId}/tick`, { method: "POST" }); await loadRuns(active.id); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not tick run."); }
    finally { setBusy(false); }
  }
  async function cancel(runId: string) {
    if (!active || busy) return;
    setBusy(true); setError("");
    try { await request(`/workflows/${active.id}/runs/${runId}/cancel`, { method: "POST" }); await loadRuns(active.id); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not cancel run."); }
    finally { setBusy(false); }
  }

  async function replay(runId: string) {
    if (!active || busy) return;
    setBusy(true); setError("");
    try {
      const result = (await request(`/workflows/${active.id}/runs/${runId}/replay`)) as Replay;
      setReplays((current) => ({ ...current, [runId]: result }));
    } catch (e) { setError(e instanceof Error ? e.message : "Could not replay run."); }
    finally { setBusy(false); }
  }
\n  async function decide(run: Run, approval: Run["approvals"][number], status: "approved" | "rejected") {
    if (!active || busy) return;
    setBusy(true); setError("");
    try { await request(`/workflows/${active.id}/runs/${run.id}/approvals/${approval.id}`, { method: "POST", body: JSON.stringify({ status, note: status === "approved" ? "Approved from operator console." : "Rejected from operator console." }) }); await loadRuns(active.id); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not decide approval."); }
    finally { setBusy(false); }
  }

  return <main className="shell">
    <section className="hero">
      <p className="eyebrow">NEXUS-Ω / PHASE 25</p>
      <h1>Durable Autonomous Workflows</h1>
      <p className="lead">Coordinate durable workflows with retries, event history, and read-only deterministic replay checks.</p>
      <p><a href="/">Home</a> · <a href="/research">Research</a> · <a href="/execution">Execution</a> · <a href="/audit">Audit</a></p>
    </section>
    {error && <p role="alert" style={{ marginTop: 18 }}>{error}</p>}
    <section className="grid" style={{ alignItems: "start", marginTop: 28 }}>
      <article>
        <h2>Create workflow</h2>
        <label>Name<input value={name} onChange={(e) => setName(e.target.value)} placeholder="Research-to-evaluation pipeline" /></label>
        <label>Description<textarea rows={3} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What should this workflow coordinate?" /></label>
        <label>Nodes JSON<textarea rows={16} value={nodes} onChange={(e) => setNodes(e.target.value)} /></label>
        <button disabled={busy || name.trim().length < 3} onClick={() => void createWorkflow()}>Create workflow</button>
        <h2 style={{ marginTop: 26 }}>Definitions</h2>
        {workflows.length === 0 ? <p>No workflows yet.</p> : <div style={{ display: "grid", gap: 10 }}>{workflows.map((workflow) => <button key={workflow.id} type="button" onClick={() => setActiveWorkflow(workflow.id)} aria-pressed={active?.id === workflow.id} style={{ textAlign: "left", padding: 12 }}>{workflow.name}<br /><small>{workflow.nodes.length} nodes · v{workflow.version} · {workflow.status}</small></button>)}</div>}
      </article>
      <article>
        {!active ? <><h2>Runs</h2><p>Create or select a workflow first.</p></> : <>
          <p className="eyebrow">{active.name.toUpperCase()} · {active.nodes.length} NODES</p>
          <h2>{active.description || "Durable workflow"}</h2>
          <button disabled={busy} onClick={() => void startRun()}>Queue run</button>
          <h3 style={{ marginTop: 24 }}>Runs</h3>
          {runs.length === 0 ? <p>No runs yet.</p> : <div style={{ display: "grid", gap: 12 }}>{runs.map((run) => <div key={run.id} style={{ border: "1px solid var(--border, #d8dee8)", borderRadius: 12, padding: 14 }}>
            <p className="eyebrow">{run.status.toUpperCase()}</p><p><code>{run.id}</code></p>
            <p>{run.node_runs.length} node runs</p>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}><button disabled={busy || ["succeeded", "failed", "cancelled"].includes(run.status)} onClick={() => void tick(run.id)}>Tick</button><button disabled={busy || ["succeeded", "failed", "cancelled"].includes(run.status)} onClick={() => void cancel(run.id)}>Cancel</button><button disabled={busy} onClick={() => void replay(run.id)}>Replay check</button></div>
            {replays[run.id] && <div style={{ marginTop: 12, padding: 12, borderRadius: 10, border: "1px solid var(--border, #d8dee8)" }}><strong>Replay {replays[run.id].drifted ? "drift detected" : "matches live state"}</strong><p>{replays[run.id].event_count} events · checksum <code>{replays[run.id].replay_checksum.slice(0, 16)}…</code></p><small>Projected status: {replays[run.id].projected_status ?? "unknown"}</small></div>}{runMarker((approval) => <div key={approval.id} style={{ marginTop: 12, padding: 12, borderRadius: 10 }}><strong>Approval required</strong><p>{approval.prompt}</p><button disabled={busy} onClick={() => void decide(run, approval, "approved")}>Approve</button>{" "}<button disabled={busy} onClick={() => void decide(run, approval, "rejected")}>Reject</button></div>)}
          </div>)}</div>}
        </>}
      </article>
    </section>
  </main>;
}

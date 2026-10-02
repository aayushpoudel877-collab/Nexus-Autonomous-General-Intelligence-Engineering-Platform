"use client";

import { FormEvent, useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

type Project = { id: string; name: string };
type Modality = "text" | "image" | "audio" | "video" | "structured";
type Asset = {
  id: string; project_id: string; owner_id: string; name: string; modality: Modality;
  source_reference: string; media_type: string; sha256: string | null; byte_size: number | null;
  duration_ms: number | null; width: number | null; height: number | null;
  metadata: Record<string, string | number | boolean | null>; created_at: string;
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

const defaultMediaTypes: Record<Modality, string> = {
  text: "text/plain", image: "image/jpeg", audio: "audio/wav",
  video: "video/mp4", structured: "application/json",
};

export default function MultimodalPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [assets, setAssets] = useState<Asset[]>([]);
  const [name, setName] = useState("");
  const [modality, setModality] = useState<Modality>("text");
  const [sourceReference, setSourceReference] = useState("");
  const [mediaType, setMediaType] = useState("text/plain");
  const [sha256, setSha256] = useState("");
  const [byteSize, setByteSize] = useState("");
  const [durationMs, setDurationMs] = useState("");
  const [width, setWidth] = useState("");
  const [height, setHeight] = useState("");
  const [metadataText, setMetadataText] = useState("{}");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function loadProjects() {
    setLoading(true);
    try {
      const rows = await request("/workbench/projects") as Project[];
      setProjects(rows);
      if (rows.length) setProjectId((current) => current || rows[0].id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load projects.");
    } finally {
      setLoading(false);
    }
  }

  async function loadAssets(id: string) {
    if (!id) { setAssets([]); return; }
    try {
      setAssets(await request(`/multimodal/projects/${id}/assets`) as Asset[]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load asset manifests.");
    }
  }

  useEffect(() => { void loadProjects(); }, []);
  useEffect(() => { void loadAssets(projectId); }, [projectId]);

  function changeModality(value: Modality) {
    setModality(value);
    setMediaType(defaultMediaTypes[value]);
    if (value !== "audio" && value !== "video") setDurationMs("");
    if (value !== "image" && value !== "video") { setWidth(""); setHeight(""); }
  }

  async function createAsset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!projectId || saving || name.trim().length < 2 || !sourceReference.trim()) return;
    setSaving(true);
    setError("");
    try {
      const metadata = JSON.parse(metadataText);
      if (!metadata || Array.isArray(metadata) || typeof metadata !== "object") {
        throw new Error("Metadata must be a JSON object.");
      }
      const asset = await request(`/multimodal/projects/${projectId}/assets`, {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(), modality, source_reference: sourceReference.trim(),
          media_type: mediaType.trim(), sha256: sha256.trim() || null,
          byte_size: byteSize === "" ? null : Number(byteSize),
          duration_ms: durationMs === "" ? null : Number(durationMs),
          width: width === "" ? null : Number(width),
          height: height === "" ? null : Number(height),
          metadata,
        }),
      }) as Asset;
      setAssets((current) => [asset, ...current]);
      setName(""); setSourceReference(""); setSha256(""); setByteSize("");
      setDurationMs(""); setWidth(""); setHeight(""); setMetadataText("{}");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not register asset.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">NEXUS-Ω / PHASE 7</p>
        <h1>Multimodal Asset Manifests</h1>
        <p className="lead">Create a tenant-scoped catalog for text, image, audio, video and structured data. This first increment validates manifests and records provenance metadata; it does not upload, download, decode or run inference on asset content.</p>
        <p><a href="/">Home</a> · <a href="/workbench">AI Workbench</a> · <a href="/ml-lifecycle">ML Lifecycle</a> · <a href="/research">Research Planner</a></p>
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
        {!loading && projects.length === 0 && <p>Create a project in the <a href="/workbench">AI Workbench</a> first.</p>}
      </section>

      <section className="grid" style={{ alignItems: "start", marginTop: 24 }}>
        <article>
          <h2>Register asset manifest</h2>
          <form onSubmit={createAsset} style={{ display: "grid", gap: 10 }}>
            <label>Asset name<input required minLength={2} maxLength={180} value={name} onChange={(event) => setName(event.target.value)} /></label>
            <label>Modality<select value={modality} onChange={(event) => changeModality(event.target.value as Modality)}>
              <option value="text">Text</option><option value="image">Image</option>
              <option value="audio">Audio</option><option value="video">Video</option>
              <option value="structured">Structured data</option>
            </select></label>
            <label>Source reference<input required maxLength={2048} value={sourceReference} onChange={(event) => setSourceReference(event.target.value)} placeholder="dataset://collection/item-001" /></label>
            <label>Media type<input required maxLength={120} value={mediaType} onChange={(event) => setMediaType(event.target.value)} /></label>
            <label>SHA-256 checksum (optional)<input minLength={64} maxLength={64} value={sha256} onChange={(event) => setSha256(event.target.value)} placeholder="64 hexadecimal characters" /></label>
            <label>Byte size (optional)<input type="number" min={0} value={byteSize} onChange={(event) => setByteSize(event.target.value)} /></label>
            {(modality === "audio" || modality === "video") && <label>Duration (milliseconds)<input type="number" min={0} value={durationMs} onChange={(event) => setDurationMs(event.target.value)} /></label>}
            {(modality === "image" || modality === "video") && <div className="grid">
              <label>Width<input type="number" min={1} value={width} onChange={(event) => setWidth(event.target.value)} /></label>
              <label>Height<input type="number" min={1} value={height} onChange={(event) => setHeight(event.target.value)} /></label>
            </div>}
            <label>Additional metadata (JSON object)<textarea rows={4} value={metadataText} onChange={(event) => setMetadataText(event.target.value)} placeholder='{"language":"ne","split":"train"}' /></label>
            <button type="submit" disabled={!projectId || saving || name.trim().length < 2 || !sourceReference.trim()}>{saving ? "Saving…" : "Register manifest"}</button>
          </form>
        </article>

        <article>
          <h2>Asset catalog</h2>
          {assets.length === 0 ? <p>No asset manifests registered for this project yet.</p> : (
            <div style={{ display: "grid", gap: 12 }}>
              {assets.map((asset) => <div key={asset.id} style={{ border: "1px solid var(--border, #d8dee8)", borderRadius: 12, padding: 14 }}>
                <p className="eyebrow">{asset.modality} · {asset.media_type}</p>
                <h3>{asset.name}</h3>
                <p>Reference: <code>{asset.source_reference}</code></p>
                <p>{asset.byte_size === null ? "Size unknown" : `${asset.byte_size.toLocaleString()} bytes`}{asset.duration_ms === null ? "" : ` · ${asset.duration_ms} ms`}{asset.width && asset.height ? ` · ${asset.width}×${asset.height}` : ""}</p>
                {asset.sha256 && <small>SHA-256: {asset.sha256}</small>}
                <details style={{ marginTop: 8 }}><summary>Manifest metadata</summary><pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{JSON.stringify(asset.metadata, null, 2)}</pre></details>
                <small>Created {new Date(asset.created_at).toLocaleString()}</small>
              </div>)}
            </div>
          )}
        </article>
      </section>
    </main>
  );
}

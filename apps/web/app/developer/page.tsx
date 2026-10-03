export default function DeveloperPage() {
  return (
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">NEXUS-Ω / PHASE 10</p>
        <h1>Developer Ecosystem</h1>
        <p className="lead">
          Build against the tenant-scoped developer API with explicit scopes and metadata-only plugin
          registration.
        </p>
        <p>
          <a href="/dashboard">Dashboard</a> · <a href="/governance">Governance</a> · <a href="/audit">Audit</a> · <a href="/">Home</a>
        </p>
      </section>

      <section style={{ display: "grid", gap: 14, marginTop: 24 }}>
        <article>
          <p className="eyebrow">AUTHENTICATION</p>
          <h2>Scoped API keys</h2>
          <p>
            Owner and admin users can issue developer keys. Secrets are shown once, stored only as
            SHA-256 digests, and may expire or be revoked.
          </p>
          <pre style={{ whiteSpace: "pre-wrap" }}>
{String.raw`X-Nexus-API-Key: nxk_<prefix>_<secret>`}</pre>
        </article>

        <article>
          <p className="eyebrow">PLUGIN REGISTRY</p>
          <h2>Metadata before execution</h2>
          <p>
            Plugins can be registered with a manifest, version and lifecycle state. Phase 10 does
            not download or execute plugin code.
          </p>
          <pre style={{ whiteSpace: "pre-wrap" }}>
{String.raw`GET  /api/v1/developer/whoami
GET  /api/v1/developer/plugins
POST /api/v1/developer/plugins
PATCH /api/v1/developer/plugins/{plugin_id}`}</pre>
        </article>

        <article>
          <p className="eyebrow">SDK</p>
          <h2>Python transport client</h2>
          <p>Use the repository's dependency-free SDK while richer generated clients are developed.</p>
          <pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
{String.raw`from packages.sdk import NexusClient

client = NexusClient(
    "http://localhost:8000/api/v1",
    "nxk_<prefix>_<secret>",
)
plugins = client.list_plugins()`}</pre>
        </article>
      </section>
    </main>
  );
}

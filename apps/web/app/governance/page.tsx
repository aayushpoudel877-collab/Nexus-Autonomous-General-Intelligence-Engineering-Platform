export default function GovernancePage() {
  return (
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">NEXUS-Ω / PHASE 14</p>
        <h1>Ecosystem Governance</h1>
        <p className="lead">
          A human-controlled supply-chain boundary for integrations, cryptographic plugin verification and installation approvals.
        </p>
        <p>
          <a href="/developer">Developer</a> · <a href="/execution">Execution</a> · <a href="/audit">Audit</a> · <a href="/dashboard">Dashboard</a>
        </p>
      </section>

      <section style={{ display: "grid", gap: 14, marginTop: 24 }}>
        <article>
          <p className="eyebrow">INTEGRATIONS</p>
          <h2>Metadata, not secrets</h2>
          <p>
            Integration records carry provider, scopes, non-secret configuration and an external secret
            reference. The platform does not store raw passwords or tokens here.
          </p>
        </article>

        <article>
          <p className="eyebrow">PLUGIN SUPPLY CHAIN</p>
          <h2>Pending → verified → installable</h2>
          <p>
            Releases carry package and manifest SHA-256 values plus signer/signature metadata. An owner or
            admin must verify the artifact against an active Ed25519 trust root before release approval.
          </p>
        </article>

        <article>
          <p className="eyebrow">TRUST ROOTS</p>
          <h2>Cryptographic verification first</h2>
          <p>
            Tenant-owned Ed25519 trust roots verify the artifact digest and detached signature before a
            release can become installable. Revoked trust roots immediately stop new approvals and execution.
          </p>
        </article>

        <article>
          <p className="eyebrow">INSTALLATION GATE</p>
          <h2>Capabilities require approval</h2>
          <p>
            Installation requests declare requested scopes. The approving administrator may grant only a
            subset of those requested capabilities, or revoke the request.
          </p>
        </article>
      </section>
    </main>
  );
}

export default function ExecutionPage() {
  return (
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">NEXUS-Ω / PHASE 20</p>
        <h1>Controlled Execution</h1>
        <p className="lead">
          Approved plugin installations now have a persistent execution-control boundary with bounded
          resources, idempotency, explicit network policy and finite secret leases.
        </p>
        <p>
          <a href="/governance">Governance</a> · <a href="/developer">Developer</a> ·{" "}
          <a href="/audit">Audit</a>
        </p>
      </section>

      <section style={{ display: "grid", gap: 14, marginTop: 24 }}>
        <article>
          <p className="eyebrow">INPUT GATE</p>
          <h2>Approved installations only</h2>
          <p>
            Requests require a verified release, an approved tenant installation, declared plugin
            capabilities and a declared entrypoint.
          </p>
        </article>

        <article>
          <p className="eyebrow">POLICY SNAPSHOT</p>
          <h2>Bounded execution policy</h2>
          <p>
            Timeout, memory, output size and network rules are captured with the request so later
            workers execute against the policy that was approved at request time.
          </p>
        </article>

        <article>
          <p className="eyebrow">RUNTIME BOUNDARY</p>
          <h2>Queue first, execute later</h2>
          <p>
            The API creates and cancels queue records but intentionally does not execute arbitrary
            plugin code. A separate worker now claims leases, heartbeats them, records bounded outcomes and fails closed when no isolated artifact executor is available.
          </p>
        </article>

        <article>
          <p className="eyebrow">CANCELLATION</p>
          <h2>Stop the runtime, not just the record</h2>
          <p>
            Cancellation is checked against the authoritative execution state. The worker terminates
            the sandbox process group and reconciles the database state before writing its final audit event.
          </p>
        </article>

        <article>
          <p className="eyebrow">EGRESS MEDIATION</p>
          <h2>Network without a network namespace</h2>
          <p>
            Allowlisted HTTP(S) requests use an authenticated per-execution Unix-socket broker while
            the plugin remains on <code>--network=none</code>. The broker enforces host/port allowlists,
            public-address resolution, bounded payloads and no redirects.
          </p>
        </article>

        <article>
          <p className="eyebrow">SECRET LEASES</p>
          <h2>Credentials expire by design</h2>
          <p>
            Secret approvals require an explicit one-minute-to-seven-day expiration. Expired grants are
            rejected during admission and rechecked by the worker immediately before sandbox launch.
            Revoked grant identities are never recycled, so historical queued requests cannot regain access.
          </p>
        </article>

        <article>
          <p className="eyebrow">SECRET MEDIATION</p>
          <h2>Credentials stay outside the plugin</h2>
          <p>
            Secret access requires an owner-approved grant and <code>secret.read</code>. The worker
            revalidates grants, then starts a short-lived scrubbed broker subprocess. The sandbox
            receives only a Unix socket and token path; resolved secret values never enter its
            environment, execution results or audit records.
          </p>
        </article>
      </section>
    </main>
  );
}

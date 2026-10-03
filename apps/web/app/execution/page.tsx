export default function ExecutionPage() {
  return (
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">NEXUS-Ω / PHASE 12</p>
        <h1>Controlled Execution</h1>
        <p className="lead">
          Approved plugin installations now have a persistent execution-control boundary with bounded
          resources, idempotency and explicit network policy.
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
            plugin code. A sandboxed worker is a separate future phase.
          </p>
        </article>
      </section>
    </main>
  );
}

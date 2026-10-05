[object Object]

## Phase 18 mediated egress

Network-enabled execution is no longer rejected solely because its policy is `allowlist`; it is eligible only when the request uses policy version 3, declares the `network.http` capability, and contains the Phase 18 `unix_socket_broker` egress mode.

The plugin container still uses `--network=none`. For an allowlisted execution the worker creates:

- a short-lived Unix socket at the execution runtime path;
- a random per-execution token file;
- a broker that performs the actual outbound HTTP(S) request.

The sandbox receives the socket and token as read-only mounts plus:

- `NEXUS_EGRESS_SOCKET=/nexus/egress.sock`
- `NEXUS_EGRESS_TOKEN_FILE=/nexus/egress.token`

The broker contract is JSON Lines:

`{"token":"...","method":"GET","url":"https://api.example.com/path","headers":{...},"body_base64":"..."}`

Successful responses include status code, bounded headers, base64 response bytes and a truncation flag. Redirects are not followed. The broker rejects IP-literal destinations and any DNS result that is not globally routable.

Limits are frozen into the execution policy snapshot: 128 KiB request payload, 4 MiB response body, at most four concurrent broker requests, and a maximum 15-second broker request timeout.

Direct socket access, arbitrary protocols and network namespace attachment remain unavailable.

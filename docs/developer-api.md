[object Object]

## Phase 18 controlled egress

Execution requests may use `network_policy=allowlist` only when the request also includes the `network.http` capability. The API freezes the following egress policy with the request:

- exact hostname/port allowlist;
- Unix-socket broker mode;
- 128 KiB request limit;
- 4 MiB response limit;
- 15-second maximum broker request timeout;
- zero redirects.

The plugin runtime remains on `--network=none`. Network traffic is performed by a short-lived egress broker subprocess through an authenticated per-execution Unix socket. The broker subprocess is started without the API/worker database and secret environment variables. Plugin code does not receive a raw network namespace.

The runtime broker protocol is intentionally narrow: HTTP(S) GET, HEAD and POST requests with bounded headers/body, no credential-bearing URLs and no redirect following.

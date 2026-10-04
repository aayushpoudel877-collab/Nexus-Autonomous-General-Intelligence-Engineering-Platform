[object Object]

## Phase 16 isolated launcher boundary

Phase 16 adds an opt-in isolated launcher behind the Phase 15 admission contract. The launcher invokes the configured OCI runtime with argument vectors only, never through a shell. Each invocation uses a fresh process session, a bounded request timeout, bounded stdout/stderr capture, explicit process-group termination, and container-ID cleanup for timeout or output-limit termination.

The launcher treats the execution policy as authoritative: the image is digest-pinned, the artifact is read-only, networking remains disabled, and the request timeout becomes the runtime deadline. The launcher returns structured terminal classification rather than exposing raw process internals to the API.

Launch is disabled by default. The repository's local Compose worker deliberately does not mount the Docker socket or enable launch. A deployment that enables it must supply an isolated runtime host boundary and ensure the configured artifact path is visible to that runtime.

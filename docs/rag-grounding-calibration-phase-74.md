# Phase 74 — Trusted reviewer verification and governed release enforcement

Phase 74 connects the approval record and Phase 73 lifecycle ledger to GitHub's authenticated pull-request review API. A release can now require all three trust layers:

1. A valid calibration approval record bound to the exact baseline manifest and provenance attestation.
2. An active approval digest in the validated Phase 73 hash-chained lifecycle ledger.
3. A merged pull request whose current review history contains the approval of the recorded reviewer, on the exact source commit, from an explicit reviewer allowlist.

The release CLI can additionally require the existing calibration regression policy to pass.

## Trusted review rules

- Review data is fetched directly from `https://api.github.com` using `GITHUB_TOKEN`; copied JSON or caller-provided reviewer names are not accepted as authenticated evidence.
- The repository and pull-request number must match the requested target.
- The pull request must be merged, and its head SHA must equal the provenance attestation's `source_revision`.
- Only allowlisted GitHub logins count. The reviewer named in the approval record must be among the current trusted approvers.
- The latest submitted review for each allowlisted reviewer on that exact head commit controls that reviewer's state. A later dismissal or changes-requested review removes the earlier approval from the active set.
- The minimum number of distinct trusted approvals is configurable.
- The approval digest must still be active in the verified lifecycle ledger, and all attested input bytes must match.

The workflow requests only `contents: read` and `pull-requests: read`. Its token is not written to the decision artifact.

## Run the governed release CLI

Set `GITHUB_TOKEN` to a GitHub token with read access to the target repository's pull requests. The attestation source revision must be the head SHA of the merged PR supplied below.

```bash
python -m services.rag.calibration_release_gate_cli \
  --baseline-manifest calibration-baseline-manifest.json \
  --current calibration-current-report.json \
  --output calibration-governance-decision.json \
  --require-governance \
  --attestation calibration-provenance.json \
  --approval calibration-approval.json \
  --ledger calibration-approval-ledger.json \
  --input dataset=calibration-dataset.jsonl \
  --repository owner/repository \
  --pull-request 123 \
  --allowed-reviewer reviewer-login \
  --minimum-approvals 1
```

Repeat `--input LABEL=PATH` for every attested input. Repeat `--allowed-reviewer` or provide comma-separated logins to define the trusted reviewer allowlist. The approval record's reviewer ID must be one of those trusted logins.

Exit codes remain stable: `0` means governance verification and calibration regression policy both passed; `1` means the valid calibration comparison found regressions; `2` means invalid or missing governance evidence, API failure, or artifact-write failure. A decision JSON is written atomically when the output path is writable.

## Manual GitHub Actions workflow

The `Calibration Governance Release` workflow can be started from the Actions tab using **Run workflow**. Supply repository paths for the baseline manifest, candidate report, provenance attestation, approval record, lifecycle ledger, and attested dataset, plus the merged PR number and comma-separated reviewer allowlist. The workflow fetches the review records with its read-only `GITHUB_TOKEN` permissions and archives the machine-readable decision artifact.

The workflow currently accepts one dataset path. For attestations containing multiple input labels, invoke the CLI directly and pass one `--input LABEL=PATH` per attested input.

## Trust boundaries and operational requirements

- GitHub review evidence establishes that GitHub reports a particular account as having submitted a review. The allowlist is an explicit policy decision; it is not a proof of a person's legal identity or independence.
- The approval record's reviewer ID and timestamp remain caller-asserted metadata until matched to the GitHub review evidence. Do not treat a standalone approval JSON as authenticated.
- Hash chaining detects edits to retained ledger history but does not prevent replacement of the entire ledger. Store the ledger and evidence in protected, retained artifact storage.
- The workflow does not create or approve a baseline. An operator must supply a reviewed manifest, provenance, approval record, and active ledger entry.
- The source revision must refer to the merged PR's head commit, not the merge commit. Re-evaluation against a different source commit requires fresh provenance and approval evidence.
- This is a governance and fixture-regression gate, not proof of semantic entailment, factual correctness, or production safety.

## Test coverage

Tests exercise allowlist enforcement, stale commit rejection, merged-PR and repository binding, latest-review precedence, dismissed and changes-requested reviews, approval thresholds, active-ledger requirements, reviewer matching, provenance input-byte integrity, and the release CLI's fail-closed governance mode.

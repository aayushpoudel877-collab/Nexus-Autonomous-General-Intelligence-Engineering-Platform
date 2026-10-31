"""Trusted GitHub review evidence for calibration release governance.

Review evidence is fetched from GitHub's authenticated API; caller-supplied reviewer
names or copied review JSON are never treated as authentication.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

from services.rag.calibration_approval import validate_approval_record
from services.rag.calibration_approval_ledger import active_approvals, validate_ledger
from services.rag.calibration_baseline import sha256_json
from services.rag.calibration_provenance import validate_attestation, verify_input_files

_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_API_ROOT = "https://api.github.com"
_MAX_GITHUB_RESPONSE_BYTES = 1_000_000
_MAX_GITHUB_REVIEW_PAGES = 100
_MAX_GITHUB_REVIEWS = 10_000


def _parse_time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise TypeError("GitHub review submitted_at must be a timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("GitHub review submitted_at is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("GitHub review submitted_at must include a timezone")
    return parsed


def validate_github_review_payload(
    pull_request: Any,
    reviews: Any,
    *,
    repository: str,
    pull_request_number: int,
    expected_head_sha: str,
    approval_reviewer_id: str,
    allowed_reviewers: set[str],
    minimum_approvals: int = 1,
) -> dict[str, Any]:
    """Validate API-shaped PR/review data and calculate current trusted approvals."""
    if not _REPOSITORY.fullmatch(repository) or any(
        part in {".", ".."} for part in repository.split("/")
    ):
        raise ValueError("repository must use a safe owner/name format")
    if isinstance(pull_request_number, bool) or not isinstance(pull_request_number, int) or pull_request_number < 1:
        raise ValueError("pull_request_number must be a positive integer")
    if not isinstance(expected_head_sha, str) or not _SHA.fullmatch(expected_head_sha):
        raise ValueError("expected_head_sha must be a full lowercase commit SHA")
    if not isinstance(approval_reviewer_id, str) or not approval_reviewer_id.strip():
        raise ValueError("approval reviewer identity is missing")
    if isinstance(minimum_approvals, bool) or not isinstance(minimum_approvals, int) or minimum_approvals < 1:
        raise ValueError("minimum_approvals must be a positive integer")
    if not isinstance(allowed_reviewers, set) or any(not isinstance(item, str) for item in allowed_reviewers):
        raise TypeError("allowed_reviewers must be a set of GitHub login strings")
    normalized_allowlist = {item.strip().casefold() for item in allowed_reviewers if item.strip()}
    if not normalized_allowlist:
        raise ValueError("at least one trusted reviewer must be allowlisted")
    if not isinstance(pull_request, dict) or not isinstance(reviews, list):
        raise TypeError("GitHub pull request and review API responses have invalid shapes")
    base = pull_request.get("base")
    base_repo = base.get("repo", {}).get("full_name") if isinstance(base, dict) else None
    head = pull_request.get("head")
    head_sha = head.get("sha") if isinstance(head, dict) else None
    if base_repo != repository:
        raise ValueError("GitHub pull request belongs to a different repository")
    if pull_request.get("number") != pull_request_number:
        raise ValueError("GitHub pull request number does not match the requested record")
    if pull_request.get("state") != "closed" or pull_request.get("merged") is not True:
        raise ValueError("GitHub pull request must be merged for release approval evidence")
    if not isinstance(pull_request.get("merged_at"), str) or not pull_request["merged_at"]:
        raise ValueError("merged GitHub pull request is missing merged_at")
    if head_sha != expected_head_sha:
        raise ValueError("GitHub pull request head does not match the attested source revision")

    latest: dict[str, tuple[datetime, str, str]] = {}
    for review in reviews:
        if not isinstance(review, dict):
            raise TypeError("GitHub review entry must be an object")
        user = review.get("user")
        login = user.get("login") if isinstance(user, dict) else None
        state = review.get("state")
        if not isinstance(login, str) or not login.strip():
            raise ValueError("GitHub review is missing its reviewer login")
        if state not in {"APPROVED", "CHANGES_REQUESTED", "COMMENTED", "DISMISSED", "PENDING"}:
            raise ValueError("GitHub review has an unsupported state")
        if review.get("commit_id") != expected_head_sha:
            continue
        submitted = _parse_time(review.get("submitted_at"))
        key = login.casefold()
        previous = latest.get(key)
        if previous is None or submitted > previous[0]:
            latest[key] = (submitted, state, login)

    approved = sorted(
        login for key, (_, state, login) in latest.items()
        if state == "APPROVED" and key in normalized_allowlist
    )
    if len(approved) < minimum_approvals:
        raise ValueError(
            f"trusted GitHub approvals {len(approved)} are below required {minimum_approvals}"
        )
    if approval_reviewer_id.casefold() not in {login.casefold() for login in approved}:
        raise ValueError("approval record reviewer_id does not have a current trusted GitHub approval")
    return {
        "provider": "github",
        "repository": repository,
        "pull_request": pull_request_number,
        "head_sha": expected_head_sha,
        "approved_reviewers": approved,
        "minimum_approvals": minimum_approvals,
        "approval_reviewer_id": approval_reviewer_id,
    }


def _github_get(url: str, token: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Nexus-Calibration-Governance",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status != 200:
                raise ValueError(f"GitHub API returned HTTP {response.status}")
            content_length = response.headers.get("Content-Length")
            if content_length is not None:
                try:
                    declared_length = int(content_length)
                except (TypeError, ValueError) as exc:
                    raise ValueError("GitHub API returned an invalid Content-Length") from exc
                if declared_length < 0 or declared_length > _MAX_GITHUB_RESPONSE_BYTES:
                    raise ValueError("GitHub API response exceeds the configured byte limit")
            payload = response.read(_MAX_GITHUB_RESPONSE_BYTES + 1)
            if len(payload) > _MAX_GITHUB_RESPONSE_BYTES:
                raise ValueError("GitHub API response exceeds the configured byte limit")
            return json.loads(payload.decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not obtain trusted GitHub review evidence: {exc}") from exc


def fetch_github_review_evidence(
    *,
    repository: str,
    pull_request_number: int,
    expected_head_sha: str,
    approval_reviewer_id: str,
    allowed_reviewers: set[str],
    token: str,
    minimum_approvals: int = 1,
) -> dict[str, Any]:
    """Fetch PR and all review pages from GitHub using a workflow/API token."""
    if not _REPOSITORY.fullmatch(repository) or any(
        part in {".", ".."} for part in repository.split("/")
    ):
        raise ValueError("repository must use a safe owner/name format")
    if not isinstance(token, str) or not token.strip():
        raise ValueError("GITHUB_TOKEN is required to fetch trusted review evidence")
    if "\r" in token or "\n" in token:
        raise ValueError("GITHUB_TOKEN contains invalid header characters")
    if isinstance(pull_request_number, bool) or not isinstance(pull_request_number, int) or pull_request_number < 1:
        raise ValueError("pull_request_number must be a positive integer")
    root = f"{_API_ROOT}/repos/{repository}/pulls/{pull_request_number}"
    pr = _github_get(root, token)
    reviews: list[Any] = []
    page = 1
    while True:
        page_data = _github_get(f"{root}/reviews?per_page=100&page={page}", token)
        if not isinstance(page_data, list):
            raise TypeError("GitHub reviews endpoint returned an invalid page")
        if len(reviews) + len(page_data) > _MAX_GITHUB_REVIEWS:
            raise ValueError("GitHub review pagination exceeded the total review limit")
        reviews.extend(page_data)
        if len(page_data) < 100:
            break
        page += 1
        if page > _MAX_GITHUB_REVIEW_PAGES:
            raise ValueError("GitHub review pagination exceeded the page limit")
    return validate_github_review_payload(
        pr, reviews, repository=repository, pull_request_number=pull_request_number,
        expected_head_sha=expected_head_sha, approval_reviewer_id=approval_reviewer_id,
        allowed_reviewers=allowed_reviewers, minimum_approvals=minimum_approvals,
    )


def evaluate_governed_release(
    *,
    manifest: Any,
    attestation: Any,
    approval_record: Any,
    ledger: Any,
    inputs: dict[str, Any],
    repository: str,
    pull_request_number: int,
    allowed_reviewers: set[str],
    token: str,
    minimum_approvals: int = 1,
) -> dict[str, Any]:
    """Fetch trusted GitHub evidence and require an exact, active approval before release."""
    checked_attestation = validate_attestation(attestation, manifest["report"])
    verify_input_files(checked_attestation, inputs)
    checked_approval = validate_approval_record(approval_record, manifest, checked_attestation)
    checked_ledger = validate_ledger(ledger)
    digest = checked_approval["approval_record_sha256"]
    if digest not in active_approvals(checked_ledger):
        raise ValueError("approval record is not active in the verified lifecycle ledger")
    github_evidence = fetch_github_review_evidence(
        repository=repository,
        pull_request_number=pull_request_number,
        expected_head_sha=checked_attestation["source_revision"],
        approval_reviewer_id=checked_approval["reviewer_id"],
        allowed_reviewers=allowed_reviewers,
        token=token,
        minimum_approvals=minimum_approvals,
    )
    return {
        "verified": True,
        "approval_record_sha256": digest,
        "baseline_manifest_sha256": sha256_json(manifest),
        "provenance_attestation_sha256": sha256_json(checked_attestation),
        "ledger_head_sha256": checked_ledger["events"][-1]["event_sha256"] if checked_ledger["events"] else None,
        "github_review": github_evidence,
    }

# Offline RAG Evaluation Harness (Phase 34)

The Phase 34 harness evaluates ranked chunk IDs against a reviewed, versioned golden set.
It is deterministic and provider-independent: it does not make model calls or use
production customer queries. The checked-in examples are synthetic test fixtures, not
evidence of real-world retrieval quality.

## Golden dataset

Use one JSON object per line in a UTF-8 JSONL file:

- `case_id`: stable unique identifier;
- `tenant_id`: synthetic or anonymized tenant slice label;
- `query`: reviewed query text;
- `relevant_chunk_ids`: non-empty list of reviewed relevant chunk IDs;
- `language`: language slice, default `und`;
- `risk_category`: risk slice, default `general`;
- `reviewer_notes`: optional short note, never production personal data.

Unknown fields, missing required fields, duplicate case IDs, duplicate labels, empty
relevance labels, malformed JSON, and oversized files/records are rejected. Files are
limited to 10 MiB, 20,000 records, 256 KiB per line, and 20,000 characters per query or
review note. Keep final evaluation data separate from tuning data and record the dataset
revision/hash in experiment notes.

## Prediction format

Use one JSON object per line with exactly `run_name`, `case_id`, and
`ranked_chunk_ids`. A run/case pair must be unique. Predictions for unknown case IDs
are rejected. If a prediction for a known case is absent, the harness counts it as an
empty result instead of silently excluding that case.

## Run locally

From the repository root:

```bash
python -m services.rag.evaluation_cli \
  --dataset tests/fixtures/rag/golden.jsonl \
  --predictions tests/fixtures/rag/predictions.jsonl \
  --output rag-evaluation-report.json \
  --k 1 --baseline baseline --candidate candidate
```

Exit codes: `0` means evaluation succeeded and any configured release gate passed;
`1` means a configured regression gate failed; `2` means the input or configuration
was invalid. The output is stable, sorted JSON suitable for archiving as a CI artifact.

## Metrics and release gate

The report computes precision@k, recall@k, reciprocal rank, NDCG@k, and empty-result
rate. It includes aggregate metrics and slices by language, risk category, and tenant.
The optional gate compares candidate against baseline using maximum absolute drops for
precision, recall, and NDCG (defaults: 0.05 each). It checks aggregate metrics and every
matching slice so a good aggregate cannot hide a material regression in a represented
slice. Small slices can be noisy; interpret the report alongside sample counts and
human-reviewed examples.

The CI workflow runs the checked-in synthetic baseline/candidate fixture through the
release gate. This protects the harness and its contract; it does not certify production
quality. The fixture is intentionally tiny and must not be cited as an empirical claim
that a retrieval strategy improved.

## Scope and next work

This phase implements reviewed golden-set loading, deterministic offline ranking reports,
slice metrics, regression thresholds, CLI output, and a CI gate. It does not generate
synthetic queries automatically, verify semantic answer entailment, measure real latency,
test cross-tenant leakage without document ownership labels, or connect to a hosted vector
database. Future work should add a larger human-reviewed benchmark, query-generation
review workflow, explicit source-ownership leakage checks, retrieval latency measurements,
and semantic-answer faithfulness evaluation.


## Claim-support and citation-quality evaluation

An optional claim-level JSONL file can be supplied with `--grounding-dataset`. Each
record includes a unique case ID, claim text, evidence ID/text, cited evidence IDs, and
a human-reviewed binary `expected_supported` label, with optional language and risk
slices. The report includes a confusion matrix, precision, recall, false-positive and
false-negative rates, IDs of false-positive/negative cases, citation-validity rate, and
language/risk slices. Missing or unknown citation IDs fail closed as unsupported.

The checked-in grounding examples are deliberately synthetic edge cases designed to
exercise false-positive, false-negative, and citation-integrity accounting. They are
not a representative or independently reviewed benchmark. Lexical overlap may wrongly
accept qualified claims or miss valid paraphrases; use the report to expose those errors,
not to claim semantic correctness. Production use requires a substantially larger,
human-reviewed and versioned dataset.

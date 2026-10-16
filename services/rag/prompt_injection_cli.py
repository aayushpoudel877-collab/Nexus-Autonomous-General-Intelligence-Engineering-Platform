"""CLI for deterministic, offline prompt-injection marker evaluation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .prompt_injection import (
    MAX_EVALUATION_CASES,
    PromptInjectionCase,
    evaluate_prompt_injection_cases,
)

MAX_DATASET_BYTES = 5 * 1024 * 1024
MAX_LINE_BYTES = 128 * 1024


def load_prompt_injection_cases(path: str | Path) -> tuple[PromptInjectionCase, ...]:
    """Load a bounded JSONL dataset with a strict, versionable field contract."""
    dataset_path = Path(path)
    if not dataset_path.is_file():
        raise ValueError(f"dataset file does not exist: {dataset_path}")
    if dataset_path.stat().st_size > MAX_DATASET_BYTES:
        raise ValueError("prompt-injection dataset exceeds the maximum file size")

    cases: list[PromptInjectionCase] = []
    required = {"case_id", "text", "expected_attack"}
    allowed = required | {"language", "risk_category"}
    with dataset_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if len(line.encode("utf-8")) > MAX_LINE_BYTES:
                raise ValueError(f"dataset line {line_number} exceeds the maximum size")
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON on dataset line {line_number}") from exc
            if not isinstance(row, dict):
                raise TypeError(f"dataset line {line_number} must contain a JSON object")
            unknown = set(row) - allowed
            missing = required - set(row)
            if unknown or missing:
                raise ValueError(
                    f"dataset line {line_number} has unknown or missing fields: "
                    f"{sorted(unknown | missing)}"
                )
            cases.append(
                PromptInjectionCase(
                    case_id=row["case_id"],
                    text=row["text"],
                    expected_attack=row["expected_attack"],
                    language=row.get("language", "und"),
                    risk_category=row.get("risk_category", "general"),
                )
            )
            if len(cases) > MAX_EVALUATION_CASES:
                raise ValueError("prompt-injection dataset contains too many cases")
    if not cases:
        raise ValueError("prompt-injection dataset must contain at least one case")
    return tuple(cases)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, help="bounded JSONL evaluation dataset")
    parser.add_argument("--output", required=True, help="path for deterministic JSON report")
    args = parser.parse_args(argv)

    try:
        cases = load_prompt_injection_cases(args.dataset)
        report = evaluate_prompt_injection_cases(cases)
        output_path = Path(args.output)
        output_path.write_text(
            json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Evaluated {len(cases)} cases; report written to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

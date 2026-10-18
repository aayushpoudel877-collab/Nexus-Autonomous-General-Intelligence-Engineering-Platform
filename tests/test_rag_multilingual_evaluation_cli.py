import json

from services.rag.evaluation_cli import main


def _write_jsonl(path, records):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records), encoding="utf-8")
    return str(path)


def test_cli_writes_multilingual_ablation_when_comparing_runs(tmp_path):
    dataset = _write_jsonl(tmp_path / "golden.jsonl", [
        {"case_id": "en-1", "tenant_id": "t1", "query": "alpha", "relevant_chunk_ids": ["a"], "language": "en"},
        {"case_id": "ne-1", "tenant_id": "t2", "query": "नेपाल", "relevant_chunk_ids": ["n"], "language": "ne"},
    ])
    predictions = _write_jsonl(tmp_path / "predictions.jsonl", [
        {"run_name": "baseline", "case_id": "en-1", "ranked_chunk_ids": ["a"]},
        {"run_name": "baseline", "case_id": "ne-1", "ranked_chunk_ids": []},
        {"run_name": "candidate", "case_id": "en-1", "ranked_chunk_ids": ["a"]},
        {"run_name": "candidate", "case_id": "ne-1", "ranked_chunk_ids": ["n"]},
    ])
    output = tmp_path / "report.json"
    result = main([
        "--dataset", dataset, "--predictions", predictions, "--output", str(output),
        "--baseline", "baseline", "--candidate", "candidate",
        "--bootstrap-samples", "100", "--bootstrap-seed", "37",
    ])
    assert result == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["multilingual_ablation"]["language_slices"]["ne"]["case_count"] == 1
    assert "confidence_interval" in report["multilingual_ablation"]["language_slices"]["ne"]["metrics"]["recall_at_k"]["candidate"]

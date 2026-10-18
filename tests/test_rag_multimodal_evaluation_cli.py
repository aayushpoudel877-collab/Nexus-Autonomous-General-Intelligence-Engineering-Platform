import json

from services.rag.evaluation_cli import main


def _write_jsonl(path, records):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records), encoding="utf-8")
    return str(path)


def test_cli_adds_modality_slices_when_map_is_provided(tmp_path):
    dataset = _write_jsonl(tmp_path / "golden.jsonl", [
        {"case_id": "q-text", "tenant_id": "t1", "query": "alpha", "relevant_chunk_ids": ["a"]},
        {"case_id": "q-image", "tenant_id": "t1", "query": "caption", "relevant_chunk_ids": ["caption"]},
    ])
    predictions = _write_jsonl(tmp_path / "predictions.jsonl", [
        {"run_name": "candidate", "case_id": "q-text", "ranked_chunk_ids": ["a"]},
        {"run_name": "candidate", "case_id": "q-image", "ranked_chunk_ids": ["caption"]},
    ])
    modalities = _write_jsonl(tmp_path / "modalities.jsonl", [
        {"case_id": "q-text", "modality": "text"},
        {"case_id": "q-image", "modality": "image"},
    ])
    output = tmp_path / "report.json"
    result = main([
        "--dataset", dataset, "--predictions", predictions, "--modality-map", modalities,
        "--output", str(output),
    ])
    assert result == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["multimodal_evaluation"]["runs"]["candidate"]["modalities"]["image"]["recall_at_k"] == 1.0

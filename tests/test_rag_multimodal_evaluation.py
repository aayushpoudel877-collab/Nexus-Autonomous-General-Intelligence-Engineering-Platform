import json

import pytest

from services.rag.evaluation import EvaluationCase, EvaluationPrediction
from services.rag.multimodal_evaluation import (
    evaluate_multimodal_slices,
    load_modality_map,
)


def _cases():
    return [
        EvaluationCase("q-text", "t1", "text query", ("text-hit",), "en"),
        EvaluationCase("q-image", "t1", "image query", ("caption-hit",), "en"),
        EvaluationCase("q-audio", "t2", "audio query", ("transcript-hit",), "ne"),
    ]


def _predictions():
    return [
        EvaluationPrediction("baseline", "q-text", ("text-hit",)),
        EvaluationPrediction("baseline", "q-image", ("wrong",)),
        EvaluationPrediction("baseline", "q-audio", ()),
        EvaluationPrediction("candidate", "q-text", ("text-hit",)),
        EvaluationPrediction("candidate", "q-image", ("caption-hit",)),
        EvaluationPrediction("candidate", "q-audio", ("transcript-hit",)),
    ]


def test_multimodal_metrics_separate_each_modality_and_run():
    report = evaluate_multimodal_slices(
        _cases(), _predictions(),
        {"q-text": "text", "q-image": "image", "q-audio": "audio"}, k=1,
    )
    assert report["modality_slices"]["image"]["case_count"] == 1
    assert report["runs"]["baseline"]["modalities"]["image"]["recall_at_k"] == 0.0
    assert report["runs"]["candidate"]["modalities"]["image"]["recall_at_k"] == 1.0
    assert report["runs"]["baseline"]["modalities"]["audio"]["empty_result_rate"] == 1.0
    assert report["runs"]["candidate"]["aggregate"]["recall_at_k"] == 1.0


def test_multimodal_metrics_require_exact_case_to_modality_mapping():
    with pytest.raises(ValueError, match="missing"):
        evaluate_multimodal_slices(_cases(), _predictions(), {"q-text": "text"})
    with pytest.raises(ValueError, match="unsupported modality"):
        evaluate_multimodal_slices(
            _cases(), _predictions(),
            {"q-text": "text", "q-image": "image", "q-audio": "telepathy"},
        )


def test_multimodal_metrics_reject_duplicate_and_unknown_predictions():
    duplicate = _predictions() + [_predictions()[0]]
    mapping = {"q-text": "text", "q-image": "image", "q-audio": "audio"}
    with pytest.raises(ValueError, match="duplicate prediction"):
        evaluate_multimodal_slices(_cases(), duplicate, mapping)
    with pytest.raises(ValueError, match="unknown case"):
        evaluate_multimodal_slices(
            _cases(), [EvaluationPrediction("run", "unknown", ("x",))], mapping,
        )


def test_modality_map_loader_is_strict_and_rejects_duplicates(tmp_path):
    path = tmp_path / "modalities.jsonl"
    path.write_text(
        json.dumps({"case_id": "q1", "modality": "image"}) + "\n"
        + json.dumps({"case_id": "q2", "modality": "audio"}) + "\n",
        encoding="utf-8",
    )
    assert load_modality_map(path) == {"q1": "image", "q2": "audio"}
    path.write_text(
        json.dumps({"case_id": "q1", "modality": "image"}) + "\n"
        + json.dumps({"case_id": "q1", "modality": "audio"}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate modality"):
        load_modality_map(path)


def test_modality_map_rejects_unknown_fields_and_unsupported_values(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps({"case_id": "q1", "modality": "image", "tenant_id": "t"}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="only case_id and modality"):
        load_modality_map(path)
    path.write_text(json.dumps({"case_id": "q1", "modality": "unknown"}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported modality"):
        load_modality_map(path)

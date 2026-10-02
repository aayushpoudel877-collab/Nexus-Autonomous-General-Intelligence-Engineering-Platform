def test_phase_one_imports():
    from services.api.app.main import app

    assert app.title == "NEXUS-Ω API"
    assert "/api/v1/auth/login" in app.openapi()["paths"]
    assert "/api/v1/auth/organizations" in app.openapi()["paths"]
    assert "/api/v1/auth/select-organization/{organization_id}" in app.openapi()["paths"]


def test_ai_tutor_routes_are_registered():
    from services.api.app.main import app

    paths = app.openapi()["paths"]
    assert "/api/v1/tutor/conversations" in paths
    assert "/api/v1/tutor/conversations/{conversation_id}" in paths
    assert "/api/v1/tutor/conversations/{conversation_id}/messages" in paths


def test_workbench_routes_are_registered():
    from services.api.app.main import app

    paths = app.openapi()["paths"]
    assert "/api/v1/workbench/projects" in paths
    assert "/api/v1/workbench/projects/{project_id}/datasets" in paths
    assert "/api/v1/workbench/projects/{project_id}/experiments" in paths
    assert "/api/v1/workbench/experiments/{experiment_id}" in paths


def test_research_routes_are_registered():
    from services.api.app.main import app

    paths = app.openapi()["paths"]
    assert "/api/v1/research/plans" in paths
    assert "/api/v1/research/plans/{plan_id}/tasks" in paths
    assert "/api/v1/research/tasks/{task_id}" in paths


def test_ml_lifecycle_routes_are_registered():
    from services.api.app.main import app

    paths = app.openapi()["paths"]
    assert "/api/v1/ml/projects/{project_id}/training-runs" in paths
    assert "/api/v1/ml/training-runs/{run_id}" in paths
    assert "/api/v1/ml/projects/{project_id}/models" in paths
    assert "/api/v1/ml/models/{model_id}/evaluations" in paths
    assert "/api/v1/ml/models/{model_id}/evaluations/run" in paths
    assert "/api/v1/ml/evaluations/{evaluation_id}" in paths


def test_multimodal_routes_are_registered():
    from services.api.app.main import app

    paths = app.openapi()["paths"]
    assert "/api/v1/multimodal/projects/{project_id}/assets" in paths
    assert "/api/v1/multimodal/assets/{asset_id}" in paths


def test_continuous_improvement_routes_are_registered():
    from services.api.app.main import app

    paths = app.openapi()["paths"]
    assert "/api/v1/benchmarks/projects/{project_id}/comparisons" in paths
    assert "/api/v1/audit/events" in paths

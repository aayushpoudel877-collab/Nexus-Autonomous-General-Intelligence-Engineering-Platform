def test_phase_one_imports():
    from services.api.app.main import app

    assert app.title == "NEXUS-Ω API"
    assert "/api/v1/auth/login" in app.openapi()["paths"]


def test_ai_tutor_routes_are_registered():
    from services.api.app.main import app

    paths = app.openapi()["paths"]
    assert "/api/v1/tutor/conversations" in paths
    assert "/api/v1/tutor/conversations/{conversation_id}" in paths
    assert "/api/v1/tutor/conversations/{conversation_id}/messages" in paths

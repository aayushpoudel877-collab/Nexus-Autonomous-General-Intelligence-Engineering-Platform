def test_phase_one_imports():
    from services.api.app.main import app
    assert app.title == "NEXUS-Ω API"
    assert any(route.path == "/api/v1/auth/login" for route in app.routes)

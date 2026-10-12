from fastapi.routing import APIRoute

from services.api.app.main import app
from services.api.app.routes.rag_upload import router


def _dependency_names(dependant):
    names = {getattr(item.call, "__name__", "") for item in dependant.dependencies}
    for item in dependant.dependencies:
        names.update(_dependency_names(item))
    return names


def test_upload_route_is_registered_as_multipart_endpoint():
    operation = app.openapi()["paths"]["/api/v1/rag/documents/upload"]["post"]
    assert operation["requestBody"]["content"].get("multipart/form-data")
    assert operation["responses"]["201"]


def test_upload_route_requires_authenticated_role_and_database_context():
    route = next(route for route in router.routes if isinstance(route, APIRoute))
    names = _dependency_names(route.dependant)
    assert "get_current_user" in names
    assert "get_db" in names
    assert "get_membership" in names

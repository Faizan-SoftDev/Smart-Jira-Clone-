from fastapi.testclient import TestClient

from app.main import app

def test_unauthenticated_request_is_blocked():
    """Verifies that missing authorizations trigger access control rejections"""
    with TestClient(app) as client:
        response = client.post("/api/v1/tasks/00000000-0000-0000-0000-000000000001/analyze-ai")
    assert response.status_code == 401

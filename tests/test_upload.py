import pytest
import io
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db

# Initialize database schema for tests
init_db()

client = TestClient(app)

def test_health_endpoint():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"

def test_upload_invalid_file_extension():
    fake_file = io.BytesIO(b"fake txt content")
    response = client.post(
        "/api/videos/upload",
        files={"file": ("test.txt", fake_file, "text/plain")}
    )
    assert response.status_code == 400
    assert "Only MP4" in response.json()["detail"]

def test_nonexistent_video_status():
    response = client.get("/api/videos/nonexistent-id/status")
    assert response.status_code == 404

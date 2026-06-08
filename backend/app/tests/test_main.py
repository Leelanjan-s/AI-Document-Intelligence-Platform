import pytest
from fastapi.testclient import TestClient
import uuid
from unittest.mock import patch

from app.main import app

client = TestClient(app)

def test_health_check():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code in [200, 503]
    data = response.json()
    assert "status" in data
    assert "components" in data

def test_login_success():
    """Test successful user login with seeded credentials."""
    response = client.post(
        "/auth/login",
        json={"email": "test@acme.com", "password": "test1234"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["email"] == "test@acme.com"
    assert data["user"]["role"] == "admin"

def test_login_invalid_credentials():
    """Test login with bad credentials returns unauthorized."""
    response = client.post(
        "/auth/login",
        json={"email": "nonexistent@acme.com", "password": "wrongpassword"}
    )
    assert response.status_code == 401

def test_refresh_token_missing():
    """Test token refresh fails without credentials."""
    client.cookies.clear()
    response = client.post("/auth/refresh", json={})
    assert response.status_code == 401

def test_document_list_unauthorized():
    """Test protected endpoints return 401 for anonymous users."""
    response = client.get("/documents")
    assert response.status_code == 401

def test_document_list_authorized():
    """Test listing documents with a valid JWT token."""
    # 1. Login to get token
    login_response = client.post(
        "/auth/login",
        json={"email": "test@acme.com", "password": "test1234"}
    )
    token = login_response.json()["access_token"]
    
    # 2. Get documents
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/documents", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)

@patch("app.api.documents.storage.upload_file_bytes")
def test_document_upload_authorized(mock_upload):
    """Test document upload with valid token."""
    mock_upload.return_value = None  # mock s3 upload
    
    # 1. Login
    login_response = client.post(
        "/auth/login",
        json={"email": "test@acme.com", "password": "test1234"}
    )
    token = login_response.json()["access_token"]
    
    # 2. Upload file
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/documents/upload",
        headers=headers,
        files={"file": ("invoice.pdf", b"dummy PDF bytes", "application/pdf")},
        data={"doc_type_id": "11111111-1111-1111-1111-111111111111"}
    )
    assert response.status_code == 201
    data = response.json()
    assert "document_id" in data
    assert data["name"] == "invoice.pdf"
    assert data["status"] == "uploaded"

def test_metrics_unauthorized():
    """Test metrics access is blocked for unauthenticated requests."""
    response = client.get("/metrics/token-usage")
    assert response.status_code == 401

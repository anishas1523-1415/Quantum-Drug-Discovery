from .conftest import register_user


def test_register_success(client):
    response = register_user(client)
    data = response.get_json()

    assert response.status_code == 201
    assert data["token"]
    assert data["user"]["email"] == "test@example.com"


def test_register_duplicate_email_rejected(client):
    register_user(client)
    response = register_user(client)

    assert response.status_code == 409
    assert "already exists" in response.get_json()["message"]


def test_register_rejects_short_password(client):
    response = register_user(client, password="123")

    assert response.status_code == 400


def test_register_rejects_invalid_email(client):
    response = register_user(client, email="not-an-email")

    assert response.status_code == 400


def test_register_requires_all_fields(client):
    response = client.post("/api/auth/register", json={"email": "a@b.com"})

    assert response.status_code == 400


def test_login_success(client):
    register_user(client)

    response = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "testpass123"},
    )

    assert response.status_code == 200
    assert response.get_json()["token"]


def test_login_wrong_password(client):
    register_user(client)

    response = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "wrongpassword"},
    )

    assert response.status_code == 401


def test_login_unknown_email(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "whatever123"},
    )

    assert response.status_code == 401


def test_me_requires_token(client):
    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_me_rejects_garbage_token(client):
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})

    assert response.status_code == 401


def test_me_returns_user_with_valid_token(client, auth_headers):
    response = client.get("/api/auth/me", headers=auth_headers)

    assert response.status_code == 200
    assert response.get_json()["user"]["email"] == "test@example.com"

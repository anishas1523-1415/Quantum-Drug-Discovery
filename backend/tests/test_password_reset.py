from app import create_app
from extensions import db
from models import User

from .conftest import register_user


def _extract_raw_token(app):
    """Reset tokens are one-way hashed at rest, so tests recover the
    raw token the same way the app does: by minting it directly."""
    with app.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        raw_token = user.issue_reset_token()
        db.session.commit()
        return raw_token


def test_forgot_password_same_response_for_unknown_email(client):
    register_user(client)

    known = client.post("/api/auth/forgot-password", json={"email": "test@example.com"})
    unknown = client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})

    assert known.status_code == 200
    assert unknown.status_code == 200
    assert known.get_json()["message"] == unknown.get_json()["message"]


def test_forgot_password_requires_email(client):
    response = client.post("/api/auth/forgot-password", json={})

    assert response.status_code == 400


def test_reset_password_rejects_invalid_token(client):
    register_user(client)

    response = client.post(
        "/api/auth/reset-password",
        json={"token": "not-a-real-token", "password": "brandnewpass"},
    )

    assert response.status_code == 400


def test_reset_password_rejects_short_password(client, app):
    register_user(client)
    raw_token = _extract_raw_token(app)

    response = client.post(
        "/api/auth/reset-password",
        json={"token": raw_token, "password": "123"},
    )

    assert response.status_code == 400


def test_reset_password_full_flow(client, app):
    register_user(client)
    raw_token = _extract_raw_token(app)

    reset_response = client.post(
        "/api/auth/reset-password",
        json={"token": raw_token, "password": "brandnewpass"},
    )
    assert reset_response.status_code == 200

    old_login = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "testpass123"},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "brandnewpass"},
    )
    assert new_login.status_code == 200


def test_reset_token_is_single_use(client, app):
    register_user(client)
    raw_token = _extract_raw_token(app)

    first = client.post(
        "/api/auth/reset-password",
        json={"token": raw_token, "password": "firstnewpass"},
    )
    second = client.post(
        "/api/auth/reset-password",
        json={"token": raw_token, "password": "secondnewpass"},
    )

    assert first.status_code == 200
    assert second.status_code == 400

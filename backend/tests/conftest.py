import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("FRONTEND_ORIGIN", "http://localhost:5173")

from app import create_app
from extensions import db


@pytest.fixture()
def app():
    application = create_app(test_config={
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "RATELIMIT_ENABLED": False,
    })

    yield application

    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def register_user(client, name="Test Doctor", email="test@example.com", password="testpass123", role=None):
    payload = {"name": name, "email": email, "password": password}
    if role is not None:
        payload["role"] = role
    return client.post("/api/auth/register", json=payload)


def login(client, email, password):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def admin_auth_headers(client):
    """The demo admin account is auto-seeded on every fresh test app (see
    create_app -> seed_demo_user), same as the demo doctor — admins can't
    self-register, so this is the realistic way tests get admin access."""

    response = login(client, "admin@gmail.com", "adminpass123")
    token = response.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def auth_token(client):
    response = register_user(client)
    return response.get_json()["token"]


@pytest.fixture()
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}

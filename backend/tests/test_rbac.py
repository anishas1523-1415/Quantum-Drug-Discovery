from unittest.mock import patch

from .conftest import admin_auth_headers, login, register_user


def auth_headers_for(client, **kwargs):
    token = register_user(client, **kwargs).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_register_defaults_to_doctor_role(client):
    response = register_user(client)

    assert response.status_code == 201
    assert response.get_json()["user"]["role"] == "doctor"


def test_register_allows_researcher_role(client):
    response = register_user(client, role="researcher")

    assert response.status_code == 201
    assert response.get_json()["user"]["role"] == "researcher"


def test_register_rejects_admin_role_self_service(client):
    response = register_user(client, role="admin")

    assert response.status_code == 400
    # The rejection must not confirm "admin" is a real role to an
    # unauthenticated caller — same generic message either way.
    assert "role" in response.get_json()["message"].lower()


def test_register_rejects_nonsense_role(client):
    response = register_user(client, role="superuser")

    assert response.status_code == 400


def test_jwt_carries_role_and_me_reflects_it(client):
    headers = auth_headers_for(client, role="researcher")

    response = client.get("/api/auth/me", headers=headers)

    assert response.status_code == 200
    assert response.get_json()["user"]["role"] == "researcher"


def test_demo_admin_account_is_seeded(client):
    response = login(client, "admin@gmail.com", "adminpass123")

    assert response.status_code == 200
    assert response.get_json()["user"]["role"] == "admin"


def test_audit_logs_endpoint_requires_auth(client):
    response = client.get("/api/admin/audit-logs")
    assert response.status_code == 401


def test_audit_logs_endpoint_rejects_non_admin(client):
    headers = auth_headers_for(client)  # default role: doctor

    response = client.get("/api/admin/audit-logs", headers=headers)

    assert response.status_code == 403


def test_audit_logs_endpoint_allows_admin(client):
    headers = admin_auth_headers(client)

    response = client.get("/api/admin/audit-logs", headers=headers)

    assert response.status_code == 200
    data = response.get_json()
    assert "entries" in data
    assert "total" in data


def test_admin_users_list_requires_admin(client):
    doctor_headers = auth_headers_for(client)
    response = client.get("/api/admin/users", headers=doctor_headers)
    assert response.status_code == 403

    admin_headers = admin_auth_headers(client)
    response = client.get("/api/admin/users", headers=admin_headers)
    assert response.status_code == 200
    emails = [u["email"] for u in response.get_json()["users"]]
    assert "admin@gmail.com" in emails
    assert "doctor@gmail.com" in emails


@patch("services.target_identification._graphql")
def test_researcher_can_use_recommend_same_as_doctor(mock_graphql, client):
    """Both self-registerable roles should have equal access to the core
    analysis features — the role distinction is about administrative
    capability, not gatekeeping the actual clinical workflow."""

    mock_graphql.return_value = {"search": {"hits": []}}

    headers = auth_headers_for(client, role="researcher")
    response = client.get("/api/recommend?gene=EGFR&cancer_type=Lung", headers=headers)

    assert response.status_code == 200

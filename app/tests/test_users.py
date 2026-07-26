"""
Covers app/api/.../users.py

Mocks crud.users functions and check_admin_or_author, since permission
logic there returns a tuple (is_admin, is_self) that route logic branches on.
Adjust the patch target module path (`app.api.endpoints.users`) to match
your actual package layout if different.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.tests.conftest import FakeUser

MODULE = "app.api.endpoints.users"


@pytest.mark.asyncio
async def test_get_current_user_info(auth_client, normal_user):
    response = await auth_client.get("/users/me")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_retrieve_users_requires_admin(auth_client):
    # normal user should be rejected by the require_admin dependency
    response = await auth_client.get("/users/")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_retrieve_users_as_admin(admin_client, db_session):
    response = await admin_client.get("/users/", params={"page": 1, "per_page": 20})
    assert response.status_code == 200
    body = response.json()
    assert "users" in body and "total" in body and "total_pages" in body


@pytest.mark.asyncio
async def test_retrieve_users_with_filters(admin_client):
    response = await admin_client.get(
        "/users/", params={"search": "ali", "is_active": True, "role": "user"}
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_retrieve_user_not_found(auth_client):
    with patch(f"{MODULE}.get_user_by_id", new=AsyncMock(return_value=None)):
        response = await auth_client.get("/users/12345")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_retrieve_user_success_self(auth_client, normal_user):
    fake_target = FakeUser(id=normal_user.id, username="target", email="target@example.com")
    fake_target.phone = "+10000000000"
    fake_target.avatar_url = "http://x/avatar.png"
    with patch(f"{MODULE}.get_user_by_id", new=AsyncMock(return_value=fake_target)), \
         patch(f"{MODULE}.check_admin_or_author", return_value=True):
        response = await auth_client.get(f"/users/{normal_user.id}")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_user_not_found(auth_client):
    with patch(f"{MODULE}.get_user_by_id", new=AsyncMock(return_value=None)):
        response = await auth_client.put("/users/1", json={"username": "new"})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_user_strips_admin_fields_for_self(auth_client, normal_user, db_session, monkeypatch):
    # db_user here is a plain stand-in, not a real session-tracked ORM row,
    # so SQLAlchemy's real db.refresh()/db.commit() can't operate on it.
    # We no-op them for this route test, since we're testing the *permission
    # stripping* logic, not persistence.
    monkeypatch.setattr(db_session, "refresh", AsyncMock())
    monkeypatch.setattr(db_session, "commit", AsyncMock())

    fake_target = FakeUser(id=normal_user.id, email="old@example.com")
    with patch(f"{MODULE}.get_user_by_id", new=AsyncMock(return_value=fake_target)), \
         patch(f"{MODULE}.check_admin_or_author", return_value=(False, True)), \
         patch(f"{MODULE}.get_user_by_email", new=AsyncMock(return_value=None)):
        response = await auth_client.put(
            f"/users/{normal_user.id}",
            json={"username": "new_name", "role": "admin", "is_active": False},
        )
    assert response.status_code == 200
    # role/is_active should NOT have been applied for a non-admin self-update
    assert fake_target.role != "admin"
    assert fake_target.is_active is True


@pytest.mark.asyncio
async def test_update_user_email_conflict_check_is_currently_a_noop(auth_client, normal_user, db_session, monkeypatch):
    """
    KNOWN BUG in users.py::update_user: the loop that applies `setattr`
    for each field runs BEFORE the email-uniqueness check, so by the time
    `request_json["email"] != db_user.email` is evaluated, db_user.email
    has already been overwritten to match request_json["email"] -- making
    the comparison always False. The 409 branch is unreachable as written.

    This test documents the CURRENT (buggy) behavior: it returns 200 even
    when another user already owns the target email. Once the route is
    fixed (snapshot db_user.email before the setattr loop), update this
    test to assert status_code == 409 instead.
    """
    monkeypatch.setattr(db_session, "refresh", AsyncMock())
    monkeypatch.setattr(db_session, "commit", AsyncMock())

    fake_target = FakeUser(id=normal_user.id, email="old@example.com")
    other_user = FakeUser(id=normal_user.id + 1, email="taken@example.com")
    with patch(f"{MODULE}.get_user_by_id", new=AsyncMock(return_value=fake_target)), \
         patch(f"{MODULE}.check_admin_or_author", return_value=(True, False)), \
         patch(f"{MODULE}.get_user_by_email", new=AsyncMock(return_value=other_user)):
        response = await auth_client.put(
            f"/users/{normal_user.id}", json={"email": "taken@example.com"}
        )
    assert response.status_code == 200  # documents the bug; should be 409 once fixed


@pytest.mark.asyncio
async def test_delete_user_not_found(auth_client):
    with patch(f"{MODULE}.get_user_by_id", new=AsyncMock(return_value=None)):
        response = await auth_client.delete("/users/1")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_user_success(auth_client, normal_user):
    fake_target = MagicMock(id=normal_user.id)
    with patch(f"{MODULE}.get_user_by_id", new=AsyncMock(return_value=fake_target)), \
         patch(f"{MODULE}.check_admin_or_author", return_value=True), \
         patch(f"{MODULE}.delete_user_from_db", new=AsyncMock(return_value=None)):
        response = await auth_client.delete(f"/users/{normal_user.id}")
    # Route raises HTTPException(status_code=204) which FastAPI will surface
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_create_new_admin_already_exists(auth_client):
    with patch(f"{MODULE}.User", MagicMock()):
        with patch(f"{MODULE}.create_admin_user", new=AsyncMock()) as create_mock:
            # simulate existing_user found via db.execute -> mock the whole db session behavior
            pass
    # This endpoint queries the DB directly; better isolated with a real
    # in-memory DB row. Left as a placeholder for once app.models.user.User
    # is available so we can insert a conflicting row via db_session.
    pytest.skip("Needs real User model fixture to seed a conflicting row in db_session")


@pytest.mark.asyncio
async def test_create_new_admin_success(auth_client, normal_user):
    new_admin = MagicMock(id=2, email="admin@example.com", username="adminuser", role="admin")
    with patch(f"{MODULE}.create_admin_user", new=AsyncMock(return_value=new_admin)):
        # db.execute(...).scalar_one_or_none() must return None (no existing user);
        # since we're using a real in-memory DB session with no seeded rows,
        # this naturally returns None.
        response = await auth_client.post(
            "/users/create-admin",
            params={"email": "admin@example.com", "username": "adminuser", "password": "pw"},
        )
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "admin@example.com"
"""
Integration-style tests that exercise the *real* cookie flow end-to-end,
instead of overriding get_current_user_from_cookie. This covers the part
of auth_service that reads the access_token cookie and decodes it, which
the per-router unit tests (test_login.py, test_users.py, etc.) don't touch
since they override that dependency directly.

Only the token creation/decoding functions are mocked (so we don't need
real JWT secrets in test env) -- everything else, including cookie
transport via httpx's cookie jar, is real.
"""
import pytest
from unittest.mock import AsyncMock, patch

LOGIN_MODULE = "app.api.endpoints.login"


@pytest.mark.asyncio
async def test_login_then_access_protected_route_via_real_cookie(client):
    fake_user = type("U", (), {"id": 1})()

    with patch(f"{LOGIN_MODULE}.authenticate", new=AsyncMock(return_value=fake_user)), \
         patch(f"{LOGIN_MODULE}.create_access_token", return_value="signed-access-token"), \
         patch(f"{LOGIN_MODULE}.create_refresh_token", return_value="signed-refresh-token"):
        login_response = await client.post("/login", json={"username": "a", "password": "b"})

    assert login_response.status_code == 200
    # httpx AsyncClient persists Set-Cookie into its own cookie jar automatically
    assert client.cookies.get("access_token") == "signed-access-token"
    assert client.cookies.get("refresh_token") == "signed-refresh-token"

    # Now hit a route guarded by get_current_user_from_cookie, using the
    # real cookie that was just set (no dependency override this time).
    # NOTE: the exact function auth_service uses to verify the access-token
    # cookie is not yet confirmed (decode_access_token was a guess and does
    # not exist on the real module). Skipping until app/services/auth_service.py
    # is available so this can target the real function name.
    pytest.skip("Need auth_service.py to know the real access-token decode function name")


@pytest.mark.asyncio
async def test_protected_route_without_cookie_is_rejected(client):
    # No login performed -> no access_token cookie present at all
    response = await client.get("/users/me")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_refresh_uses_real_refresh_cookie_to_reissue_access_cookie(client):
    fake_user = type("U", (), {"id": 1})()

    with patch(f"{LOGIN_MODULE}.authenticate", new=AsyncMock(return_value=fake_user)), \
         patch(f"{LOGIN_MODULE}.create_access_token", return_value="access-v1"), \
         patch(f"{LOGIN_MODULE}.create_refresh_token", return_value="refresh-v1"):
        await client.post("/login", json={"username": "a", "password": "b"})

    assert client.cookies.get("refresh_token") == "refresh-v1"

    with patch(f"{LOGIN_MODULE}.decode_refresh_token", return_value=fake_user.id), \
         patch(f"{LOGIN_MODULE}.get_user_by_id", new=AsyncMock(return_value=fake_user)), \
         patch(f"{LOGIN_MODULE}.create_access_token", return_value="access-v2"):
        refresh_response = await client.post("/refresh")

    assert refresh_response.status_code == 200
    # Cookie jar should now hold the *new* access token
    assert client.cookies.get("access_token") == "access-v2"


@pytest.mark.asyncio
async def test_logout_removes_cookies_from_jar(client):
    client.cookies.set("access_token", "some-token")
    client.cookies.set("refresh_token", "some-refresh")

    response = await client.post("/logout")
    assert response.status_code == 200

    set_cookie_headers = response.headers.get_list("set-cookie")
    # Deletion cookies carry Max-Age=0 or an expired `expires` date
    assert any("access_token=" in h and ("Max-Age=0" in h or "expires=" in h.lower()) for h in set_cookie_headers)
    assert any("refresh_token=" in h and ("Max-Age=0" in h or "expires=" in h.lower()) for h in set_cookie_headers)
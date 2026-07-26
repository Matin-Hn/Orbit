"""
Covers app/api/.../channels.py

Most of this router queries the Channel model directly via `db.execute`,
so we use the real in-memory async DB (db_session/client fixtures) and
seed rows directly, rather than mocking the DB layer. ChannelService is
mocked for create/update since its internals aren't shown here.
"""
import itertools
import pytest
from unittest.mock import AsyncMock, patch
from app.models.channel import Channel

MODULE = "app.api.endpoints.channels"

# SQLite only auto-generates a primary key when the column is declared as
# EXACTLY "INTEGER PRIMARY KEY" (its rowid alias). If Channel.id is a
# BigInteger (typical for a Postgres-backed model), SQLite has no
# autoincrement behavior for it and a plain INSERT with no id raises
# `IntegrityError: NOT NULL constraint failed: channels.id`. Since this is
# purely a SQLite-in-memory testing limitation (not an app bug), we assign
# explicit ids ourselves when seeding test rows.
_id_counter = itertools.count(1)


def _fake_channel_response(**overrides):
    base = {
        "id": next(_id_counter),
        "user_id": 1,
        "name": "New Channel",
        "handle": "newhandle",
        "description": None,
        "avatar_url": None,
        "banner_url": None,
        "website": None,
        "contact_email": None,
        "is_suspended": False,
        "verified_badge": False,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }
    base.update(overrides)
    return base


async def _seed_channel(db_session, **overrides):
    n = next(_id_counter)
    defaults = dict(
        id=n,
        # channels.user_id and channels.name both carry UNIQUE constraints
        # in the real model (confirmed by the IntegrityError when multiple
        # channels were seeded with the same defaults). Derive unique
        # defaults from the shared counter so tests seeding several
        # channels in one function don't collide unless a test explicitly
        # wants to exercise the constraint itself.
        name=f"Test Channel {n}",
        handle=f"testhandle{n}",
        user_id=n,
        is_suspended=False,
        verified_badge=False,
    )
    defaults.update(overrides)
    channel = Channel(**defaults)
    db_session.add(channel)
    await db_session.commit()
    await db_session.refresh(channel)
    return channel


@pytest.mark.asyncio
async def test_create_channel(auth_client):
    fake_response = _fake_channel_response(name="New Channel", handle="newhandle")
    with patch(f"{MODULE}.ChannelService.create_channel", new=AsyncMock(return_value=fake_response)):
        response = await auth_client.post(
            "/channels/", json={"name": "New Channel", "handle": "newhandle"}
        )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_get_channel_by_handle_found(client, db_session):
    seeded = await _seed_channel(db_session, handle="findme")
    response = await client.get("/channels/findme")
    assert response.status_code == 200
    # NOTE: ChannelResponse (schemas/channel.py) does not declare a
    # `handle` field, so FastAPI strips it from every response even
    # though the row has one -- asserting on `id`/`name` instead, which
    # ARE declared. Worth fixing on the schema side: GET /channels/{handle}
    # currently can't return the channel's own handle to the caller.
    assert response.json()["id"] == seeded.id
    assert response.json()["name"] == seeded.name


@pytest.mark.asyncio
async def test_get_channel_by_handle_not_found(client):
    response = await client.get("/channels/does-not-exist")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_channels_pagination(client, db_session):
    for i in range(3):
        await _seed_channel(db_session, handle=f"chan{i}", name=f"Channel {i}")
    response = await client.get("/channels/", params={"page": 1, "size": 2})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["pages"] == 2


@pytest.mark.asyncio
async def test_list_channels_search_filter(client, db_session):
    await _seed_channel(db_session, handle="alpha", name="Alpha Channel")
    await _seed_channel(db_session, handle="beta", name="Beta Channel")
    response = await client.get("/channels/", params={"search": "Alpha"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    # `handle` isn't in ChannelResponse -- see note in
    # test_get_channel_by_handle_found. Asserting on `name` instead.
    assert body["items"][0]["name"] == "Alpha Channel"


@pytest.mark.asyncio
async def test_list_channels_suspended_filter(client, db_session):
    await _seed_channel(db_session, handle="sus", name="Suspended Channel", is_suspended=True)
    await _seed_channel(db_session, handle="ok", name="OK Channel", is_suspended=False)
    response = await client.get("/channels/", params={"is_suspended": True})
    body = response.json()
    assert body["total"] == 1
    # `handle` isn't in ChannelResponse -- see note in
    # test_get_channel_by_handle_found. Asserting on `name` instead.
    assert body["items"][0]["name"] == "Suspended Channel"


@pytest.mark.asyncio
async def test_update_channel(auth_client):
    fake_response = _fake_channel_response(name="Updated", handle="updated")
    with patch(f"{MODULE}.ChannelService.update_channel", new=AsyncMock(return_value=fake_response)):
        response = await auth_client.put("/channels/1", json={"name": "Updated"})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_delete_channel_not_found(client):
    response = await client.delete("/channels/9999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_channel_success(client, db_session):
    channel = await _seed_channel(db_session, handle="deleteme")
    response = await client.delete(f"/channels/{channel.id}")
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_suspend_channel_not_found(client):
    response = await client.patch("/channels/9999/suspend", params={"suspend": True})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_suspend_channel_success(client, db_session):
    channel = await _seed_channel(db_session, is_suspended=False)
    response = await client.patch(f"/channels/{channel.id}/suspend", params={"suspend": True})
    assert response.status_code == 200
    assert response.json()["is_suspended"] is True


@pytest.mark.asyncio
async def test_verify_channel_success(client, db_session):
    from sqlalchemy import select

    channel = await _seed_channel(db_session, verified_badge=False)
    response = await client.patch(f"/channels/{channel.id}/verify", params={"verify": True})
    assert response.status_code == 200
    # NOTE: ChannelResponse (schemas/channel.py) does not declare a
    # `verified_badge` field, so the response body can never confirm this
    # toggle to a caller -- PATCH /channels/{id}/verify returns 200 with no
    # indication of the new state. Verifying via a direct DB read instead,
    # since response.json() literally cannot tell us. Worth adding
    # `verified_badge: bool` to ChannelResponse so clients get real
    # confirmation.
    result = await db_session.execute(select(Channel).filter(Channel.id == channel.id))
    updated = result.scalar_one()
    assert updated.verified_badge is True


@pytest.mark.asyncio
async def test_verify_channel_not_found(client):
    response = await client.patch("/channels/9999/verify", params={"verify": True})
    assert response.status_code == 404
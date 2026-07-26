"""
Covers app/api/.../public.py (get_video)

This route touches: get_video_by_public_id, db.refresh (lazy relationships),
reaction_crud, and VideoStatsCounter(redis).likes.get(). We mock everything
except the redis dependency (uses fakeredis) to exercise the real Redis
counter code path if it's simple, or mock VideoStatsCounter itself if it
does more (e.g. touches DB aggregates) -- shown here fully mocked for
isolation.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

MODULE = "app.api.endpoints.public"


class _FakeChannel:
    def __init__(self, name="Test Channel", user_id=1):
        self.name = name
        self.user_id = user_id


class _FakeStats:
    def __init__(self, comments_count=3, views_count=100):
        self.comments_count = comments_count
        self.views_count = views_count


class _FakeVideo:
    """
    Plain object (not MagicMock) standing in for the ORM Video instance.
    Using MagicMock here breaks Pydantic response_model serialization
    (raises AttributeError: _mock_methods when FastAPI tries to read real
    attributes off a Mock), so a plain class is used instead.
    """

    def __init__(self, channel=None, stats=None):
        # Route checks `"channel" not in video.__dict__` to decide whether
        # to await db.refresh() (simulating an unloaded SQLAlchemy
        # relationship). Plain instance attributes land in __dict__
        # naturally, so setting them directly (not via @property) makes
        # that check pass and skips the refresh branch, which would
        # otherwise try to call db.refresh() on this fake object and fail.
        self.channel = channel if channel is not None else _FakeChannel()
        self.stats = stats if stats is not None else _FakeStats()
        self.id = 10
        self.status = "ready"
        self.title = "Test video"
        self.description = "desc"
        self.channel_id = 1
        self.duration_seconds = 120
        self.thumbnail_url = "http://x/thumb.jpg"
        self.hls_manifest_url = "http://x/manifest.m3u8"
        self.sprite_url = None
        self.sprite_vtt_url = None
        self.sprite_tile_width = None
        self.sprite_tile_height = None
        self.sprite_columns = None
        self.sprite_rows = None
        self.created_at = "2024-01-01T00:00:00Z"
        self.file_url = "http://x/file.mp4"
        self.is_published = True
        self.published_at = "2024-01-01T00:00:00Z"
        self.updated_at = "2024-01-01T00:00:00Z"


def _fake_video(with_reaction_field=True):
    return _FakeVideo()


@pytest.mark.asyncio
async def test_get_video_anonymous(client):
    video = _fake_video()
    with patch(f"{MODULE}.get_video_by_public_id", new=AsyncMock(return_value=video)), \
         patch(f"{MODULE}.VideoStatsCounter") as mock_counter_cls:
        mock_counter_cls.return_value.likes.get = AsyncMock(return_value=42)
        response = await client.get("/videos/abc123")

    assert response.status_code == 200
    body = response.json()
    assert body["like_count"] == 42
    assert body["current_user_reaction"] is None
    assert body["can_edit"] is False


@pytest.mark.asyncio
async def test_get_video_authenticated_with_reaction(auth_client, normal_user):
    video = _fake_video()
    video.channel.user_id = normal_user.id  # owner matches -> can_edit True
    fake_reaction = MagicMock()
    fake_reaction.type.value = "like"

    with patch(f"{MODULE}.get_video_by_public_id", new=AsyncMock(return_value=video)), \
         patch(f"{MODULE}.reaction_crud.get_by_video_and_user", new=AsyncMock(return_value=fake_reaction)), \
         patch(f"{MODULE}.VideoStatsCounter") as mock_counter_cls:
        mock_counter_cls.return_value.likes.get = AsyncMock(return_value=7)
        response = await auth_client.get("/videos/abc123")

    assert response.status_code == 200
    body = response.json()
    assert body["current_user_reaction"] == "like"
    assert body["can_edit"] is True
    assert body["like_count"] == 7


@pytest.mark.asyncio
async def test_get_video_no_reaction_found(auth_client):
    video = _fake_video()
    with patch(f"{MODULE}.get_video_by_public_id", new=AsyncMock(return_value=video)), \
         patch(f"{MODULE}.reaction_crud.get_by_video_and_user", new=AsyncMock(return_value=None)), \
         patch(f"{MODULE}.VideoStatsCounter") as mock_counter_cls:
        mock_counter_cls.return_value.likes.get = AsyncMock(return_value=0)
        response = await auth_client.get("/videos/abc123")

    assert response.status_code == 200
    assert response.json()["current_user_reaction"] is None


@pytest.mark.asyncio
async def test_get_video_missing_stats_defaults_to_zero(client):
    video = _fake_video()
    video.stats = None
    with patch(f"{MODULE}.get_video_by_public_id", new=AsyncMock(return_value=video)), \
         patch(f"{MODULE}.VideoStatsCounter") as mock_counter_cls:
        mock_counter_cls.return_value.likes.get = AsyncMock(return_value=0)
        response = await client.get("/videos/abc123")

    assert response.status_code == 200
    body = response.json()
    assert body["comment_count"] == 0
    assert body["view_count"] == 0
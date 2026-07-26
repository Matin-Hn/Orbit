"""
Covers app/api/.../comments.py

CommentService and get_video_by_public_id are mocked entirely: this router
is a thin pass-through to CommentService, so route tests focus on:
- correct status codes
- correct data flowing from path/query params into service calls
- optional-auth branch (get_optional_current_user_from_cookie) for public list
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

MODULE = "app.api.endpoints.comments"

# GUESS: CommentResponse's exact required fields aren't known (schema file
# not shared yet). This produced a ResponseValidationError with 8 missing
# fields on the minimal stub. Expanded to a plausible shape below -- if it
# still fails, share app/schemas/comment.py and I'll match it exactly.
def _fake_comment_response(**overrides):
    base = {
        "id": 5,
        "body": "a comment",
        "video_id": 10,
        "user_id": 1,
        "username": "testuser",
        "parent_id": None,
        "is_approved": True,
        "is_pinned": False,
        "is_edited": False,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "replies_count": 0,
        "like_count": 0,
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_create_comment(auth_client):
    fake_video = MagicMock(id=10)
    fake_comment_response = _fake_comment_response(id=1, body="hello", video_id=10)
    with patch(f"{MODULE}.get_video_by_public_id", new=AsyncMock(return_value=fake_video)), \
         patch(f"{MODULE}.CommentService.create_comment", new=AsyncMock(return_value=fake_comment_response)):
        response = await auth_client.post(
            "/comments/", json={"public_id": "abc123", "body": "hello"}
        )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_get_comment_public_access(client):
    fake_comment = _fake_comment_response(id=5, body="public comment")
    with patch(f"{MODULE}.CommentService.get_comment", new=AsyncMock(return_value=fake_comment)):
        response = await client.get("/comments/5")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_comment_invalid_id_rejected_by_validation(client):
    response = await client.get("/comments/0")  # gt=0 constraint
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_video_comments_anonymous(client):
    fake_video = MagicMock(id=10)
    fake_list = {"comments": [], "total": 0, "page": 1, "per_page": 20, "total_pages": 0}
    with patch(f"{MODULE}.get_video_by_public_id", new=AsyncMock(return_value=fake_video)), \
         patch(f"{MODULE}.CommentService.get_video_comments", new=AsyncMock(return_value=fake_list)):
        response = await client.get("/comments/video/abc123")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_video_comments_sort_by_popular(auth_client):
    fake_video = MagicMock(id=10)
    fake_list = {"comments": [], "total": 0, "page": 1, "per_page": 20, "total_pages": 0}
    with patch(f"{MODULE}.get_video_by_public_id", new=AsyncMock(return_value=fake_video)), \
         patch(f"{MODULE}.CommentService.get_video_comments", new=AsyncMock(return_value=fake_list)) as mock_svc:
        response = await auth_client.get(
            "/comments/video/abc123", params={"sort_by": "popular"}
        )
    assert response.status_code == 200
    _, kwargs = mock_svc.call_args
    assert kwargs["sort_by"] == "popular"


@pytest.mark.asyncio
async def test_get_video_comments_invalid_sort_rejected(client):
    response = await client.get("/comments/video/abc123", params={"sort_by": "invalid"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_comment_replies(client):
    fake_replies = {"comments": [], "total": 0, "page": 1, "per_page": 10, "total_pages": 0}
    with patch(f"{MODULE}.CommentService.get_comment_replies", new=AsyncMock(return_value=fake_replies)):
        response = await client.get("/comments/5/replies")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_comment(auth_client):
    fake_response = _fake_comment_response(id=5, body="edited")
    with patch(f"{MODULE}.CommentService.update_comment", new=AsyncMock(return_value=fake_response)):
        response = await auth_client.put("/comments/5", json={"body": "edited"})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_delete_comment(auth_client):
    with patch(f"{MODULE}.CommentService.delete_comment", new=AsyncMock(return_value=None)):
        response = await auth_client.delete("/comments/5")
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_approve_comment(auth_client):
    fake_response = _fake_comment_response(id=5, is_approved=True)
    with patch(f"{MODULE}.CommentService.approve_comment", new=AsyncMock(return_value=fake_response)):
        response = await auth_client.post("/comments/5/approve")
    assert response.status_code == 200
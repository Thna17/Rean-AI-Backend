from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from api.routes import chat as chat_route
from api.routes import ai_tutor_chat as ai_tutor_route
from api.core.auth import AuthenticatedUser


@pytest.fixture
def mock_chat_db():
    db = MagicMock()

    chat_messages = MagicMock()
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.limit.return_value = cursor
    cursor.to_list = AsyncMock(return_value=[])
    chat_messages.find.return_value = cursor

    def get_collection(name):
        if name == "chat_messages":
            return chat_messages
        return AsyncMock()

    db.__getitem__.side_effect = get_collection
    return db



@pytest.fixture
def mock_ai_tutor_db():
    db = MagicMock()

    ai_tutor_sessions = MagicMock()
    ai_tutor_sessions.find_one = AsyncMock(return_value=None)

    ai_tutor_messages = MagicMock()
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.to_list = AsyncMock(return_value=[])
    ai_tutor_messages.find.return_value = cursor

    def get_collection(name):
        if name == "ai_tutor_sessions":
            return ai_tutor_sessions
        if name == "ai_tutor_messages":
            return ai_tutor_messages
        return AsyncMock()

    db.__getitem__.side_effect = get_collection
    return db


@pytest.fixture
def mock_ai_tutor_store(monkeypatch):
    store = MagicMock()
    store.get_session = AsyncMock(return_value=None)
    store.get_messages = AsyncMock(return_value=[])
    store.set_session = AsyncMock()
    store.delete_messages = AsyncMock()
    store.append_message = AsyncMock()
    monkeypatch.setattr(ai_tutor_route, "_store", store)
    return store


@pytest.mark.asyncio
async def test_chat_messages_limit_positive_uses_limit_cursor(mock_chat_db):
    cursor = mock_chat_db["chat_messages"].find.return_value
    cursor.to_list = AsyncMock(
        return_value=[
            {
                "role": "user",
                "content": "hello",
                "timestamp": datetime.utcnow(),
            }
        ]
    )

    result = await chat_route.get_session_messages(
        session_id="chat_s1",
        limit=1,
        db=mock_chat_db,
    )

    assert len(result) == 1
    cursor.limit.assert_called_once_with(1)
    cursor.to_list.assert_awaited_once_with(length=1)


@pytest.mark.asyncio
async def test_ai_tutor_messages_returns_cached_when_cache_is_complete(mock_ai_tutor_db, mock_ai_tutor_store):
    mock_ai_tutor_db["ai_tutor_sessions"].find_one.return_value = {
        "session_id": "ai_tutor_s1",
        "message_count": 2,
    }
    mock_ai_tutor_store.get_session.return_value = {
        "session_id": "ai_tutor_s1",
        "user_id": "u1",
    }
    mock_ai_tutor_store.get_messages.return_value = [
        {"id": "m1", "role": "user", "content": "hello", "timestamp": "2026-04-16T10:00:00"},
        {"id": "m2", "role": "assistant", "content": "hi", "timestamp": "2026-04-16T10:00:01"},
    ]

    result = await ai_tutor_route.get_ai_tutor_messages(
        session_id="ai_tutor_s1",
        db=mock_ai_tutor_db,
        current_user=AuthenticatedUser(user_id="u1", claims={}),
        full=True,
    )

    assert result["success"] is True
    assert len(result["messages"]) == 2
    mock_ai_tutor_db["ai_tutor_messages"].find.assert_not_called()


@pytest.mark.asyncio
async def test_ai_tutor_messages_uses_cached_payload_when_session_doc_missing(mock_ai_tutor_db, mock_ai_tutor_store):
    mock_ai_tutor_db["ai_tutor_sessions"].find_one.return_value = None
    mock_ai_tutor_store.get_session.return_value = {
        "session_id": "ai_tutor_s1",
        "user_id": "u1",
    }
    mock_ai_tutor_store.get_messages.return_value = [
        {"id": "m1", "role": "user", "content": "cached", "timestamp": "2026-04-16T10:00:00"}
    ]

    result = await ai_tutor_route.get_ai_tutor_messages(
        session_id="ai_tutor_s1",
        db=mock_ai_tutor_db,
        current_user=AuthenticatedUser(user_id="u1", claims={}),
        full=True,
    )

    assert result["success"] is True
    assert len(result["messages"]) == 1
    assert result["messages"][0]["content"] == "cached"


@pytest.mark.asyncio
async def test_ai_tutor_messages_raises_404_when_no_db_and_no_cache(mock_ai_tutor_db, mock_ai_tutor_store):
    mock_ai_tutor_db["ai_tutor_sessions"].find_one.return_value = None
    mock_ai_tutor_store.get_session.return_value = None

    with pytest.raises(HTTPException) as exc:
        await ai_tutor_route.get_ai_tutor_messages(
            session_id="missing",
            db=mock_ai_tutor_db,
            current_user=AuthenticatedUser(user_id="u1", claims={}),
            full=True,
        )

    assert exc.value.status_code == 404

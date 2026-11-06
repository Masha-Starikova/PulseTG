from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from telethon.errors import (
    BadRequestError,
    ChannelPrivateError,
    FloodWaitError,
    ServerError,
    TimedOutError,
    UsernameInvalidError,
    UsernameNotOccupiedError,
)

from backend.telegram.session_manager import TelegramSessionError
from backend.telegram.telegram_collector import TelegramCollectorError, get_channel_posts


def make_message(
    message_id: int = 1,
    age_days: int = 1,
    text: str | None = "текст",
    views: int | None = 100,
    forwards: int | None = 5,
    reactions: list[int] | None = None,
    replies: int | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=message_id,
        date=datetime.now(tz=UTC) - timedelta(days=age_days),
        message=text,
        views=views,
        forwards=forwards,
        reactions=(
            SimpleNamespace(results=[SimpleNamespace(count=count) for count in reactions])
            if reactions
            else None
        ),
        replies=SimpleNamespace(replies=replies) if replies is not None else None,
    )


def make_client(messages: list[SimpleNamespace] | None = None) -> MagicMock:
    async def iter_messages(_entity: object) -> AsyncIterator[SimpleNamespace]:
        for message in messages or []:
            yield message

    client = MagicMock()
    client.get_entity = AsyncMock(return_value=object())
    client.iter_messages = iter_messages
    client.is_connected.return_value = True
    client.disconnect = AsyncMock()
    return client


@pytest.fixture
def connect(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock = AsyncMock()
    monkeypatch.setattr("backend.telegram.telegram_collector.get_telegram_client", mock)
    return mock


async def test_maps_telegram_message_to_post(connect: AsyncMock) -> None:
    connect.return_value = make_client([make_message(message_id=7, reactions=[3, 4], replies=2)])

    posts = await get_channel_posts("@channel")

    assert len(posts) == 1
    post = posts[0]
    assert (post["id"], post["text"], post["views"]) == (7, "текст", 100)
    assert (post["reactions"], post["forwards"], post["comments_count"]) == (7, 5, 2)
    connect.return_value.get_entity.assert_awaited_once_with("channel")


async def test_message_without_counters_gives_zeroes(connect: AsyncMock) -> None:
    connect.return_value = make_client([make_message(text=None, views=None, forwards=None)])

    post = (await get_channel_posts("channel"))[0]

    assert (post["text"], post["views"], post["forwards"], post["reactions"]) == ("", 0, 0, 0)


async def test_stops_at_period_boundary(connect: AsyncMock) -> None:
    messages = [make_message(1, age_days=1), make_message(2, age_days=29), make_message(3, age_days=31)]
    connect.return_value = make_client(messages)

    posts = await get_channel_posts("channel", days=30)

    assert [post["id"] for post in posts] == [1, 2]


async def test_skips_messages_without_date(connect: AsyncMock) -> None:
    undated = make_message(1)
    undated.date = None
    connect.return_value = make_client([undated, make_message(2)])

    posts = await get_channel_posts("channel")

    assert [post["id"] for post in posts] == [2]


async def test_client_is_disconnected_even_after_error(connect: AsyncMock) -> None:
    client = make_client()
    client.get_entity.side_effect = UsernameInvalidError(request=None)
    connect.return_value = client

    with pytest.raises(TelegramCollectorError):
        await get_channel_posts("channel")

    client.disconnect.assert_awaited_once()


@pytest.mark.parametrize(
    ("username", "days"),
    [("", 30), ("  @ ", 30), ("channel", 0), ("channel", -1)],
)
async def test_bad_arguments_fail_before_connecting(connect: AsyncMock, username: str, days: int) -> None:
    with pytest.raises(TelegramCollectorError):
        await get_channel_posts(username, days=days)

    connect.assert_not_awaited()


@pytest.mark.parametrize(
    "error",
    [UsernameInvalidError(request=None), UsernameNotOccupiedError(request=None)],
    ids=["invalid", "not-occupied"],
)
async def test_unknown_channel_gives_clear_message(connect: AsyncMock, error: Exception) -> None:
    client = make_client()
    client.get_entity.side_effect = error
    connect.return_value = client

    with pytest.raises(TelegramCollectorError, match="Канал не найден") as exc_info:
        await get_channel_posts("channel")

    assert exc_info.value.retryable is False


async def test_nonexistent_channel_as_reported_by_telethon(connect: AsyncMock) -> None:
    """get_entity превращает UsernameNotOccupiedError в ValueError, это его настоящее поведение."""
    client = make_client()
    client.get_entity.side_effect = ValueError('No user has "channel" as username')
    connect.return_value = client

    with pytest.raises(TelegramCollectorError, match="Канал не найден") as exc_info:
        await get_channel_posts("channel")

    assert exc_info.value.retryable is False


async def test_private_channel_gives_clear_message(connect: AsyncMock) -> None:
    client = make_client()
    client.get_entity.side_effect = ChannelPrivateError(request=None)
    connect.return_value = client

    with pytest.raises(TelegramCollectorError, match="приватный") as exc_info:
        await get_channel_posts("channel")

    assert exc_info.value.retryable is False


async def test_flood_wait_is_temporary_and_reports_seconds(connect: AsyncMock) -> None:
    client = make_client()
    client.get_entity.side_effect = FloodWaitError(request=None, capture=120)
    connect.return_value = client

    with pytest.raises(TelegramCollectorError, match="120 сек") as exc_info:
        await get_channel_posts("channel")

    assert exc_info.value.retryable is True
    assert exc_info.value.retry_after == 120


@pytest.mark.parametrize(
    "error",
    [
        ServerError(request=None, message="INTERNAL"),
        TimedOutError(request=None, message="Timeout"),
        ConnectionError("Connection to Telegram failed"),
        TimeoutError(),
    ],
    ids=["server-error", "rpc-timeout", "connection", "timeout"],
)
async def test_network_and_server_errors_are_temporary(connect: AsyncMock, error: Exception) -> None:
    client = make_client()
    client.get_entity.side_effect = error
    connect.return_value = client

    with pytest.raises(TelegramCollectorError) as exc_info:
        await get_channel_posts("channel")

    assert exc_info.value.retryable is True


@pytest.mark.parametrize(
    "error",
    [BadRequestError(request=None, message="SOMETHING_ELSE"), KeyError("bug")],
    ids=["other-rpc", "unexpected"],
)
async def test_other_errors_are_permanent(connect: AsyncMock, error: Exception) -> None:
    client = make_client()
    client.get_entity.side_effect = error
    connect.return_value = client

    with pytest.raises(TelegramCollectorError) as exc_info:
        await get_channel_posts("channel")

    assert exc_info.value.retryable is False


async def test_session_problem_is_reported(connect: AsyncMock) -> None:
    connect.side_effect = TelegramSessionError("Session-файл не найден")

    with pytest.raises(TelegramCollectorError, match="Session-файл") as exc_info:
        await get_channel_posts("channel")

    assert exc_info.value.retryable is False

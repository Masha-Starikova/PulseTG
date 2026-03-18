from __future__ import annotations

from datetime import datetime
from math import ceil
from typing import Any, TypedDict


class PostData(TypedDict, total=False):
    id: int
    date: str
    text: str
    views: int
    reactions: int
    comments_count: int
    comments: int


def calculate_metrics(posts: list[PostData]) -> dict[str, Any]:
    """Считает агрегированные метрики по списку постов и возвращает JSON-структуру."""

    normalized_posts: list[dict[str, Any]] = []
    parsed_dates: list[datetime] = []

    for post in posts:
        views = max(_to_int(post.get("views", 0)), 0)
        reactions = max(_to_int(post.get("reactions", 0)), 0)

        # Поддерживаем оба ключа: comments_count (основной) и comments (резервный).
        comments = max(_to_int(post.get("comments_count", post.get("comments", 0))), 0)

        text = str(post.get("text", "") or "")
        text_length = len(text)

        post_date = _parse_datetime(post.get("date"))
        if post_date is not None:
            parsed_dates.append(post_date)

        er = _calculate_er(views=views, reactions=reactions, comments=comments)

        normalized_posts.append(
            {
                "id": _to_int(post.get("id", 0)),
                "date": post.get("date", ""),
                "views": views,
                "reactions": reactions,
                "comments_count": comments,
                "text_length": text_length,
                "er": round(er, 2),
                "text_preview": _text_preview(text),
            }
        )

    posts_count = len(normalized_posts)
    if posts_count == 0:
        return {
            "summary": {
                "posts_count": 0,
                "avg_views": 0.0,
                "avg_er": 0.0,
                "avg_text_length": 0.0,
                "posts_per_day": 0.0,
            },
            "engagement": {
                "formula": "ER = (reactions + comments) / views * 100",
                "best_posts": [],
                "worst_posts": [],
            },
            "period": {
                "from": None,
                "to": None,
                "days": 0,
            },
        }

    total_views = sum(post["views"] for post in normalized_posts)
    total_er = sum(post["er"] for post in normalized_posts)
    total_text_length = sum(post["text_length"] for post in normalized_posts)

    avg_views = round(total_views / posts_count, 2)
    avg_er = round(total_er / posts_count, 2)
    avg_text_length = round(total_text_length / posts_count, 2)

    period_from, period_to, period_days = _resolve_period(parsed_dates)
    posts_per_day = round(posts_count / period_days, 2) if period_days > 0 else 0.0

    top_count = max(1, ceil(posts_count * 0.2))
    best_posts = sorted(
        normalized_posts,
        key=lambda post: (post["er"], post["views"]),
        reverse=True,
    )[:top_count]
    worst_posts = sorted(
        normalized_posts,
        key=lambda post: (post["er"], post["views"]),
    )[:top_count]

    return {
        "summary": {
            "posts_count": posts_count,
            "avg_views": avg_views,
            "avg_er": avg_er,
            "avg_text_length": avg_text_length,
            "posts_per_day": posts_per_day,
        },
        "engagement": {
            "formula": "ER = (reactions + comments) / views * 100",
            "best_posts": best_posts,
            "worst_posts": worst_posts,
        },
        "period": {
            "from": period_from,
            "to": period_to,
            "days": period_days,
        },
    }


def _calculate_er(views: int, reactions: int, comments: int) -> float:
    # При нулевых просмотрах считаем ER равным 0, чтобы избежать деления на ноль.
    if views <= 0:
        return 0.0
    return ((reactions + comments) / views) * 100


def _resolve_period(dates: list[datetime]) -> tuple[str | None, str | None, int]:
    if not dates:
        return None, None, 1

    start_dt = min(dates)
    end_dt = max(dates)
    days = max((end_dt.date() - start_dt.date()).days + 1, 1)
    return start_dt.isoformat(), end_dt.isoformat(), days


def _parse_datetime(raw_value: Any) -> datetime | None:
    if raw_value is None:
        return None

    raw = str(raw_value).strip()
    if not raw:
        return None

    # Поддерживаем ISO с суффиксом Z.
    normalized = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _text_preview(text: str, limit: int = 180) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 3]}..."

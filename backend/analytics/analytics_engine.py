from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from math import ceil
from typing import Any, TypedDict

# Маппинг номера дня недели (isoweekday) → русское название.
_WEEKDAY_NAMES = {
    1: "Понедельник",
    2: "Вторник",
    3: "Среда",
    4: "Четверг",
    5: "Пятница",
    6: "Суббота",
    7: "Воскресенье",
}


class PostData(TypedDict, total=False):
    id: int
    date: str
    text: str
    views: int
    reactions: int
    forwards: int
    comments_count: int
    comments: int


def calculate_metrics(posts: list[PostData]) -> dict[str, Any]:
    """Считает агрегированные метрики по списку постов и возвращает JSON-структуру."""

    normalized_posts: list[dict[str, Any]] = []
    parsed_dates: list[datetime] = []

    for post in posts:
        views = max(_to_int(post.get("views", 0)), 0)
        reactions = max(_to_int(post.get("reactions", 0)), 0)
        forwards = max(_to_int(post.get("forwards", 0)), 0)

        # Поддерживаем оба ключа: comments_count (основной) и comments (резервный).
        comments = max(_to_int(post.get("comments_count", post.get("comments", 0))), 0)

        text = str(post.get("text", "") or "")
        text_length = len(text)

        post_date = _parse_datetime(post.get("date"))
        if post_date is not None:
            parsed_dates.append(post_date)

        er = _calculate_er(views=views, reactions=reactions, forwards=forwards, comments=comments)

        normalized_posts.append(
            {
                "id": _to_int(post.get("id", 0)),
                "date": post.get("date", ""),
                "views": views,
                "reactions": reactions,
                "forwards": forwards,
                "comments_count": comments,
                "text_length": text_length,
                "er": round(er, 2),
                "text_preview": _text_preview(text),
            }
        )

    posts_count = len(normalized_posts)
    empty_result: dict[str, Any] = {
        "summary": {
            "posts_count": 0,
            "avg_views": 0.0,
            "avg_er": 0.0,
            "avg_forwards": 0.0,
            "avg_text_length": 0.0,
            "posts_per_day": 0.0,
        },
        "engagement": {
            "formula": "ER = (reactions + forwards + comments) / views * 100",
            "best_posts": [],
            "worst_posts": [],
        },
        "period": {"from": None, "to": None, "days": 0},
        "trends": {"weekly": [], "direction": "unknown"},
        "posting_time": {
            "by_hour": {},
            "best_hour": None,
            "by_weekday": {},
            "best_weekday": None,
        },
    }
    if posts_count == 0:
        return empty_result

    total_views = sum(p["views"] for p in normalized_posts)
    total_er = sum(p["er"] for p in normalized_posts)
    total_forwards = sum(p["forwards"] for p in normalized_posts)
    total_text_length = sum(p["text_length"] for p in normalized_posts)

    avg_views = round(total_views / posts_count, 2)
    avg_er = round(total_er / posts_count, 2)
    avg_forwards = round(total_forwards / posts_count, 2)
    avg_text_length = round(total_text_length / posts_count, 2)

    period_from, period_to, period_days = _resolve_period(parsed_dates)
    posts_per_day = round(posts_count / period_days, 2) if period_days > 0 else 0.0

    top_count = max(1, ceil(posts_count * 0.2))
    best_posts = sorted(
        normalized_posts,
        key=lambda p: (p["er"], p["views"]),
        reverse=True,
    )[:top_count]
    worst_posts = sorted(
        normalized_posts,
        key=lambda p: (p["er"], p["views"]),
    )[:top_count]

    # ── Тренды по неделям ──
    trends = _calculate_weekly_trends(normalized_posts, parsed_dates)

    # ── Анализ времени постинга ──
    posting_time = _calculate_posting_time(normalized_posts, parsed_dates)

    return {
        "summary": {
            "posts_count": posts_count,
            "avg_views": avg_views,
            "avg_er": avg_er,
            "avg_forwards": avg_forwards,
            "avg_text_length": avg_text_length,
            "posts_per_day": posts_per_day,
        },
        "engagement": {
            "formula": "ER = (reactions + forwards + comments) / views * 100",
            "best_posts": best_posts,
            "worst_posts": worst_posts,
        },
        "period": {
            "from": period_from,
            "to": period_to,
            "days": period_days,
        },
        "trends": trends,
        "posting_time": posting_time,
    }


# ── Вспомогательные функции ──


def _calculate_er(views: int, reactions: int, forwards: int, comments: int) -> float:
    """ER = (reactions + forwards + comments) / views * 100."""
    if views <= 0:
        return 0.0
    return ((reactions + forwards + comments) / views) * 100


def _calculate_weekly_trends(
    posts: list[dict[str, Any]],
    dates: list[datetime],
) -> dict[str, Any]:
    """Группирует посты по ISO-неделям, считает avg_er и avg_views за каждую."""
    if not dates:
        return {"weekly": [], "direction": "unknown"}

    # Группировка: iso_year-week → list[post]
    weekly_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for post, dt in zip(posts, dates):
        iso_year, iso_week, _ = dt.isocalendar()
        key = f"{iso_year}-W{iso_week:02d}"
        weekly_buckets[key] = weekly_buckets.get(key, [])
        weekly_buckets[key].append(post)

    weekly: list[dict[str, Any]] = []
    for week_key in sorted(weekly_buckets):
        bucket = weekly_buckets[week_key]
        count = len(bucket)
        w_avg_er = round(sum(p["er"] for p in bucket) / count, 2)
        w_avg_views = round(sum(p["views"] for p in bucket) / count, 2)
        weekly.append({
            "week": week_key,
            "posts_count": count,
            "avg_er": w_avg_er,
            "avg_views": w_avg_views,
        })

    # Направление: сравниваем первую и последнюю неделю.
    direction = "stable"
    if len(weekly) >= 2:
        first_er = weekly[0]["avg_er"]
        last_er = weekly[-1]["avg_er"]
        if first_er > 0:
            change_pct = ((last_er - first_er) / first_er) * 100
            if change_pct > 10:
                direction = "growing"
            elif change_pct < -10:
                direction = "declining"

    return {"weekly": weekly, "direction": direction}


def _calculate_posting_time(
    posts: list[dict[str, Any]],
    dates: list[datetime],
) -> dict[str, Any]:
    """Анализ: в какие часы и дни недели посты получают наибольший ER."""
    if not dates:
        return {
            "by_hour": {},
            "best_hour": None,
            "by_weekday": {},
            "best_weekday": None,
        }

    # Группировка по часу
    hour_buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)
    weekday_buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)

    for post, dt in zip(posts, dates):
        hour_buckets[dt.hour].append(post)
        weekday_buckets[dt.isoweekday()].append(post)

    # Средний ER по часам
    by_hour: dict[str, dict[str, Any]] = {}
    for hour in sorted(hour_buckets):
        bucket = hour_buckets[hour]
        count = len(bucket)
        avg_er = round(sum(p["er"] for p in bucket) / count, 2)
        avg_views = round(sum(p["views"] for p in bucket) / count, 2)
        by_hour[f"{hour:02d}:00"] = {
            "posts_count": count,
            "avg_er": avg_er,
            "avg_views": avg_views,
        }

    best_hour = max(by_hour, key=lambda h: by_hour[h]["avg_er"]) if by_hour else None

    # Средний ER по дням недели
    by_weekday: dict[str, dict[str, Any]] = {}
    for wd in sorted(weekday_buckets):
        bucket = weekday_buckets[wd]
        count = len(bucket)
        avg_er = round(sum(p["er"] for p in bucket) / count, 2)
        avg_views = round(sum(p["views"] for p in bucket) / count, 2)
        name = _WEEKDAY_NAMES.get(wd, str(wd))
        by_weekday[name] = {
            "posts_count": count,
            "avg_er": avg_er,
            "avg_views": avg_views,
        }

    best_weekday = max(by_weekday, key=lambda d: by_weekday[d]["avg_er"]) if by_weekday else None

    return {
        "by_hour": by_hour,
        "best_hour": best_hour,
        "by_weekday": by_weekday,
        "best_weekday": best_weekday,
    }


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

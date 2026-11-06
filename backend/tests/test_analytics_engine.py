from datetime import UTC, datetime, timedelta

import pytest

from backend.analytics.analytics_engine import calculate_metrics


def make_post(
    date: str = "2026-03-02T10:00:00+00:00",
    views: int = 100,
    reactions: int = 0,
    forwards: int = 0,
    comments: int = 0,
    text: str = "пост",
    post_id: int = 1,
) -> dict:
    return {
        "id": post_id,
        "date": date,
        "text": text,
        "views": views,
        "reactions": reactions,
        "forwards": forwards,
        "comments_count": comments,
    }


def weekly_post(weeks_after_start: int, er: int) -> dict:
    """Пост с заданным ER: при 100 просмотрах ER равен числу реакций."""
    start = datetime(2026, 3, 2, 10, tzinfo=UTC)
    return make_post(date=(start + timedelta(weeks=weeks_after_start)).isoformat(), reactions=er)


class TestEngagementRate:
    def test_counts_reactions_forwards_and_comments_against_views(self) -> None:
        metrics = calculate_metrics([make_post(views=200, reactions=10, forwards=6, comments=4)])

        assert metrics["summary"]["avg_er"] == 10.0
        assert metrics["engagement"]["best_posts"][0]["er"] == 10.0

    def test_zero_views_gives_zero_er_instead_of_division_error(self) -> None:
        metrics = calculate_metrics([make_post(views=0, reactions=10)])

        assert metrics["summary"]["avg_er"] == 0.0

    def test_legacy_comments_key_is_supported(self) -> None:
        post = make_post(views=100)
        del post["comments_count"]
        post["comments"] = 5

        assert calculate_metrics([post])["summary"]["avg_er"] == 5.0

    def test_negative_and_non_numeric_counters_are_treated_as_zero(self) -> None:
        post = make_post(reactions=-5)
        post["views"] = "not-a-number"

        metrics = calculate_metrics([post])

        assert metrics["summary"]["avg_views"] == 0.0
        assert metrics["summary"]["avg_er"] == 0.0

    def test_best_and_worst_posts_take_top_fifth_rounded_up(self) -> None:
        posts = [make_post(post_id=i, reactions=i) for i in range(1, 7)]

        metrics = calculate_metrics(posts)

        assert [p["id"] for p in metrics["engagement"]["best_posts"]] == [6, 5]
        assert [p["id"] for p in metrics["engagement"]["worst_posts"]] == [1, 2]


class TestSummary:
    def test_empty_list_returns_zeroes_and_unknown_trend(self) -> None:
        metrics = calculate_metrics([])

        assert metrics["summary"]["posts_count"] == 0
        assert metrics["summary"]["avg_er"] == 0.0
        assert metrics["period"] == {"from": None, "to": None, "days": 0}
        assert metrics["trends"] == {"weekly": [], "direction": "unknown"}
        assert metrics["posting_time"]["best_hour"] is None

    def test_single_post_is_its_own_best_and_worst(self) -> None:
        metrics = calculate_metrics([make_post(views=50, reactions=5)])

        assert metrics["summary"]["posts_count"] == 1
        assert metrics["summary"]["posts_per_day"] == 1.0
        assert metrics["engagement"]["best_posts"] == metrics["engagement"]["worst_posts"]
        assert metrics["trends"]["direction"] == "stable"

    def test_period_covers_both_edge_days(self) -> None:
        posts = [
            make_post(date="2026-03-02T23:59:00+00:00"),
            make_post(date="2026-03-11T00:01:00+00:00"),
        ]

        metrics = calculate_metrics(posts)

        assert metrics["period"]["days"] == 10
        assert metrics["summary"]["posts_per_day"] == 0.2

    def test_long_text_preview_is_trimmed_and_whitespace_collapsed(self) -> None:
        metrics = calculate_metrics([make_post(text="слово\n\n  " * 100)])

        preview = metrics["engagement"]["best_posts"][0]["text_preview"]
        assert len(preview) == 180
        assert preview.endswith("...")
        assert "\n" not in preview

    def test_z_suffix_date_is_parsed(self) -> None:
        metrics = calculate_metrics([make_post(date="2026-03-02T10:00:00Z")])

        assert metrics["period"]["from"] == "2026-03-02T10:00:00+00:00"


class TestBrokenDates:
    def test_post_with_broken_date_still_counts_in_summary(self) -> None:
        posts = [make_post(date="вчера", reactions=10), make_post(reactions=20)]

        metrics = calculate_metrics(posts)

        assert metrics["summary"]["posts_count"] == 2
        assert metrics["summary"]["avg_er"] == 15.0

    def test_all_dates_broken_leaves_time_analytics_empty(self) -> None:
        metrics = calculate_metrics([make_post(date="вчера"), make_post(date="")])

        assert metrics["period"]["from"] is None
        assert metrics["trends"] == {"weekly": [], "direction": "unknown"}
        assert metrics["posting_time"]["by_hour"] == {}

    @pytest.mark.xfail(
        strict=True,
        reason="Известный баг: zip(posts, dates) сдвигается, если у поста битая дата. "
        "Вне согласованного списка, ждёт решения.",
    )
    def test_broken_date_does_not_shift_er_to_another_post(self) -> None:
        posts = [
            make_post(date="битая", reactions=90),
            make_post(date="2026-03-02T10:00:00+00:00", reactions=10),
        ]

        metrics = calculate_metrics(posts)

        assert metrics["trends"]["weekly"][0]["avg_er"] == 10.0
        assert metrics["posting_time"]["by_hour"]["10:00"]["avg_er"] == 10.0


class TestWeeklyTrends:
    def test_posts_are_grouped_by_iso_week(self) -> None:
        posts = [
            make_post(date="2026-03-02T10:00:00+00:00", reactions=10),
            make_post(date="2026-03-08T10:00:00+00:00", reactions=20),
            make_post(date="2026-03-09T10:00:00+00:00", reactions=40),
        ]

        weekly = calculate_metrics(posts)["trends"]["weekly"]

        assert weekly == [
            {"week": "2026-W10", "posts_count": 2, "avg_er": 15.0, "avg_views": 100.0},
            {"week": "2026-W11", "posts_count": 1, "avg_er": 40.0, "avg_views": 100.0},
        ]

    def test_weeks_across_new_year_stay_in_chronological_order(self) -> None:
        posts = [make_post(date="2027-01-04T10:00:00+00:00"), make_post(date="2026-12-28T10:00:00+00:00")]

        weekly = calculate_metrics(posts)["trends"]["weekly"]

        assert [w["week"] for w in weekly] == ["2026-W53", "2027-W01"]

    @pytest.mark.parametrize(
        ("first_er", "last_er", "direction"),
        [
            (10, 12, "growing"),
            (10, 8, "declining"),
            (10, 11, "stable"),
            (10, 9, "stable"),
        ],
    )
    def test_direction_uses_ten_percent_threshold(self, first_er: int, last_er: int, direction: str) -> None:
        metrics = calculate_metrics([weekly_post(0, first_er), weekly_post(3, last_er)])

        assert metrics["trends"]["direction"] == direction


class TestPostingTime:
    def test_best_hour_and_weekday_have_highest_average_er(self) -> None:
        posts = [
            make_post(date="2026-03-02T09:00:00+00:00", reactions=1),
            make_post(date="2026-03-02T09:30:00+00:00", reactions=3),
            make_post(date="2026-03-03T18:00:00+00:00", reactions=30),
        ]

        posting_time = calculate_metrics(posts)["posting_time"]

        assert posting_time["by_hour"]["09:00"] == {"posts_count": 2, "avg_er": 2.0, "avg_views": 100.0}
        assert posting_time["best_hour"] == "18:00"
        assert posting_time["best_weekday"] == "Вторник"
        assert posting_time["by_weekday"]["Понедельник"]["posts_count"] == 2

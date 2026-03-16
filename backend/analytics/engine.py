from dataclasses import dataclass


@dataclass(slots=True)
class AnalyticsEngine:
    """Вычисление агрегированных метрик по данным канала."""

    def build_metrics(self, raw_data: dict) -> dict:
        posts = raw_data.get("posts", [])
        posts_count = len(posts)

        if posts_count == 0:
            return {
                "posts_count": 0,
                "avg_views": 0.0,
                "avg_reactions": 0.0,
                "avg_forwards": 0.0,
                "engagement_rate": 0.0,
            }

        total_views = sum(post.get("views", 0) for post in posts)
        total_reactions = sum(post.get("reactions", 0) for post in posts)
        total_forwards = sum(post.get("forwards", 0) for post in posts)

        avg_views = total_views / posts_count
        avg_reactions = total_reactions / posts_count
        avg_forwards = total_forwards / posts_count

        engagement_rate = 0.0
        if total_views > 0:
            engagement_rate = (total_reactions / total_views) * 100

        return {
            "posts_count": posts_count,
            "avg_views": round(avg_views, 2),
            "avg_reactions": round(avg_reactions, 2),
            "avg_forwards": round(avg_forwards, 2),
            "engagement_rate": round(engagement_rate, 2),
        }

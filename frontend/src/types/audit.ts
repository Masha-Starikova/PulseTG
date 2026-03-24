/* Типы данных аудита, соответствующие бэкенд-схемам */

export type AuditStatus = 'pending' | 'running' | 'completed' | 'failed';

/* Пост с метриками */
export interface PostMetrics {
  id: number;
  date: string;
  views: number;
  reactions: number;
  forwards: number;
  comments_count: number;
  text_length: number;
  er: number;
  text_preview: string;
}

/* Недельный тренд */
export interface WeeklyTrend {
  week: string;
  posts_count: number;
  avg_er: number;
  avg_views: number;
}

/* Статистика по часу / дню недели */
export interface TimeSlotStats {
  posts_count: number;
  avg_er: number;
  avg_views: number;
}

/* Метрики (вложены в report.metrics) */
export interface AuditMetrics {
  summary: {
    posts_count: number;
    avg_views: number;
    avg_er: number;
    avg_forwards: number;
    avg_text_length: number;
    posts_per_day: number;
  };
  engagement: {
    formula: string;
    best_posts: PostMetrics[];
    worst_posts: PostMetrics[];
  };
  period: {
    from: string | null;
    to: string | null;
    days: number;
  };
  trends: {
    weekly: WeeklyTrend[];
    direction: 'growing' | 'declining' | 'stable' | 'unknown';
  };
  posting_time: {
    by_hour: Record<string, TimeSlotStats>;
    best_hour: string | null;
    by_weekday: Record<string, TimeSlotStats>;
    best_weekday: string | null;
  };
}

/* AI-аналитика (вложена в report.ai)
 * NB: backend может вернуть strengths/problems как строку (не массив),
 * поэтому фронтенд нормализует через toStringArray(). */
export interface AuditAI {
  status: string;
  summary: string;
  recommendations: string[];
  strengths?: string[] | string;
  problems?: string[] | string;
  forecast?: string;
  optimal_time?: string;
  best_post_insight?: string;
  raw_text?: string;
}

/* Полный отчёт — структура, которую возвращает бэкенд */
export interface AuditReport {
  channel: string;
  period_days: number;
  posts?: Array<{
    id: number;
    date: string;
    text: string;
    views: number;
    reactions: number;
    forwards?: number;
    comments_count: number;
  }>;
  metrics: AuditMetrics;
  ai?: AuditAI;
}

/* Ответ API аудита */
export interface AuditResponse {
  id: string;
  channel_username: string;
  status: AuditStatus;
  report: AuditReport | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

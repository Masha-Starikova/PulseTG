import type { AuditMetrics, AuditReport, AuditResponse } from '../types/audit';

const API_BASE = '/api/v1';

class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

type JsonRecord = Record<string, unknown>;

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === 'object' && value !== null;
}

/* FastAPI отдаёт detail строкой, а ошибки валидации (422) списком объектов */
function errorMessage(detail: unknown, fallback: string): string {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && isRecord(detail[0]) && typeof detail[0].msg === 'string') {
    return detail[0].msg.replace(/^Value error, /, '');
  }
  return fallback;
}

function toNumber(value: unknown): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function normalizeStatus(value: unknown): AuditResponse['status'] {
  if (value === 'pending' || value === 'running' || value === 'completed' || value === 'failed') {
    return value;
  }
  return 'pending';
}

function parseReport(report: unknown): JsonRecord | null {
  if (!report) return null;
  if (isRecord(report)) return report;

  if (typeof report === 'string') {
    try {
      const parsed = JSON.parse(report);
      return isRecord(parsed) ? parsed : null;
    } catch {
      return null;
    }
  }

  return null;
}

function isAuditMetrics(value: unknown): value is AuditMetrics {
  if (!isRecord(value)) return false;
  return isRecord(value.summary)
    && isRecord(value.engagement)
    && isRecord(value.period)
    && isRecord(value.trends)
    && isRecord(value.posting_time);
}

function buildMetricsFromPosts(posts: unknown[]): AuditMetrics {
  const normalized = posts
    .filter(isRecord)
    .map((post) => {
      const views = toNumber(post.views);
      const reactions = toNumber(post.reactions);
      const forwards = toNumber(post.forwards);
      const comments = toNumber(post.comments_count ?? post.comments);
      const text = typeof post.text === 'string' ? post.text : '';
      const er = views > 0 ? ((reactions + forwards + comments) / views) * 100 : 0;

      return {
        id: toNumber(post.id),
        date: typeof post.date === 'string' ? post.date : '',
        views,
        reactions,
        forwards,
        comments_count: comments,
        text_length: text.length,
        text_preview: text.slice(0, 180),
        er: Number(er.toFixed(2)),
      };
    });

  const postsCount = normalized.length;
  const totalViews = normalized.reduce((acc, p) => acc + p.views, 0);
  const totalEr = normalized.reduce((acc, p) => acc + p.er, 0);
  const totalForwards = normalized.reduce((acc, p) => acc + p.forwards, 0);
  const totalTextLength = normalized.reduce((acc, p) => acc + p.text_length, 0);

  const sortedByEr = [...normalized].sort((a, b) => b.er - a.er);
  const bucketSize = Math.max(1, Math.ceil(postsCount * 0.2));
  const bestPosts = sortedByEr.slice(0, bucketSize);
  const worstPosts = [...normalized].sort((a, b) => a.er - b.er).slice(0, bucketSize);

  // Готовим данные для графика "по времени публикации".
  const byHourMap = new Map<string, { posts_count: number; er_sum: number; views_sum: number }>();
  for (const p of normalized) {
    const dt = new Date(p.date);
    if (Number.isNaN(dt.getTime())) continue;

    const key = `${String(dt.getHours()).padStart(2, '0')}:00`;
    const prev = byHourMap.get(key) ?? { posts_count: 0, er_sum: 0, views_sum: 0 };
    byHourMap.set(key, {
      posts_count: prev.posts_count + 1,
      er_sum: prev.er_sum + p.er,
      views_sum: prev.views_sum + p.views,
    });
  }

  const byHour: Record<string, { posts_count: number; avg_er: number; avg_views: number }> = {};
  for (const [hour, value] of byHourMap.entries()) {
    byHour[hour] = {
      posts_count: value.posts_count,
      avg_er: Number((value.er_sum / value.posts_count).toFixed(2)),
      avg_views: Number((value.views_sum / value.posts_count).toFixed(2)),
    };
  }

  const bestHour = Object.keys(byHour).sort((a, b) => byHour[b].avg_er - byHour[a].avg_er)[0] ?? null;

  // Готовим недельный тренд ER.
  const weeklyMap = new Map<string, { posts_count: number; er_sum: number; views_sum: number }>();
  for (const p of normalized) {
    const dt = new Date(p.date);
    if (Number.isNaN(dt.getTime())) continue;

    const week = isoWeekLabel(dt);
    const prev = weeklyMap.get(week) ?? { posts_count: 0, er_sum: 0, views_sum: 0 };
    weeklyMap.set(week, {
      posts_count: prev.posts_count + 1,
      er_sum: prev.er_sum + p.er,
      views_sum: prev.views_sum + p.views,
    });
  }

  const weekly = [...weeklyMap.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([week, value]) => ({
      week,
      posts_count: value.posts_count,
      avg_er: Number((value.er_sum / value.posts_count).toFixed(2)),
      avg_views: Number((value.views_sum / value.posts_count).toFixed(2)),
    }));

  let direction: 'growing' | 'declining' | 'stable' | 'unknown' = 'unknown';
  if (weekly.length >= 2) {
    const first = weekly[0].avg_er;
    const last = weekly[weekly.length - 1].avg_er;
    const delta = last - first;
    if (delta > 0.5) direction = 'growing';
    else if (delta < -0.5) direction = 'declining';
    else direction = 'stable';
  } else if (weekly.length === 1) {
    direction = 'stable';
  }

  return {
    summary: {
      posts_count: postsCount,
      avg_views: Number((postsCount ? totalViews / postsCount : 0).toFixed(2)),
      avg_er: Number((postsCount ? totalEr / postsCount : 0).toFixed(2)),
      avg_forwards: Number((postsCount ? totalForwards / postsCount : 0).toFixed(2)),
      avg_text_length: Number((postsCount ? totalTextLength / postsCount : 0).toFixed(2)),
      posts_per_day: 0,
    } as AuditMetrics['summary'],
    engagement: {
      formula: 'ER = (reactions + forwards + comments) / views * 100',
      best_posts: bestPosts,
      worst_posts: worstPosts,
    } as AuditMetrics['engagement'],
    period: {
      from: null,
      to: null,
      days: 0,
    } as AuditMetrics['period'],
    trends: {
      weekly,
      direction,
    } as AuditMetrics['trends'],
    posting_time: {
      by_hour: byHour,
      best_hour: bestHour,
      by_weekday: {},
      best_weekday: null,
    } as AuditMetrics['posting_time'],
  };
}

function isoWeekLabel(date: Date): string {
  const dt = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const dayNum = dt.getUTCDay() || 7;
  dt.setUTCDate(dt.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(dt.getUTCFullYear(), 0, 1));
  const weekNo = Math.ceil((((dt.getTime() - yearStart.getTime()) / 86400000) + 1) / 7);
  return `${dt.getUTCFullYear()}-W${String(weekNo).padStart(2, '0')}`;
}

function normalizeAuditResponse(raw: unknown): AuditResponse {
  const data = isRecord(raw) ? raw : {};
  const report = parseReport(data.report);
  const reportPosts = Array.isArray(report?.posts) ? report.posts : [];

  // Если backend не прислал metrics или прислал их в другом формате,
  // строим минимально достаточную структуру из posts.
  let normalizedReport: AuditReport | null = null;
  if (report) {
    const metrics = isAuditMetrics(report.metrics) ? report.metrics : buildMetricsFromPosts(reportPosts);
    const ai = isRecord(report.ai) ? report.ai : undefined;

    normalizedReport = {
      ...report,
      channel:
        typeof report.channel === 'string'
          ? report.channel
          : (typeof data.channel_username === 'string' ? data.channel_username : ''),
      period_days: Math.max(1, toNumber(report.period_days) || 30),
      posts: reportPosts as AuditReport['posts'],
      metrics,
      ai: ai as AuditReport['ai'],
    };
  }

  return {
    id: typeof data.id === 'string' ? data.id : '',
    channel_username: typeof data.channel_username === 'string' ? data.channel_username : '',
    status: normalizeStatus(data.status),
    report: normalizedReport,
    error_message: typeof data.error_message === 'string' ? data.error_message : null,
    created_at: typeof data.created_at === 'string' ? data.created_at : '',
    updated_at: typeof data.updated_at === 'string' ? data.updated_at : '',
  };
}

/* Создание нового аудита */
export async function createAudit(channelUsername: string): Promise<AuditResponse> {
  const res = await fetch(`${API_BASE}/audits`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ channel_username: channelUsername }),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, errorMessage(body.detail, 'Не удалось создать аудит'));
  }

  const data = normalizeAuditResponse(await res.json());
  console.log('AUDIT CREATED RESPONSE', data);
  return data;
}

/* Получение аудита по ID */
export async function getAudit(auditId: string): Promise<AuditResponse> {
  const res = await fetch(`${API_BASE}/audits/${auditId}`);

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, errorMessage(body.detail, 'Аудит не найден'));
  }

  const data = normalizeAuditResponse(await res.json());
  console.log('AUDIT RESPONSE', data);
  console.log('REPORT:', data.report);
  console.log('REPORT KEYS:', data.report ? Object.keys(data.report) : 'null');
  if (data.report && isRecord(data.report.metrics)) {
    console.log('METRICS KEYS:', Object.keys(data.report.metrics));
  }
  if (data.report && isRecord(data.report.ai)) {
    console.log('AI KEYS:', Object.keys(data.report.ai));
    console.log('AI STRENGTHS TYPE:', typeof data.report.ai.strengths);
    console.log('AI PROBLEMS TYPE:', typeof data.report.ai.problems);
  }
  return data;
}
